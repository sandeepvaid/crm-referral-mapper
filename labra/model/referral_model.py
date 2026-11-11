"""The referral and its validation rules.

The model is built dynamically from the template's field list, so a field added
later is validated from the same single list the template uses — there is no
second hardcoded field list that could drift.

Known fields (the six originals + customer_duns) carry specific rules below.
Any other field the list grows is validated generically: required => non-empty.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Optional
from urllib.parse import urlparse

from pydantic import BeforeValidator, create_model

from labra import clock

ALLOWED_COUNTRIES = {"United States", "India", "Germany", "United Kingdom"}
_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --- per-field validators (raise ValueError on bad input) --------------------

def _company_name(v: Any) -> str:
    s = str(v).strip()
    if not s or len(s) > 255:
        raise ValueError("company_name")
    return s


def _website(v: Any) -> str:
    s = str(v).strip()
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("website")
    return s


def _country(v: Any) -> str:
    s = str(v).strip()
    if s not in ALLOWED_COUNTRIES:
        raise ValueError("country")
    return s


def _revenue(v: Any) -> float | int:
    try:
        num = float(v)
    except (TypeError, ValueError):
        raise ValueError("expected_monthly_revenue")
    if num <= 0:
        raise ValueError("expected_monthly_revenue")
    return int(num) if num.is_integer() else num


def _close_date(v: Any) -> str:
    s = str(v).strip()
    try:
        parsed = date.fromisoformat(s)
    except ValueError:
        raise ValueError("target_close_date")
    if parsed < clock.today_utc():
        raise ValueError("target_close_date")
    return s


def _email(v: Any) -> str:
    s = str(v).strip()
    if not _EMAIL_RE.match(s):
        raise ValueError("primary_sales_rep_email")
    return s


def _duns(v: Any) -> str:
    s = str(v).strip()
    if len(s) != 9 or not s.isdigit():
        raise ValueError("customer_duns")
    return s


def _generic_required(v: Any) -> Any:
    s = str(v).strip()
    if not s:
        raise ValueError("generic")
    return v


VALIDATORS = {
    "company_name": _company_name,
    "website": _website,
    "country": _country,
    "expected_monthly_revenue": _revenue,
    "target_close_date": _close_date,
    "primary_sales_rep_email": _email,
    "customer_duns": _duns,
}


def _annotated(labra_field: str):
    fn = VALIDATORS.get(labra_field, _generic_required)
    return Annotated[Any, BeforeValidator(fn)]


def build_referral_model(field_specs: list[tuple[str, bool]]):
    """field_specs: (labra_field, required) in display order."""
    fields: dict[str, tuple] = {}
    for name, required in field_specs:
        ann = _annotated(name)
        fields[name] = (ann, ...) if required else (Optional[ann], None)
    return create_model("Referral", **fields)
