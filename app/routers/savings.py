from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.savings import (
    SavingsContributionCreate,
    SavingsGoalCreate,
    SavingsGoalResponse,
    SavingsGoalUpdate,
)
from app.services import savings_service

router = APIRouter(prefix="/savings", tags=["savings"])


@router.post("", response_model=SavingsGoalResponse, status_code=status.HTTP_201_CREATED)
def create_savings_goal(
    payload: SavingsGoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return savings_service.create_goal(db, current_user.id, payload.model_dump())


@router.get("", response_model=list[SavingsGoalResponse])
def list_savings_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return savings_service.list_goals(db, current_user.id)


@router.post(
    "/{goal_id}/contributions",
    response_model=SavingsGoalResponse,
)
def contribute_to_savings_goal(
    goal_id: int,
    payload: SavingsContributionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        goal = savings_service.contribute(
            db,
            current_user.id,
            goal_id,
            payload.amount,
            payload.action,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savings goal not found")
    return goal


@router.put("/{goal_id}", response_model=SavingsGoalResponse)
def update_savings_goal(
    goal_id: int,
    payload: SavingsGoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = savings_service.update_goal(
        db,
        current_user.id,
        goal_id,
        payload.model_dump(exclude_unset=True),
    )
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savings goal not found")
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_savings_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not savings_service.delete_goal(db, current_user.id, goal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savings goal not found")
