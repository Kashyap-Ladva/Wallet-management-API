import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limit import rate_limit_write
from app.database import get_db
from app.jobs.excel_import import process_excel_import_task
from app.models import ImportJob, MWallet, SWallet, User
from app.routers.tasks import record_task_ownership
from app.schema.celery_tasks import AsyncImportCreatedResponse, ImportJobStatusResponse
from app.services import cache_service, import_service, wallet_service

router = APIRouter(prefix="/imports", tags=["imports"])


def _resolve_super_wallet(
    db: Session,
    current_user: User,
    super_wallet_id: int | None = None,
    mini_wallet_id: int | None = None,
) -> SWallet:
    if super_wallet_id is not None:
        super_wallet = db.get(SWallet, super_wallet_id)
        if super_wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super wallet not found")
        if super_wallet.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return super_wallet

    if mini_wallet_id is not None:
        mini_wallet = db.get(MWallet, mini_wallet_id)
        if mini_wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
        if mini_wallet.super_wallet.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return mini_wallet.super_wallet

    if current_user.wallet is not None:
        return current_user.wallet

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super wallet not found")


async def _read_and_validate_upload(upload: UploadFile) -> tuple[bytes, str]:
    content = await upload.read(import_service.MAX_UPLOAD_BYTES + 1)
    try:
        digest = import_service.validate_upload(
            upload.filename,
            upload.content_type,
            content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return content, digest


@router.post("/excel/preview")
async def preview_excel_import(
    super_wallet_id: int | None = Form(default=None),
    mini_wallet_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    super_wallet = _resolve_super_wallet(db, current_user, super_wallet_id, mini_wallet_id)
    content, digest = await _read_and_validate_upload(file)
    try:
        preview = import_service.preview_excel_for_super_wallet(db, super_wallet, content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    preview["file_sha256"] = digest
    return preview


@router.post(
    "/excel/confirm",
    dependencies=[Depends(rate_limit_write)],
)
async def confirm_excel_import(
    super_wallet_id: int | None = Form(default=None),
    mini_wallet_id: int | None = Form(default=None),
    preview_sha256: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    super_wallet = _resolve_super_wallet(db, current_user, super_wallet_id, mini_wallet_id)
    content, digest = await _read_and_validate_upload(file)
    if digest != preview_sha256.lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The uploaded file differs from the file that was previewed",
        )
    try:
        preview = import_service.preview_excel_for_super_wallet(db, super_wallet, content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if preview["errors"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Correct all invalid rows before confirming", "rows": preview["errors"]},
        )
    if not preview["rows"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The workbook contains no transaction rows",
        )
    try:
        imported_count, errors = import_service.import_preview_rows_for_super_wallet(
            db,
            super_wallet,
            content,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Correct all invalid rows before confirming", "rows": errors},
        )
    if imported_count > 0:
        await cache_service.invalidate_user_analytics(current_user.id)
    return {
        "imported_count": imported_count,
        "duplicate_policy": "allow",
    }


@router.post(
    "/excel",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_write)],
)
async def import_validated_excel(
    super_wallet_id: int | None = Form(default=None),
    mini_wallet_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    super_wallet = _resolve_super_wallet(db, current_user, super_wallet_id, mini_wallet_id)
    content, _ = await _read_and_validate_upload(file)
    try:
        imported_count, errors = import_service.import_preview_rows_for_super_wallet(
            db,
            super_wallet,
            content,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Correct all invalid rows before importing", "rows": errors},
        )
    if imported_count > 0:
        await cache_service.invalidate_user_analytics(current_user.id)
    return {
        "imported_count": imported_count,
        "duplicate_policy": "allow",
    }


@router.post(
    "/async",
    response_model=AsyncImportCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit_write)],
)
@router.post(
    "/excel/async",
    response_model=AsyncImportCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit_write)],
)
async def import_excel_async(
    super_wallet_id: int | None = Form(default=None),
    mini_wallet_id: int | None = Form(default=None),
    preview_sha256: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    super_wallet = _resolve_super_wallet(db, current_user, super_wallet_id, mini_wallet_id)
    content, digest = await _read_and_validate_upload(file)

    if preview_sha256 and digest != preview_sha256.lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The uploaded file differs from the file that was previewed",
        )

    # Stage file securely on shared volume
    storage_root = os.getenv("FILE_STORAGE_PATH", "app/data/proofs")
    base_dir = os.path.dirname(storage_root) if "proofs" in storage_root else storage_root
    imports_dir = os.path.join(base_dir, "imports")
    os.makedirs(imports_dir, exist_ok=True)

    job_id = uuid4().hex
    staged_filename = f"{job_id}.xlsx"
    staged_path = os.path.join(imports_dir, staged_filename)

    with open(staged_path, "wb") as f:
        f.write(content)

    # Create ImportJob record
    job = ImportJob(
        id=job_id,
        user_id=current_user.id,
        status="PENDING",
        filename=file.filename,
        file_sha256=digest,
    )
    db.add(job)
    db.commit()

    # Dispatch Celery background task
    task = process_excel_import_task.delay(
        import_job_id=job_id,
        super_wallet_id=super_wallet.id,
        user_id=current_user.id,
        file_path=staged_path,
        preview_sha256=digest,
    )

    job.task_id = task.id
    db.commit()

    # Record task ownership in Redis
    record_task_ownership(task.id, current_user.id)

    return AsyncImportCreatedResponse(
        import_id=job_id,
        task_id=task.id,
        status="PENDING",
        message="Excel import queued for background processing",
        file_sha256=digest,
    )


@router.get(
    "/{import_id}/status",
    response_model=ImportJobStatusResponse,
)
def get_import_status(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(ImportJob, import_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )

    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    return ImportJobStatusResponse(
        import_id=job.id,
        task_id=job.task_id,
        status=job.status,
        total_rows=job.total_rows,
        imported_count=job.imported_count,
        file_sha256=job.file_sha256,
        error_details=job.error_details,
        date_created=job.date_created,
        date_completed=job.date_completed,
    )

