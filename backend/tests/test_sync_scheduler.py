import threading
import time
from unittest.mock import patch

from app.services import sync_scheduler


def test_scheduler_job_skips_if_previous_run_still_in_progress():
    """
    _run_sync_job must not let a second invocation start while the first is
    still running (guards against one BackgroundScheduler tick overlapping
    a slow-running previous sync).
    """
    call_count = {"n": 0}
    release_event = threading.Event()

    def slow_sync(db, **kwargs):
        call_count["n"] += 1
        release_event.wait(timeout=2)
        return {"forms_checked": 0, "responses_found": 0, "synced": 0, "duplicates": 0, "rejected": 0, "failed": 0, "forms_with_errors": 0}

    with patch("app.services.sync_scheduler.registration_sync_orchestrator.sync_all_active_forms", side_effect=slow_sync), \
         patch("app.services.sync_scheduler.SessionLocal") as mock_session_local:
        mock_session_local.return_value.close = lambda: None

        t1 = threading.Thread(target=sync_scheduler._run_sync_job)
        t1.start()
        time.sleep(0.1)  # let the first job acquire the lock and start "running"

        # A second job attempting to run concurrently must skip immediately
        # rather than blocking or running in parallel.
        sync_scheduler._run_sync_job()

        release_event.set()
        t1.join(timeout=2)

    assert call_count["n"] == 1  # the second call skipped - never invoked sync


def test_start_scheduler_noop_when_disabled(monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_SYNC_SCHEDULER", "false")
    sync_scheduler._scheduler = None
    sync_scheduler.start_scheduler()
    assert sync_scheduler._scheduler is None
    config.get_settings.cache_clear()


def test_start_scheduler_noop_when_google_not_configured(monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_SYNC_SCHEDULER", "true")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")
    sync_scheduler._scheduler = None
    sync_scheduler.start_scheduler()
    assert sync_scheduler._scheduler is None
    config.get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_SYNC_SCHEDULER", "false")
    config.get_settings.cache_clear()
