"""Unit tests for the dynamic referral model's field rules."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from labra.model.referral_model import build_referral_model


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr("labra.clock.today_utc", lambda: date(2026, 11, 1))


def test_duns_nine_digits_valid():
    M = build_referral_model([("customer_duns", False)])
    assert M(customer_duns="123456789").customer_duns == "123456789"


@pytest.mark.parametrize("bad", ["ABC", "12345678", "1234567890", "12345678a"])
def test_duns_rejects_non_nine_digits(bad):
    M = build_referral_model([("customer_duns", False)])
    with pytest.raises(ValidationError):
        M(customer_duns=bad)


def test_duns_optional_missing_ok():
    M = build_referral_model([("customer_duns", False)])
    assert M().model_dump(exclude_none=True) == {}


def test_website_and_country_rules():
    M = build_referral_model([("website", True), ("country", True)])
    ok = M(website="https://northwind.example", country="United States")
    assert ok.website == "https://northwind.example"
    with pytest.raises(ValidationError):
        M(website="northwind.example", country="United States")
    with pytest.raises(ValidationError):
        M(website="https://northwind.example", country="USA")


def test_revenue_coercion_and_positivity():
    M = build_referral_model([("expected_monthly_revenue", True)])
    assert M(expected_monthly_revenue="5000").expected_monthly_revenue == 5000
    with pytest.raises(ValidationError):
        M(expected_monthly_revenue="-10")


def test_close_date_today_or_later():
    M = build_referral_model([("target_close_date", True)])
    assert M(target_close_date="2026-11-01").target_close_date == "2026-11-01"
    with pytest.raises(ValidationError):
        M(target_close_date="2020-01-01")
