from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator


class VoucherImagePayload(BaseModel):
    jobId: str = ""
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0


class VoucherFieldsDraft(BaseModel):
    voucherNo: str = ""
    budgetItem: str = ""
    amount: str = ""
    purpose: str = ""
    receiptCount: str = ""
    payDate: str = ""
    isManuallyEdited: bool = False


class VoucherPageDraft(BaseModel):
    pageIndex: int = 0
    fields: VoucherFieldsDraft = Field(default_factory=VoucherFieldsDraft)
    images: List[VoucherImagePayload] = Field(default_factory=list)


class VoucherLayoutPayloadDraft(BaseModel):
    globalPrefix: str = ""
    startIndex: int = 1
    pages: List[VoucherPageDraft] = Field(default_factory=list)


class VoucherFieldsStrict(BaseModel):
    voucherNo: str = Field(min_length=1)
    budgetItem: str = ""
    amount: str = Field(min_length=1)
    purpose: str = ""
    receiptCount: str = Field(min_length=1)
    payDate: str = Field(min_length=1)
    isManuallyEdited: bool = False

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("amount must contain digits only")
        if int(value) > 999999:
            raise ValueError("amount must be <= 999999 (six-digit voucher limit)")
        return value

    @field_validator("receiptCount")
    @classmethod
    def validate_receipt_count(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("receiptCount must contain digits only")
        return value

    @field_validator("payDate")
    @classmethod
    def validate_paydate(cls, value: str) -> str:
        datetime.fromisoformat(value)
        return value


class VoucherImageStrict(BaseModel):
    jobId: str = Field(min_length=1)
    x: float
    y: float
    w: float
    h: float

    @field_validator("w", "h")
    @classmethod
    def validate_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("w/h must be > 0")
        return value


class VoucherPageStrict(BaseModel):
    pageIndex: int
    fields: VoucherFieldsStrict
    images: List[VoucherImageStrict] = Field(default_factory=list)


class VoucherLayoutPayloadStrict(BaseModel):
    globalPrefix: str = ""
    startIndex: int = 1
    pages: List[VoucherPageStrict] = Field(default_factory=list)
