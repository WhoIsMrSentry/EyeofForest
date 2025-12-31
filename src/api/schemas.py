from pydantic import BaseModel
from typing import Optional


class ContactBase(BaseModel):
    full_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]


class ContactCreate(ContactBase):
    pass


class Contact(ContactBase):
    id: int
    # Pydantic v2 compatibility: prefer `model_config` with `from_attributes`.
    model_config = {"from_attributes": True}
