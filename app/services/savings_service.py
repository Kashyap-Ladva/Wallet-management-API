from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SavingsGoal


def _get_goal(db: Session, user_id: int, goal_id: int) -> SavingsGoal | None:
    return db.scalar(
        select(SavingsGoal).where(
            SavingsGoal.id == goal_id,
            SavingsGoal.user_id == user_id,
        )
    )


def create_goal(db: Session, user_id: int, payload: dict) -> SavingsGoal:
    goal = SavingsGoal(user_id=user_id, **payload)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_goals(db: Session, user_id: int) -> list[SavingsGoal]:
    return list(
        db.scalars(
            select(SavingsGoal)
            .where(SavingsGoal.user_id == user_id)
            .order_by(SavingsGoal.id.desc())
        )
    )


def update_goal(
    db: Session,
    user_id: int,
    goal_id: int,
    updates: dict,
) -> SavingsGoal | None:
    goal = _get_goal(db, user_id, goal_id)
    if goal is None:
        return None
    for field, value in updates.items():
        if value is None and field != "target_date":
            continue
        if field == "name":
            value = value.strip()
        setattr(goal, field, value)
    if goal.current_amount >= goal.target_amount:
        goal.status = "completed"
    elif "target_amount" in updates and updates["target_amount"] is not None:
        goal.status = "active"
    db.commit()
    db.refresh(goal)
    return goal


def contribute(
    db: Session,
    user_id: int,
    goal_id: int,
    amount: Decimal,
    action: str,
) -> SavingsGoal | None:
    goal = _get_goal(db, user_id, goal_id)
    if goal is None:
        return None
    amount = Decimal(amount)
    if action == "withdraw":
        if amount > goal.current_amount:
            raise ValueError("Withdrawal exceeds the current saved amount")
        goal.current_amount -= amount
        if goal.current_amount < goal.target_amount:
            goal.status = "active"
    else:
        goal.current_amount += amount
        if goal.current_amount >= goal.target_amount:
            goal.status = "completed"
    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: Session, user_id: int, goal_id: int) -> bool:
    goal = _get_goal(db, user_id, goal_id)
    if goal is None:
        return False
    db.delete(goal)
    db.commit()
    return True
