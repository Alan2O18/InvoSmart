"""
Tests for voucher payload schema validation.
Defense #3 (Draft/Strict split), #7 (date validation), #15 (amount limit).
"""
import pytest
from pydantic import ValidationError

from backend.models.voucher_payload import (
    VoucherFieldsDraft,
    VoucherFieldsStrict,
    VoucherImageStrict,
    VoucherLayoutPayloadDraft,
    VoucherLayoutPayloadStrict,
    VoucherPageDraft,
    VoucherPageStrict,
)


# ── Draft Schema (lenient) ──────────────────────────────────────────────────

class TestDraftSchema:
    def test_all_empty_fields_accepted(self):
        """Draft must accept completely empty fields (Defense #3, #40)."""
        fields = VoucherFieldsDraft()
        assert fields.voucherNo == ""
        assert fields.amount == ""
        assert fields.payDate == ""

    def test_empty_layout_accepted(self):
        payload = VoucherLayoutPayloadDraft(globalPrefix="", startIndex=1, pages=[])
        assert payload.pages == []

    def test_page_with_empty_fields_accepted(self):
        page = VoucherPageDraft(pageIndex=0, fields=VoucherFieldsDraft(), images=[])
        assert page.fields.amount == ""

    def test_invalid_date_in_draft_accepted(self):
        """Draft should accept invalid date strings (v29 §10.1.6)."""
        fields = VoucherFieldsDraft(payDate="not-a-date")
        assert fields.payDate == "not-a-date"

    def test_decimal_amount_in_draft_accepted(self):
        """Draft should accept decimal amounts."""
        fields = VoucherFieldsDraft(amount="100.5")
        assert fields.amount == "100.5"

    def test_excessive_amount_in_draft_accepted(self):
        """Draft should still accept legacy 7-digit amounts for migration UX."""
        fields = VoucherFieldsDraft(amount="99999999")
        assert fields.amount == "99999999"


# ── Strict Schema (rigorous) ───────────────────────────────────────────────

class TestStrictSchema:
    def test_valid_payload_accepted(self):
        fields = VoucherFieldsStrict(
            voucherNo="D-16-01",
            amount="4607",
            receiptCount="3",
            payDate="2024-11-28",
        )
        assert fields.amount == "4607"

    def test_empty_paydate_rejected(self):
        """v29 §10.1.6: payDate='' in Strict → 422."""
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="100",
                receiptCount="1",
                payDate="",
            )

    def test_invalid_paydate_rejected(self):
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="100",
                receiptCount="1",
                payDate="not-a-date",
            )

    def test_amount_1_million_rejected(self):
        """V0.0.7 six-cell policy: amount=1000000 -> invalid."""
        with pytest.raises(ValidationError) as exc_info:
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="1000000",
                receiptCount="1",
                payDate="2024-11-28",
            )
        assert "999999" in str(exc_info.value)

    def test_amount_999999_accepted(self):
        fields = VoucherFieldsStrict(
            voucherNo="D-16-01",
            amount="999999",
            receiptCount="1",
            payDate="2024-11-28",
        )
        assert fields.amount == "999999"

    def test_decimal_amount_rejected(self):
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="100.5",
                receiptCount="1",
                payDate="2024-11-28",
            )

    def test_non_digit_amount_rejected(self):
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="abc",
                receiptCount="1",
                payDate="2024-11-28",
            )

    def test_empty_voucherno_rejected(self):
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="",
                amount="100",
                receiptCount="1",
                payDate="2024-11-28",
            )

    def test_empty_receipt_count_rejected(self):
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="100",
                receiptCount="",
                payDate="2024-11-28",
            )

    def test_non_digit_receipt_count_rejected(self):
        with pytest.raises(ValidationError):
            VoucherFieldsStrict(
                voucherNo="D-16-01",
                amount="100",
                receiptCount="abc",
                payDate="2024-11-28",
            )

    def test_image_zero_width_rejected(self):
        with pytest.raises(ValidationError):
            VoucherImageStrict(jobId="j1", x=30, y=394, w=0, h=100)

    def test_image_zero_height_rejected(self):
        with pytest.raises(ValidationError):
            VoucherImageStrict(jobId="j1", x=30, y=394, w=100, h=0)

    def test_image_negative_dimensions_rejected(self):
        with pytest.raises(ValidationError):
            VoucherImageStrict(jobId="j1", x=30, y=394, w=-10, h=100)

    def test_image_empty_jobid_rejected(self):
        with pytest.raises(ValidationError):
            VoucherImageStrict(jobId="", x=30, y=394, w=100, h=100)

    def test_full_strict_layout_accepted(self):
        payload = VoucherLayoutPayloadStrict(
            globalPrefix="D-16",
            startIndex=1,
            pages=[
                VoucherPageStrict(
                    pageIndex=0,
                    fields=VoucherFieldsStrict(
                        voucherNo="D-16-01",
                        amount="100",
                        receiptCount="1",
                        payDate="2024-11-28",
                    ),
                    images=[VoucherImageStrict(jobId="j1", x=30, y=394, w=100, h=100)],
                )
            ],
        )
        assert len(payload.pages) == 1
