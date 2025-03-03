import tempfile
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiopath import AsyncPath
from crackerjack.crackerjack import Crackerjack


@pytest.mark.asyncio
class TestCrackerjack(unittest.IsolatedAsyncioTestCase):
    temp_dir: tempfile.TemporaryDirectory[Any]

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pkg_path = AsyncPath(self.temp_dir.name)
        self.crackerjack_path = AsyncPath(__file__).parent
        self.settings_path = self.pkg_path / ".crackerjack.yaml"
        self.pkg_name = "test_package"
        self.pkg_dir = self.pkg_path / self.pkg_name
        self.crackerjack = Crackerjack(
            pkg_path=self.pkg_path,
            pkg_name=self.pkg_name,
            settings_path=self.settings_path,
        )
        await self.pkg_dir.mkdir(exist_ok=True)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("crackerjack.crackerjack.load.yaml")
    @patch("crackerjack.crackerjack.dump.yaml")
    async def test_load_config(
        self, mock_dump_yaml: AsyncMock, mock_load_yaml: AsyncMock
    ) -> None:
        # Test loading existing config.
        mock_load_yaml.return_value = {"python_version": "3.12"}
        await self.crackerjack.load_config()
        self.assertEqual(self.crackerjack.config.python_version, "3.12")
        mock_load_yaml.assert_called_once_with(self.settings_path)
        mock_dump_yaml.assert_not_called()

        # Test creating a new default config if none exists
        mock_load_yaml.side_effect = TypeError
        with pytest.raises(SystemExit):
            await self.crackerjack.load_config()  # type: ignore
        mock_dump_yaml.assert_called_once_with(
            {"python_version": "3.13"}, self.settings_path
        )

    @patch("crackerjack.crackerjack.load.toml")
    @patch("crackerjack.crackerjack.dump.toml")
    async def test_update_pyproject_configs(
        self,
        mock_dump_toml: AsyncMock,
        mock_load_toml: AsyncMock,
    ) -> None:
        mock_load_toml.side_effect = (
            {
                "tool": {
                    "ruff": {
                        "exclude-deps": ["foo"],
                        "exclude": ["bar"],
                        "line-length": 88,
                        "select": ["C", "F"],
                        "skips": ["test_file.py"],
                    },
                    "mypy": {
                        "exclude": ["foo"],
                    },
                },
                "project": {
                    "requires-python": ">=3.9",
                    "classifiers": ["Programming Language :: Python :: 3.10"],
                },
                "dependency-groups": {"dev": ["test", "dev"]},
            },
            {
                "tool": {
                    "ruff": {
                        "exclude": ["test_file.py"],
                        "exclude-deps": ["bar"],
                        "ignore": ["foo", "bar"],
                        "skips": ["test_file_2.py"],
                    },
                    "mypy": {
                        "exclude": ["bar"],
                        "ignore": ["foo", "bar"],
                    },
                },
                "dependency-groups": {"dev": ["test", "dev"]},
            },
        )

        await self.crackerjack.load_config()
        self.crackerjack.our_path = self.crackerjack_path
        self.crackerjack.pkg_path = self.pkg_path
        self.crackerjack.config.python_version = "3.12"

        await self.crackerjack.update_pyproject_configs()

        mock_dump_toml.assert_called_once()
        args, _ = mock_dump_toml.call_args
        result = args[0]

        self.assertIn("tool", result)
        self.assertEqual(result["tool"]["ruff"]["exclude-deps"], {"foo", "bar"})
        self.assertEqual(result["tool"]["ruff"]["exclude"], ["test_file.py"])
        self.assertEqual(result["tool"]["mypy"]["exclude"], ["foo", "bar"])
        self.assertEqual(
            result["tool"]["ruff"]["skips"], {"test_file.py", "test_file_2.py"}
        )
        self.assertEqual(
            result["project"]["classifiers"], ["Programming Language :: Python :: 3.12"]
        )
        self.assertEqual(result["project"]["requires-python"], ">=3.9")

        self.assertEqual(result["dependency-groups"], {"dev": ["test", "dev"]})

    @patch("crackerjack.crackerjack.execute")
    async def test_copy_configs(self, mock_execute: AsyncMock) -> None:
        mock_execute.return_value = MagicMock(returncode=0)

        config_files = (".gitignore", ".pre-commit-config.yaml", ".libcst.codemod.yaml")  # type: ignore
        for config in config_files:
            config_path = self.crackerjack.our_path / config
            await config_path.touch(exist_ok=True)
            if config != ".gitignore":
                await config_path.write_text("test crackerjack config")

        await self.crackerjack.copy_configs()

        for config in config_files:
            pkg_config_path = self.pkg_path / config
            self.assertTrue(await pkg_config_path.exists())

        mock_execute.assert_called()

    @patch("crackerjack.crackerjack.ainput")
    @patch("crackerjack.crackerjack.aprint")
    @patch("crackerjack.crackerjack.execute")
    async def test_run_interactive(
        self,
        mock_execute: AsyncMock,
        mock_aprint: AsyncMock,
        mock_ainput: AsyncMock,
    ) -> None:
        mock_execute.return_value = MagicMock(returncode=0)
        mock_ainput.return_value = "y"

        await self.crackerjack.run_interactive("refurb")

        mock_execute.assert_called_with(["pre-commit", "run", "refurb", "--all-files"])
        mock_aprint.assert_called_once()
        mock_ainput.assert_called_once()

        mock_execute.reset_mock()
        mock_aprint.reset_mock()
        mock_ainput.reset_mock()

        mock_execute.return_value = MagicMock(returncode=1)
        mock_ainput.return_value = "n"

        with pytest.raises(SystemExit):
            await self.crackerjack.run_interactive("bandit")  # type: ignore
        mock_execute.assert_called_with(["pre-commit", "run", "bandit", "--all-files"])
        mock_aprint.assert_not_called()
        mock_ainput.assert_called_once()

    @patch("crackerjack.crackerjack.execute")
    async def test_update_pkg_configs(self, mock_execute: AsyncMock) -> None:
        mock_execute.return_value = MagicMock(stdout="", returncode=0)
        await self.crackerjack.copy_configs()
        await self.crackerjack.update_pkg_configs()
        mock_execute.assert_called()

    @patch("crackerjack.crackerjack.execute")
    @patch("crackerjack.crackerjack.ainput")
    async def test_process(
        self,
        mock_ainput: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        mock_ainput.return_value = "test commit msg"
        options = MagicMock(
            do_not_update_configs=False,
            update_precommit=False,
            interactive=False,
            publish=None,
            bump=None,
            commit=False,
        )

        mock_execute.return_value = MagicMock(stdout="", returncode=0)
        self.crackerjack.pkg_path.stem = "crackerjack"  # type: ignore
        await self.crackerjack.process(options)

        self.assertEqual(self.crackerjack.pkg_name, "crackerjack")
        self.assertTrue(await (self.crackerjack.pkg_path / "crackerjack").exists())
        mock_execute.assert_called()

    @patch("crackerjack.crackerjack.execute")
    @patch("crackerjack.crackerjack.ainput")
    @patch("crackerjack.crackerjack.aprint")
    async def test_run_commit(
        self,
        mock_aprint: AsyncMock,
        mock_ainput: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        mock_ainput.return_value = "test commit msg"
        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish=None,
            bump=None,
            commit=True,
        )
        mock_execute.return_value = MagicMock(stdout="", returncode=0)

        await self.crackerjack.process(options)
        mock_execute.assert_called()
        mock_ainput.assert_called_once()

        mock_execute.reset_mock()
        mock_ainput.reset_mock()

        mock_ainput.return_value = "test commit msg 2"
        await self.crackerjack.process(options)
        mock_execute.assert_called()
        mock_ainput.assert_called_once()

    @patch("crackerjack.crackerjack.execute")
    @patch("crackerjack.crackerjack.ainput")
    @patch("crackerjack.crackerjack.aprint")
    async def test_run_publish_bump(
        self,
        mock_aprint: AsyncMock,
        mock_ainput: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish="major",
            bump="minor",
            commit=False,
        )
        mock_execute.return_value = MagicMock(stdout="", returncode=0)
        await self.crackerjack.process(options)

        calls = [c[0][0] for c in mock_execute.call_args_list]
        self.assertIn(["pdm", "bump", "minor"], calls)
        self.assertNotIn(["pdm", "bump", "major"], calls)

        mock_execute.reset_mock()
        mock_ainput.reset_mock()

        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish="major",
            bump=None,
            commit=False,
        )
        mock_execute.return_value = MagicMock(stdout="", returncode=0)
        await self.crackerjack.process(options)
        calls = [c[0][0] for c in mock_execute.call_args_list]
        self.assertIn(["pdm", "bump", "major"], calls)
        self.assertIn(["pdm", "build"], calls)
        self.assertIn(["pdm", "publish", "--no-build"], calls)

        mock_execute.reset_mock()
        mock_ainput.reset_mock()
        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish="major",
            bump="major",
            commit=False,
        )
        mock_execute.return_value = MagicMock(stdout="", returncode=0)
        await self.crackerjack.process(options)
        calls = [c[0][0] for c in mock_execute.call_args_list]
        self.assertIn(["pdm", "bump", "major"], calls)
        self.assertIn(["pdm", "build"], calls)
        self.assertIn(["pdm", "publish", "--no-build"], calls)

        mock_execute.reset_mock()
        mock_ainput.reset_mock()
        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish=None,
            bump="major",
            commit=False,
        )
        mock_execute.return_value = MagicMock(stdout="", returncode=0)
        await self.crackerjack.process(options)
        calls = [c[0][0] for c in mock_execute.call_args_list]
        self.assertIn(["pdm", "bump", "major"], calls)
        self.assertNotIn(["pdm", "build"], calls)
        self.assertNotIn(["pdm", "publish", "--no-build"], calls)

    @patch("crackerjack.crackerjack.execute")
    @patch("crackerjack.crackerjack.ainput")
    @patch("crackerjack.crackerjack.aprint")
    async def test_run_publish_fail(
        self,
        mock_aprint: AsyncMock,
        mock_ainput: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish="major",
            bump=None,
            commit=False,
        )

        mock_execute.side_effect = [
            MagicMock(stdout="", returncode=1, stderr="Failed"),  # type: ignore
        ]

        with pytest.raises(SystemExit):
            await self.crackerjack.process(options)
        mock_execute.assert_called()

    @patch("crackerjack.crackerjack.execute")
    @patch("crackerjack.crackerjack.ainput")
    @patch("crackerjack.crackerjack.aprint")
    async def test_run_pre_commit_fail(
        self,
        mock_aprint: AsyncMock,
        mock_ainput: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        options = MagicMock(
            do_not_update_configs=True,
            update_precommit=False,
            interactive=False,
            publish="major",
            bump=None,
            commit=False,
        )

        mock_execute.side_effect = [
            MagicMock(stdout="", returncode=1, stderr="Failed"),  # type: ignore
            MagicMock(stdout="", returncode=1, stderr="Failed"),  # type: ignore
        ]
        with pytest.raises(SystemExit):
            await self.crackerjack.process(options)
        mock_execute.assert_called()
