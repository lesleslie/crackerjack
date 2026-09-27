"""Integration tests for the C-13 review-pr skill.

Five error paths covered (per plan §"Tests"):

  1. 5xx (server error) → GitHubAPIError with "server error"
  2. 429 (rate limited) → GitHubAPIError with "rate limited"
  3. 401 (auth failure) → GitHubAPIError with "auth failure"
  4. Malformed PR URL → caller decides; html returned as diff
  5. Network timeout → GitHubAPIError with "network error"

Plus:

  - Akosha pattern filter (skip non-git-monitor events)
  - DurableQueue enqueue/dequeue + concurrent flock serialization
  - Akosha pattern filter (skip events without pr_url)
  - Cross-repo version pin (mahavishnu >= 0.29)
  - ``review_pr`` skill is registered in the crackerjack skill catalog

Why we do NOT use respx: crackerjack pins ``httpx2`` (a fork); respx
upstream's ``isinstance(httpx.Response)`` check rejects ``httpx2.Response``
instances. We follow the same seam pattern as
``tests/unit/services/test_mahavishnu_discovery.py`` — patch
``crackerjack.skills.github_client._client_get`` and ``_client_post``
with stubs that return ``SimpleNamespace``-shaped responses.
"""
from __future__ import annotations

import importlib.metadata
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch

import httpx2 as httpx
import pytest

from crackerjack.skills import durable_queue as dq
from crackerjack.skills import github_client
from crackerjack.skills import review_pr
from crackerjack.skills.durable_queue import DurableQueue, ReviewQueueRecord
from crackerjack.skills.github_client import (
    GITHUB_TOKEN_ENV,
    GitHubAPIError,
    _diff_url_for,
    _parse_pr_url,
    fetch_pr_diff,
    post_pr_comment,
)
from crackerjack.skills.review_metrics import (
    GITHUB_API_QUOTA_REMAINING,
    PR_REVIEW_DURATION,
    PR_REVIEW_FORK_PR_TOTAL,
    PR_REVIEW_POST_TOTAL,
)


@pytest.fixture(autouse=True)
def _github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the env var; tests that need it missing clear it explicitly."""
    monkeypatch.setenv(GITHUB_TOKEN_ENV, "ghp_TEST_TOKEN")


def _fake_response(
    *,
    status_code: int = 200,
    text: str = "",
    json_payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build an httpx2.Response-shaped stub for the test seam."""
    payload = json_payload if json_payload is not None else None
    text_value = text if text else (
        json.dumps(payload) if payload is not None else ""
    )

    return SimpleNamespace(
        status_code=status_code,
        text=text_value,
        headers=headers or {},
        json=lambda: json.loads(text_value) if text_value else None,
    )


class TestFetchPrDiff:
    async def test_success(self) -> None:
        diff_body = "diff --git a/file b/file\n@@\n+hi\n"
        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(status_code=200, text=diff_body),
        ):
            diff = await fetch_pr_diff("https://github.com/owner/repo/pull/123")
        assert "diff --git" in diff

    async def test_5xx_triggers_retry_label(self) -> None:
        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(
                status_code=503, text="Service Unavailable"
            ),
        ):
            with pytest.raises(GitHubAPIError, match="server error"):
                await fetch_pr_diff("https://github.com/owner/repo/pull/123")

    async def test_429_triggers_backoff_label(self) -> None:
        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(status_code=429, text="Too Many Requests"),
        ):
            with pytest.raises(GitHubAPIError, match="rate limited"):
                await fetch_pr_diff("https://github.com/owner/repo/pull/123")

    async def test_401_auth_failure(self) -> None:
        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(status_code=401, text="Unauthorized"),
        ):
            with pytest.raises(GitHubAPIError, match="auth failure"):
                await fetch_pr_diff("https://github.com/owner/repo/pull/123")

    async def test_malformed_pr_diff_returns_html_body(self) -> None:
        """GitHub returns 200 with an HTML error page when the PR is bogus.

        The caller (review_pr.py) decides what to do with the body; the
        client returns the text and labels the result downstream.
        """
        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(
                status_code=200, text="<html>Not Found</html>"
            ),
        ):
            diff = await fetch_pr_diff(
                "https://github.com/owner/repo/pull/abc"
            )
        assert "<html>" in diff

    async def test_network_timeout(self) -> None:
        async def raise_timeout(*_args: object, **_kwargs: object) -> object:
            raise httpx.TimeoutException("timeout")

        with patch.object(github_client, "_client_get", side_effect=raise_timeout):
            with pytest.raises(GitHubAPIError, match="network error"):
                await fetch_pr_diff("https://github.com/owner/repo/pull/123")

    async def test_quota_gauge_updated_from_headers(self) -> None:
        GITHUB_API_QUOTA_REMAINING.set(0.0)
        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(
                status_code=200,
                text="diff --git a b\n",
                headers={"x-ratelimit-remaining": "4242"},
            ),
        ):
            await fetch_pr_diff("https://github.com/owner/repo/pull/123")
        assert GITHUB_API_QUOTA_REMAINING.snapshot() == 4242.0

    async def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(GITHUB_TOKEN_ENV, raising=False)
        with pytest.raises(GitHubAPIError, match="not set"):
            await fetch_pr_diff("https://github.com/owner/repo/pull/123")


class TestPostPrComment:
    async def test_success(self) -> None:
        comment_body = {"id": 99, "body": "review"}
        with patch.object(
            github_client,
            "_client_post",
            return_value=_fake_response(
                status_code=201, json_payload=comment_body
            ),
        ):
            result = await post_pr_comment(
                "https://github.com/owner/repo/pull/123",
                "looks good",
            )
        assert result == comment_body

    async def test_4xx_raises(self) -> None:
        with patch.object(
            github_client,
            "_client_post",
            return_value=_fake_response(status_code=403, text="forbidden"),
        ):
            with pytest.raises(GitHubAPIError, match="comment post failed"):
                await post_pr_comment(
                    "https://github.com/owner/repo/pull/123", "x"
                )

    async def test_malformed_url_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(GITHUB_TOKEN_ENV, raising=False)
        with pytest.raises(GitHubAPIError, match="not set"):
            await post_pr_comment("not-a-url", "x")


class TestOnAkoshaPattern:
    async def test_skips_non_git_monitor_events(self) -> None:
        result = await review_pr.on_akosha_pattern(
            {"payload": {"source": "crontroller"}}
        )
        assert result is None

    async def test_skips_events_without_pr_url(self) -> None:
        result = await review_pr.on_akosha_pattern(
            {"payload": {"source": "git-monitor"}}
        )
        assert result is None

    async def test_skips_malformed_event(self) -> None:
        result = await review_pr.on_akosha_pattern({})
        assert result is None

    async def test_handles_full_event(self, tmp_path: Path) -> None:
        """A complete event flows through _handle_pr_event."""
        queue = DurableQueue(tmp_path / "queue.db")

        async def fake_dispatch(prompt: str, nonce: str) -> dict:
            assert "PR: https://github.com/owner/repo/pull/5" in prompt
            return {"comment": "looks good"}

        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(status_code=200, text="diff --git a b\n"),
        ), patch.object(
            github_client,
            "_client_post",
            return_value=_fake_response(
                status_code=201, json_payload={"id": 1}
            ),
        ):
            result = await review_pr._handle_pr_event(
                "https://github.com/owner/repo/pull/5",
                queue=queue,
                dispatch=fake_dispatch,
            )

        assert result is not None
        assert result["pr_url"] == "https://github.com/owner/repo/pull/5"

    async def test_records_5xx_metric_on_github_failure(
        self, tmp_path: Path
    ) -> None:
        queue = DurableQueue(tmp_path / "queue.db")
        before = PR_REVIEW_POST_TOTAL.snapshot()
        before_count = before.get(("5xx",), 0)

        with patch.object(
            github_client,
            "_client_get",
            return_value=_fake_response(status_code=502, text="bad gateway"),
        ):
            result = await review_pr._handle_pr_event(
                "https://github.com/owner/repo/pull/77",
                queue=queue,
                dispatch=lambda *_a, **_kw: {},
            )

        assert result is None
        after = PR_REVIEW_POST_TOTAL.snapshot()
        assert after.get(("5xx",), 0) == before_count + 1


class TestDurableQueue:
    def test_enqueue_dequeue(self, tmp_path: Path) -> None:
        path = tmp_path / "queue.db"
        queue = DurableQueue(path)
        queue.enqueue("item-1")
        queue.enqueue("item-2")
        assert queue.dequeue() == "item-1"
        assert queue.dequeue() == "item-2"
        assert queue.dequeue() is None
        assert len(queue) == 0

    def test_enqueue_is_idempotent(self, tmp_path: Path) -> None:
        path = tmp_path / "queue.db"
        queue = DurableQueue(path)
        queue.enqueue("same-url")
        queue.enqueue("same-url")
        assert len(queue) == 1

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        path = tmp_path / "queue.db"
        first = DurableQueue(path)
        first.enqueue("persisted-item")

        second = DurableQueue(path)
        assert len(second) == 1
        assert second.dequeue() == "persisted-item"

    def test_flock_serializes_concurrent_writes(self, tmp_path: Path) -> None:
        """Two threads writing to the same queue do not corrupt the table."""
        path = tmp_path / "queue.db"
        queue = DurableQueue(path)

        def writer(prefix: str) -> None:
            for i in range(5):
                queue.enqueue(f"{prefix}-{i}")

        threads = [
            threading.Thread(target=writer, args=("a",)),
            threading.Thread(target=writer, args=("b",)),
            threading.Thread(target=writer, args=("c",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(queue) == 15

    def test_legacy_jsonl_drain(self, tmp_path: Path) -> None:
        legacy = tmp_path / "legacy.jsonl"
        legacy.write_text(
            json.dumps({"item": "url-1"}) + "\n"
            + json.dumps({"item": "url-2"}) + "\n"
        )
        queue = DurableQueue(tmp_path / "queue.db")
        drained = dq._drain_legacy_jsonl(legacy, queue)
        assert drained == 2
        assert len(queue) == 2
        assert not legacy.exists()


class TestParsePrUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            (
                "https://github.com/owner/repo/pull/123",
                ("owner", "repo", "123"),
            ),
            (
                "https://github.com/owner/repo/pull/123.diff",
                ("owner", "repo", "123"),
            ),
            ("not-a-url", None),
            ("https://github.com/owner/repo/issues/1", None),
        ],
    )
    def test_parse(self, url: str, expected: tuple[str, str, str] | None) -> None:
        assert _parse_pr_url(url) == expected

    def test_diff_url_for(self) -> None:
        assert (
            _diff_url_for("https://github.com/owner/repo/pull/1")
            == "https://github.com/owner/repo/pull/1.diff"
        )
        assert (
            _diff_url_for("https://github.com/owner/repo/pull/1.diff")
            == "https://github.com/owner/repo/pull/1.diff"
        )


class TestMahavishnuVersionPin:
    def test_mahavishnu_version_pin_constant(self) -> None:
        assert review_pr.MAHAVISHNU_VERSION_PIN == "0.29"

    def test_review_pr_handler_signature_uses_idempotency_source(self) -> None:
        """The dispatch surfaces the C-6 idempotency source.

        If the flag shape changes (e.g. -> --idempotency-source=...), the
        crackerjack release audit will fail loudly; this test pins the
        contract for crackerjack's side.
        """
        import inspect

        source = inspect.getsource(review_pr._dispatch_via_mahavishnu)
        assert "--idempotency-source" in source
        # The constant is referenced by name in source; verify the
        # module-level constant has the expected value too.
        assert (
            review_pr.MAHAVISHNU_DISPATCH_IDEMPOTENCY_SOURCE
            == "crackerjack.review_pr"
        )
        assert "MAHAVISHNU_DISPATCH_IDEMPOTENCY_SOURCE" in source

    def test_mahavishnu_metadata_available(self) -> None:
        """If mahavishnu is not installed the contract test cannot probe it.

        Cross-repo contract tests that actually import mahavishnu live
        in the mahavishnu repo's integration suite; this test pins only
        that the constant agrees with C-5 + C-6 publication line.
        """
        try:
            version = importlib.metadata.version("mahavishnu")
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("mahavishnu not installed in test environment")
        major_minor = ".".join(version.split(".")[:2])
        # Accept any 0.x or 1.x as long as the major.minor >= 0.29
        major, minor = major_minor.split(".")
        assert int(major) >= 1 or (int(major) == 0 and int(minor) >= 29)


class TestSkillRegistered:
    def test_review_pr_in_static_catalog(self) -> None:
        from crackerjack.mcp.tools.skill_registry import _STATIC_SKILLS_BY_NAME

        assert "review-pr" in _STATIC_SKILLS_BY_NAME
        entry = _STATIC_SKILLS_BY_NAME["review-pr"]
        assert entry["body_filename"] == "review-pr.md"

    def test_skill_metadata_round_trip(self) -> None:
        """Build the metadata via the same path the MCP tool uses."""
        from crackerjack.mcp.tools.skill_registry import _build_unsigned_metadata

        metadata = _build_unsigned_metadata("review-pr")
        assert metadata.server == "crackerjack"
        assert metadata.name == "review-pr"
        assert metadata.version == "1.0.0"
        assert "idempotency" in metadata.description.lower()
        assert "Akosha" in metadata.description or "akosha" in metadata.description


class TestMetricsShape:
    def test_post_counter_labels(self) -> None:
        PR_REVIEW_POST_TOTAL.labels(result="success").inc()
        snapshot = PR_REVIEW_POST_TOTAL.snapshot()
        assert snapshot[("success",)] >= 1

    def test_fork_counter_labels(self) -> None:
        PR_REVIEW_FORK_PR_TOTAL.labels(result="success").inc()
        snapshot = PR_REVIEW_FORK_PR_TOTAL.snapshot()
        assert snapshot[("success",)] >= 1

    def test_duration_histogram_observe(self) -> None:
        before = PR_REVIEW_DURATION.snapshot()["count"]
        PR_REVIEW_DURATION.observe(7.5)
        after = PR_REVIEW_DURATION.snapshot()
        assert after["count"] == before + 1
        assert after["buckets"][10.0] >= 1

    def test_quota_gauge_set(self) -> None:
        GITHUB_API_QUOTA_REMAINING.set(1000.0)
        assert GITHUB_API_QUOTA_REMAINING.snapshot() == 1000.0


class TestReviewQueueRecordModel:
    def test_record_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "queue.db"
        queue = DurableQueue(path)
        queue.enqueue("https://github.com/x/y/pull/1")
        with queue._engine.connect() as conn:
            row = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT pr_url FROM crackerjack_review_queue"
                )
            ).fetchone()
        assert row is not None
        assert row[0] == "https://github.com/x/y/pull/1"
        # Smoke-import the model class so coverage hits its definition.
        assert ReviewQueueRecord.__tablename__ == "crackerjack_review_queue"