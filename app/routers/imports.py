from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import MWallet, SWallet, User
from app.services import import_service, wallet_service

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


@router.post("/excel/confirm")
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
    return {
        "imported_count": imported_count,
        "duplicate_policy": "allow",
    }


@router.post("/excel", status_code=status.HTTP_201_CREATED)
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
    return {
        "imported_count": imported_count,
        "duplicate_policy": "allow",
    }
