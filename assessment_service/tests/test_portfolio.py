"""Tests for portfolio loading and market logic (portfolio.py)."""

from config import DEFAULT_PARTNERS_PATH
from portfolio import in_eu_market, iter_products, load_partners


def test_load_partners_counts():
    partners = load_partners(DEFAULT_PARTNERS_PATH)
    assert len(partners) == 22
    products = list(iter_products(partners))
    assert len(products) == 53


def test_in_eu_market_expands_eu():
    assert in_eu_market({"markets": ["EU"]}) is True
    assert in_eu_market({"markets": ["DE", "FR"]}) is True  # member states
    assert in_eu_market({"markets": ["UK"]}) is False
    assert in_eu_market({"markets": ["US"]}) is False
    assert in_eu_market({"markets": []}) is False
    assert in_eu_market({}) is False


def test_iter_products_yields_partner_product_pairs():
    partners = load_partners(DEFAULT_PARTNERS_PATH)
    partner, product = next(iter_products(partners))
    assert "partner_id" in partner
    assert "product_id" in product
