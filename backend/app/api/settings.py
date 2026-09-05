from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.deps import get_current_user, get_db, require_role
from app.models.setting import SystemSetting
from app.models.user import Role, User
from app.schemas.setting import SystemSettingOut, SystemSettingUpsert

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SystemSettingOut])
def list_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SystemSetting]:
    return db.query(SystemSetting).order_by(SystemSetting.key).all()


@router.put("/{key}", response_model=SystemSettingOut)
def upsert_setting(
    key: str,
    body: SystemSettingUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
) -> SystemSetting:
    setting = db.get(SystemSetting, key)
    if setting is None:
        setting = SystemSetting(key=key, value=body.value)
        db.add(setting)
    else:
        setting.value = body.value
    db.flush()
    log_event(db, entity_type="system_setting", entity_id=key, action="update", actor=user, payload={"value": body.value})
    db.commit()
    return setting
