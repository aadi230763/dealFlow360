from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.engine.ceilings import resolve_ceiling
from app.models.catalog import Category
from app.models.customer import CustomerTier
from app.models.pricing_config import CategoryTierCeiling
from app.models.user import Role, User
from app.schemas.pricing_config import CeilingCellOut, CeilingMatrixOut, CeilingUpsert

router = APIRouter(prefix="/api/ceilings", tags=["ceilings"])


@router.get("/matrix", response_model=CeilingMatrixOut)
def get_matrix(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> CeilingMatrixOut:
    tiers = db.query(CustomerTier).order_by(CustomerTier.rank).all()
    categories = db.query(Category).order_by(Category.name).all()
    overrides = {(o.tier_id, o.category_id): o.ceiling_pct for o in db.query(CategoryTierCeiling).all()}

    cells: list[CeilingCellOut] = []
    for tier in tiers:
        for category in categories:
            override = overrides.get((tier.id, category.id))
            resolved = resolve_ceiling(
                tier_base=tier.base_discount_ceiling_pct,
                category_default=category.default_discount_ceiling_pct,
                override=override,
            )
            cells.append(
                CeilingCellOut(
                    tier_id=tier.id,
                    tier_name=tier.name,
                    category_id=category.id,
                    category_name=category.name,
                    ceiling_pct=resolved,
                    is_override=override is not None,
                )
            )
    return CeilingMatrixOut(cells=cells)


@router.put("", response_model=CeilingCellOut)
def upsert_ceiling(
    body: CeilingUpsert, db: Session = Depends(get_db), user: User = Depends(require_role(Role.ADMIN))
) -> CeilingCellOut:
    existing = (
        db.query(CategoryTierCeiling)
        .filter(
            CategoryTierCeiling.tier_id == body.tier_id,
            CategoryTierCeiling.category_id == body.category_id,
        )
        .first()
    )
    if existing:
        existing.ceiling_pct = body.ceiling_pct
    else:
        import uuid

        existing = CategoryTierCeiling(id=uuid.uuid4(), **body.model_dump())
        db.add(existing)
    db.flush()
    log_event(
        db,
        entity_type="category_tier_ceiling",
        entity_id=f"{body.tier_id}:{body.category_id}",
        action="update",
        actor=user,
        payload=body.model_dump(mode="json"),
    )
    db.commit()

    tier = db.get(CustomerTier, body.tier_id)
    category = db.get(Category, body.category_id)
    return CeilingCellOut(
        tier_id=tier.id,
        tier_name=tier.name,
        category_id=category.id,
        category_name=category.name,
        ceiling_pct=existing.ceiling_pct,
        is_override=True,
    )
