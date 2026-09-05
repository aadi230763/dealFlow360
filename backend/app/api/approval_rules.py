import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.approval_rule import ApprovalRule
from app.models.user import Role, User
from app.schemas.approval_rule import ApprovalRuleCreate, ApprovalRuleOut, ApprovalRuleUpdate

router = APIRouter(prefix="/api/approval-rules", tags=["approval-rules"])


@router.get("", response_model=list[ApprovalRuleOut])
def list_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ApprovalRule]:
    return db.query(ApprovalRule).order_by(ApprovalRule.sequence).all()


@router.post("", response_model=ApprovalRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    body: ApprovalRuleCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> ApprovalRule:
    rule = ApprovalRule(id=uuid.uuid4(), **body.model_dump())
    db.add(rule)
    db.flush()
    log_event(db, entity_type="approval_rule", entity_id=str(rule.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return rule


@router.put("/{rule_id}", response_model=ApprovalRuleOut)
def update_rule(
    rule_id: uuid.UUID,
    body: ApprovalRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> ApprovalRule:
    rule = db.get(ApprovalRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.flush()
    log_event(db, entity_type="approval_rule", entity_id=str(rule.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    rule = db.get(ApprovalRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    log_event(db, entity_type="approval_rule", entity_id=str(rule_id), action="delete", actor=user)
    db.commit()
