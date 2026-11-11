
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "pipeline"))

import scheduler


def setup_window(monkeypatch):
    monkeypatch.setitem(scheduler.CFG, "maintenance_start", "02:00")
    monkeypatch.setitem(scheduler.CFG, "maintenance_end", "04:00")
    monkeypatch.setitem(scheduler.CFG, "retry_minutes", [15, 30])


def test_outside_maintenance_window(monkeypatch):
    setup_window(monkeypatch)

    active = Mock()
    monkeypatch.setattr(scheduler, "active_version", active)

    now = datetime(2026, 11, 10, 8, 0)
    scheduler.run_scheduled(now, scale=0)

    active.assert_not_called()


def test_retry_then_success(monkeypatch):
    setup_window(monkeypatch)

    monkeypatch.setattr(
        scheduler, "active_version",
        Mock(side_effect=["v1", "v2"])
    )

    run_update = Mock()
    monkeypatch.setattr(scheduler.update, "run_update", run_update)

    sleep = Mock()
    monkeypatch.setattr(scheduler.time, "sleep", sleep)

    health = Mock(return_value=True)
    monkeypatch.setattr(scheduler, "health_watch", health)

    now = datetime(2026, 11, 10, 2, 30)

    scheduler.run_scheduled(
        now, scale=1, fail_times=2
    )

    run_update.assert_called_once()
    assert [c.args[0] for c in sleep.call_args_list] == [900, 1800]
    health.assert_called_once_with(1)


def test_all_retries_fail(monkeypatch):
    setup_window(monkeypatch)

    monkeypatch.setattr(
        scheduler, "active_version", Mock(return_value="v1")
    )

    run_update = Mock()
    monkeypatch.setattr(scheduler.update, "run_update", run_update)

    sleep = Mock()
    monkeypatch.setattr(scheduler.time, "sleep", sleep)

    now = datetime(2026, 11, 10, 2, 30)

    scheduler.run_scheduled(
        now, scale=1, fail_times=3
    )

    run_update.assert_not_called()
    assert sleep.call_count == 2


def test_health_failure_triggers_rollback(monkeypatch):
    monkeypatch.setitem(scheduler.CFG, "health_check_minutes", 2)

    monkeypatch.setattr(
        scheduler, "healthy",
        Mock(side_effect=[True, False])
    )

    rollback = Mock()
    monkeypatch.setattr(scheduler.update, "rollback", rollback)

    monkeypatch.setattr(scheduler.time, "sleep", Mock())

    result = scheduler.health_watch(scale=0)

    assert result is False
    rollback.assert_called_once()


def test_successful_deployment_without_retry(monkeypatch):
    setup_window(monkeypatch)

    monkeypatch.setattr(
        scheduler, "active_version",
        Mock(side_effect=["v1", "v2"])
    )

    run_update = Mock()
    monkeypatch.setattr(scheduler.update, "run_update", run_update)

    health = Mock(return_value=True)
    monkeypatch.setattr(scheduler, "health_watch", health)

    now = datetime(2026, 11, 10, 2, 30)

    scheduler.run_scheduled(now, scale=0)

    run_update.assert_called_once()
    health.assert_called_once_with(0)
