from typing import Any

from pydantic import BaseModel


class SystemSettingOut(BaseModel):
    key: str
    value: Any
    model_config = {"from_attributes": True}


class SystemSettingUpsert(BaseModel):
    value: Any
