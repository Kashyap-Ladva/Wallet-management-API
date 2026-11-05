from datetime import datetime, timezone
import hashlib
import logging
import os

from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.celery_app import celery_app
from app.database import get_task_db
from app.models import ImportJob, SWallet, utc_now
from app.services import cache_service, import_service

logger = logging.getLogger("app.jobs.excel_import")


def _cleanup_staged_file(file_path: str) -> None:
    """Safely remove staged import file from disk."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.debug("Cleaned up staged import file: %s", file_path)
    except Exception as exc:
        logger.warning("Failed to remove staged import file %s: %s", file_path, exc)


@celery_app.task(
    name="app.jobs.excel_import.process_excel_import_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    # Only retry on transient database connectivity failures; permanent validation errors never retry!
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
)
def process_excel_import_task(
    self,
    import_job_id: str,
    super_wallet_id: int,
    user_id: int,
    file_path: str,
    preview_sha256: str | None = None,
) -> dict:
    """
    Process an Excel transaction import asynchronously with atomic financial integrity.
    Maintains job lifecycle state (PENDING -> PROCESSING -> COMPLETED | FAILED).
    """
    logger.info(
        "Starting async Excel import: job_id=%s, super_wallet_id=%d, user_id=%d",
        import_job_id,
        super_wallet_id,
        user_id,
    )

    with get_task_db() as db:
        job = db.get(ImportJob, import_job_id)
        if not job:
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": f"Import job {import_job_id} not found"}

        # Transition status to PROCESSING
        job.status = "PROCESSING"
        db.commit()

        # Step 1: Read and verify staged file exists
        if not os.path.exists(file_path):
            job.status = "FAILED"
            job.error_details = {"detail": "Staged file not found on server"}
            job.date_completed = utc_now()
            db.commit()
            return {"status": "FAILED", "error": "Staged file missing"}

        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except Exception as exc:
            job.status = "FAILED"
            job.error_details = {"detail": f"Failed to read file: {str(exc)}"}
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": str(exc)}

        # Step 2: Validate SHA-256 integrity
        actual_sha256 = hashlib.sha256(content).hexdigest()
        job.file_sha256 = actual_sha256
        if preview_sha256 and actual_sha256 != preview_sha256.lower():
            job.status = "FAILED"
            job.error_details = {
                "detail": "The uploaded file content differs from the previewed file SHA-256"
            }
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": "SHA-256 mismatch"}

        # Step 3: Resolve super wallet and verify ownership
        super_wallet = db.get(SWallet, super_wallet_id)
        if not super_wallet or super_wallet.user_id != user_id:
            job.status = "FAILED"
            job.error_details = {"detail": "Super wallet not found or unauthorized"}
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": "Unauthorized wallet"}

        # Step 4: Validate rows and compute available mini-wallet balances
        try:
            preview = import_service.preview_excel_for_super_wallet(db, super_wallet, content)
        except ValueError as exc:
            job.status = "FAILED"
            job.error_details = {"detail": str(exc)}
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": str(exc)}

        if preview.get("errors"):
            job.status = "FAILED"
            job.error_details = {"errors": preview["errors"]}
            job.total_rows = len(preview.get("rows", []))
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "errors": preview["errors"]}

        rows = preview.get("rows", [])
        if not rows:
            job.status = "FAILED"
            job.error_details = {"detail": "The workbook contains no transaction rows"}
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": "Empty workbook"}

        # Step 5: Atomic insertion of transactions
        job.total_rows = len(rows)
        try:
            imported_count = import_service.import_excel_rows_for_super_wallet(
                db,
                super_wallet,
                rows,
            )
            # import_excel_rows_for_super_wallet commits inside its implementation
            job.imported_count = imported_count
            job.status = "COMPLETED"
            job.date_completed = utc_now()
            db.commit()
        except ValueError as exc:
            db.rollback()
            job.status = "FAILED"
            job.error_details = {"detail": str(exc)}
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            return {"status": "FAILED", "error": str(exc)}
        except Exception as exc:
            db.rollback()
            job.status = "FAILED"
            job.error_details = {"detail": "Internal processing error during transaction commit"}
            job.date_completed = utc_now()
            db.commit()
            _cleanup_staged_file(file_path)
            raise exc

        # Step 6: Post-processing (Cache invalidation and cleanup)
        _cleanup_staged_file(file_path)
        try:
            cache_service.invalidate_user_analytics_sync(user_id)
        except Exception as exc:
            logger.warning("Cache invalidation error after import: %s", exc)

        logger.info(
            "Async Excel import completed successfully: job_id=%s, imported=%d",
            import_job_id,
            imported_count,
        )
        return {
            "status": "COMPLETED",
            "import_id": import_job_id,
            "imported_count": imported_count,
            "total_rows": len(rows),
        }

