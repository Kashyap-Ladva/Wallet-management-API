from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.debt import (
    DebtCreate,
    DebtRepaymentCreate,
    DebtRepaymentResponse,
    DebtResponse,
    DebtUpdate,
)
from app.services import debt_service

router = APIRouter(prefix="/debts", tags=["debts"])


@router.post("", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
def create_debt(
    payload: DebtCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return debt_service.create_debt(db, current_user.id, payload.model_dump())


@router.get("", response_model=list[DebtResponse])
def list_debts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return debt_service.list_debts(db, current_user.id)


@router.post(
    "/{debt_id}/repayments",
    response_model=DebtRepaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_debt_repayment(
    debt_id: int,
    payload: DebtRepaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        repayment = debt_service.record_repayment(
            db,
            current_user.id,
            debt_id,
            payload.model_dump(),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if repayment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
    return repayment


@router.put("/{debt_id}", response_model=DebtResponse)
def update_debt(
    debt_id: int,
    payload: DebtUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        debt = debt_service.update_debt(
            db,
            current_user.id,
            debt_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
    return debt


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debt(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not debt_service.delete_debt(db, current_user.id, debt_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
