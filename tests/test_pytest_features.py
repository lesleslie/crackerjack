"""Tests for pytest timeout and parallel execution features."""

import time

import pytest


def test_normal_execution() -> None:
    assert True


@pytest.mark.timeout(2)
def test_timeout_feature() -> None:
    time.sleep(1)
    assert True


@pytest.mark.xdist_group("group1")
def test_xdist_group1() -> None:
    assert True


@pytest.mark.xdist_group("group1")
def test_xdist_group1_second() -> None:
    assert True


@pytest.mark.xdist_group("group2")
def test_xdist_group2() -> None:
    assert True


def test_slow_but_not_hanging() -> None:
    time.sleep(12)
    assert True


@pytest.mark.skip(reason="This test intentionally hangs to test timeout feature")
def test_hanging() -> None:
    while True:
        time.sleep(1)
