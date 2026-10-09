from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import MWallet, User
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])


def _owned_mini_wallet(
    db: Session,
    current_user: User,
    mini_wallet_id: int,
) -> MWallet:
    mini_wallet = db.get(MWallet, mini_wallet_id)
    if mini_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
    if mini_wallet.super_wallet.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return mini_wallet


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return content, digest


def _preview_payload(content: bytes, digest: str, mini_wallet: MWallet) -> dict:
    try:
        result = import_service.preview_excel(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    errors = result["errors"]
    available = mini_wallet.balance
    for row in result["rows"]:
        if row["type"] == "expense":
            if row["amount"] > available:
                errors.append(
                    {
                        "row": row["row_number"],
                        "errors": [
                            "expense exceeds the available mini-wallet balance"
                        ],
                    }
                )
            else:
                available -= row["amount"]
        else:
            available += row["amount"]
    return {
        "file_sha256": digest,
        "valid": not errors and bool(result["rows"]),
        "rows": result["rows"],
        "errors": errors,
        "duplicate_policy": (
            "Duplicate rows are imported as separate transactions; no automatic "
            "deduplication is performed."
        ),
    }


@router.post("/excel/preview")
async def preview_excel_import(
    mini_wallet_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = _owned_mini_wallet(db, current_user, mini_wallet_id)
    content, digest = await _read_and_validate_upload(file)
    return _preview_payload(content, digest, mini_wallet)


@router.post("/excel/confirm")
async def confirm_excel_import(
    mini_wallet_id: int = Form(...),
    preview_sha256: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = _owned_mini_wallet(db, current_user, mini_wallet_id)
    content, digest = await _read_and_validate_upload(file)
    if digest != preview_sha256.lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The uploaded file differs from the file that was previewed",
        )
    preview = _preview_payload(content, digest, mini_wallet)
    if preview["errors"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Correct all invalid rows before confirming", "rows": preview["errors"]},
        )
    if not preview["rows"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The workbook contains no transaction rows",
        )
    try:
        imported_count, errors = import_service.import_preview_rows(
            db,
            mini_wallet,
            content,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Correct all invalid rows before confirming", "rows": errors},
        )
    return {
        "imported_count": imported_count,
        "duplicate_policy": "allow",
    }


@router.post("/excel", status_code=status.HTTP_201_CREATED)
async def import_validated_excel(
    mini_wallet_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = _owned_mini_wallet(db, current_user, mini_wallet_id)
    content, _ = await _read_and_validate_upload(file)
    try:
        imported_count, errors = import_service.import_preview_rows(
            db,
            mini_wallet,
            content,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Correct all invalid rows before importing", "rows": errors},
        )
    return {
        "imported_count": imported_count,
        "duplicate_policy": "allow",
    }
