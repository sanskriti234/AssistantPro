"""
Automatic synchronization scheduler.

Runs registration_sync_orchestrator.sync_all_active_forms() on a timer
inside the FastAPI process, using APScheduler's BackgroundScheduler (a
single in-process thread - no Redis/Celery, per project instruction not to
introduce that infrastructure without a demonstrated need).

IMPORTANT - multi-worker deployments: if CoreSight runs with more than one
uvicorn/gunicorn worker process (e.g. `--workers 4`), each worker is a
separate Python process and would start its OWN scheduler if this were
enabled unconditionally, causing duplicate concurrent syncs. This is safe
regardless (google_response_id's UNIQUE constraint and the retry-safe
status model in registration_sync.py prevent duplicate students even under
concurrent syncs), but it wastes Google API quota. The recommended
production setup is either:
  (a) run with a single worker, or
  (b) run with ENABLE_SYNC_SCHEDULER=true on exactly one designated worker/
      process (e.g. a dedicated `python -m app.sync_worker` process - see
      that module for a one-shot cron-friendly alternative) and
      ENABLE_SYNC_SCHEDULER=false everywhere else.
This module does not attempt to auto-detect or coordinate across workers -
that coordination is a deployment-level decision, documented here rather
than silently guessed at.
"""

from __future__ import annotations

import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.services import registration_sync_orchestrator

logger = logging.getLogger("coresight.sync_scheduler")

_scheduler: BackgroundScheduler | None = None
_run_lock = threading.Lock()


def _run_sync_job() -> None:
    # Guards against a single BackgroundScheduler firing an overlapping run
    # if one sync takes longer than the configured interval - the next
    # scheduled tick is skipped rather than stacking up concurrent syncs.
    if not _run_lock.acquire(blocking=False):
        logger.info("REGISTRATION_SYNC_SKIPPED reason=previous_run_still_in_progress")
        return
    try:
        db = SessionLocal()
        try:
            summary = registration_sync_orchestrator.sync_all_active_forms(db)
            logger.info("REGISTRATION_SYNC_STARTED %s", summary)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - a scheduler job must never crash the app
        logger.exception("REGISTRATION_SYNC_FAILED unexpected error in scheduled sync")
    finally:
        _run_lock.release()


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()

    if not settings.enable_sync_scheduler:
        logger.info("Sync scheduler disabled (ENABLE_SYNC_SCHEDULER=false)")
        return
    if not settings.google_forms_configured:
        logger.warning("Sync scheduler enabled but Google Forms is not configured - not starting")
        return
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _run_sync_job,
        "interval",
        seconds=settings.google_form_sync_interval_seconds,
        id="registration_form_sync",
        max_instances=1,  # belt-and-suspenders alongside _run_lock
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Sync scheduler started (interval=%ss)", settings.google_form_sync_interval_seconds)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
