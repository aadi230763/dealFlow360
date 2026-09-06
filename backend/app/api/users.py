from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.models.user import Role, User
from app.schemas.user import UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    role: Role | None = Query(None),
    db: Session = Depends(get_db),
    # Scoped to ADMIN/SALES_MANAGER/FINANCE -- this exists so account ownership can be
    # assigned to a rep, and so Finance can check whether they're the sole holder of
    # their role for the self-approval exception, not as a general internal directory.
    _: User = Depends(require_role(Role.ADMIN, Role.SALES_MANAGER, Role.FINANCE)),
) -> list[User]:
    q = db.query(User)
    if role is not None:
        q = q.filter(User.role == role)
    return q.order_by(User.name).all()
