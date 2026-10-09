from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.recurring_payment import (
    RecurringPaymentCreate,
    RecurringPaymentResponse,
    RecurringPaymentUpdate,
)
from app.services import recurring_payment_service

router = APIRouter(prefix="/recurring-payments", tags=["recurring payments"])


@router.post(
    "",
    response_model=RecurringPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recurring_payment(
    payload: RecurringPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.frequency != "monthly":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only monthly recurring payments are supported",
        )
    return recurring_payment_service.create_payment(
        db,
        current_user.id,
        payload.model_dump(),
    )


@router.get("", response_model=list[RecurringPaymentResponse])
def list_recurring_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return recurring_payment_service.list_payments(db, current_user.id)


@router.put("/{payment_id}", response_model=RecurringPaymentResponse)
def update_recurring_payment(
    payment_id: int,
    payload: RecurringPaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payment = recurring_payment_service.update_payment(
            db,
            current_user.id,
            payment_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring payment not found")
    return payment


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not recurring_payment_service.delete_payment(db, current_user.id, payment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring payment not found")
