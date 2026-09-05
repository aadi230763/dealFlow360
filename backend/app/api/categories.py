import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.catalog import Category
from app.models.user import Role, User
from app.schemas.catalog import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Category]:
    return db.query(Category).order_by(Category.name).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> Category:
    category = Category(id=uuid.uuid4(), **body.model_dump())
    db.add(category)
    db.flush()
    log_event(db, entity_type="category", entity_id=str(category.id), action="create", actor=user, payload=body.model_dump(mode="json"))
    db.commit()
    return category


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.flush()
    log_event(db, entity_type="category", entity_id=str(category.id), action="update", actor=user, payload=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    log_event(db, entity_type="category", entity_id=str(category_id), action="delete", actor=user)
    db.commit()
