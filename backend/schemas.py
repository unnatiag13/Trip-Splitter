from typing import List, Optional
from pydantic import BaseModel, Field, validator


class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=255)

    @validator("email")
    def validate_email_basic(cls, v: str) -> str:
        val = v.strip().lower()
        if "@" not in val or "." not in val.split("@")[-1]:
            raise ValueError("Please provide a valid email address.")
        return val


class TripCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    destination: Optional[str] = Field(default=None, max_length=160)
    start_date: str = Field(..., min_length=8, max_length=20)
    end_date: Optional[str] = Field(default=None, max_length=20)
    currency: str = Field(default="INR", max_length=10)
    members: List[MemberCreate] = Field(..., min_items=2)


class TripUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    destination: Optional[str] = Field(default=None, max_length=160)
    start_date: Optional[str] = Field(default=None, min_length=8, max_length=20)
    end_date: Optional[str] = Field(default=None, max_length=20)


class ParticipantInput(BaseModel):
    member_id: int
    share_paise: Optional[int] = Field(default=None, ge=0)
    percentage: Optional[float] = Field(default=None, ge=0, le=100)
    percentage_bps: Optional[int] = Field(default=None, ge=0, le=10000)


class ExpenseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    amount_paise: int = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=60)
    expense_date: str = Field(..., min_length=8, max_length=20)
    payer_id: int
    split_method: str = Field(..., regex="^(equal|custom|percentage)$")
    participants: List[ParticipantInput] = Field(..., min_items=1)
    notes: Optional[str] = Field(default=None, max_length=500)


class ExpenseUpdate(ExpenseCreate):
    pass
