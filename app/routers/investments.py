from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.investment import (
    InvestmentCreate,
    InvestmentResponse,
    InvestmentUpdate,
)
from app.services import investment_service

router = APIRouter(prefix="/investments", tags=["investments"])


@router.post("", response_model=InvestmentResponse, status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: InvestmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return investment_service.create_investment(
        db,
        current_user.id,
        payload.model_dump(),
    )


@router.get("", response_model=list[InvestmentResponse])
def list_investments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return investment_service.list_investments(db, current_user.id)


@router.get("/{investment_id}", response_model=InvestmentResponse)
def get_investment(
    investment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investment = investment_service.get_investment(
        db,
        current_user.id,
        investment_id,
    )
    if investment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")
    return investment


@router.put("/{investment_id}", response_model=InvestmentResponse)
def update_investment(
    investment_id: int,
    payload: InvestmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investment = investment_service.update_investment(
        db,
        current_user.id,
        investment_id,
        payload.model_dump(exclude_unset=True),
    )
    if investment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")
    return investment


@router.delete("/{investment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment(
    investment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not investment_service.delete_investment(db, current_user.id, investment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")
