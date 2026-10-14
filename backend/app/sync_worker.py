"""
One-shot registration sync run, for deployments that prefer an external
cron/scheduled-task trigger over the in-process APScheduler
(app/services/sync_scheduler.py) - e.g. a platform that already runs
scheduled jobs, or a multi-worker deployment where only one designated
process/cron entry should trigger sync (see sync_scheduler.py's
multi-worker note).

Usage (e.g. as a cron entry running every 5 minutes):
    cd backend && python -m app.sync_worker
"""

import logging
import sys

from app.database.connection import SessionLocal
from app.services import registration_sync_orchestrator
from app.services.google_forms_service import GoogleFormsNotConfigured

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("coresight.sync_worker")


def main() -> int:
    db = SessionLocal()
    try:
        summary = registration_sync_orchestrator.sync_all_active_forms(db)
        logger.info("Sync complete: %s", summary)
        return 0
    except GoogleFormsNotConfigured as e:
        logger.error("Sync not run: %s", e)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
