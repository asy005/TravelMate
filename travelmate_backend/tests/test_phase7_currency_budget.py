"""
Tests for Phase 7 — Currency Conversion & Advanced Budget Optimization.

Verifies:
1. Currency conversion service with real-time and mock provider tests.
2. Handling of invalid currencies, invalid amounts, and error guards.
3. Cache behavior (fresh hit within TTL, refetch on expiration).
4. Stale cache fallback during provider timeouts/failures (transparent warning, is_stale=True, never claiming live).
5. Error guard when providers fail and no cache exists (never invents exchange rates).
6. Budget conversion preserves original INR amounts while computing converted breakdown, totals, and per-day/per-traveler rates.
7. Advanced budget optimizer using Linear Programming (scipy.optimize.linprog) respecting constraints, floors, caps, and exact total sum.
8. Safe analytical fallback when solver is unavailable or fails.
9. All budget outputs include planning disclaimer and price_guarantee=False (never presenting estimates as confirmed booking prices).
10. API endpoints for currency routes (/currency/supported, /currency/rates, /currency/convert, /currency/convert-budget).
"""
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.currency_service import (
    SUPPORTED_CURRENCIES,
    CurrencyServiceError,
    _cache,
    get_supported_currencies,
    get_exchange_rates,
    convert_amount,
    convert_budget_data,
    DISCLAIMER_TEXT,
)
from app.services.budget_optimizer import (
    is_solver_available,
    solve_flexible_budget_lp,
    solve_flexible_budget_analytical,
    allocate_budget,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_currency_cache():
    """Ensure cache is reset before and after each test."""
    _cache.clear()
    yield
    _cache.clear()


# ============================================================================
# 1. Currency Conversion Service Tests
# ============================================================================

class TestCurrencyService:
    def test_supported_currencies_structure(self):
        currencies = get_supported_currencies()
        assert len(currencies) >= 10
        codes = {c["code"] for c in currencies}
        assert "INR" in codes
        assert "USD" in codes
        assert "EUR" in codes
        assert "GBP" in codes
        assert "AED" in codes

        for c in currencies:
            assert "symbol" in c and len(c["symbol"]) > 0
            assert "name" in c and len(c["name"]) > 0

    def test_convert_amount_inr_to_inr(self):
        res = convert_amount(5000.0, "INR")
        assert res["original_amount"] == 5000.0
        assert res["converted_amount"] == 5000.0
        assert res["rate"] == 1.0
        assert res["target_currency"] == "INR"
        assert res["symbol"] == "₹"
        assert res["is_stale"] is False
        assert res["disclaimer"] == DISCLAIMER_TEXT
        assert res["price_guarantee"] is False

    def test_convert_amount_with_mocked_rate(self):
        mock_rates = {
            "rates": {"INR": 1.0, "USD": 0.012, "EUR": 0.011},
            "timestamp": "2026-10-26 12:00:00 UTC",
            "source": "MockProvider",
        }
        with patch("app.services.currency_service._fetch_from_primary", return_value=mock_rates):
            res = convert_amount(10000.0, "USD")
            assert res["original_amount"] == 10000.0
            assert res["converted_amount"] == 120.0
            assert res["rate"] == 0.012
            assert res["symbol"] == "$"
            assert res["target_currency"] == "USD"
            assert res["is_stale"] is False
            assert res["disclaimer"] == DISCLAIMER_TEXT

    def test_convert_amount_unsupported_currency_raises(self):
        with pytest.raises(CurrencyServiceError) as exc_info:
            convert_amount(100.0, "XYZ_FAKE")
        assert "Unsupported currency" in str(exc_info.value)

    def test_convert_amount_invalid_inputs(self):
        with pytest.raises(CurrencyServiceError):
            convert_amount(None, "USD")

        with pytest.raises(CurrencyServiceError):
            convert_amount("not-a-number", "USD")

    def test_cache_fresh_hit_bypasses_network(self):
        _cache.set({"INR": 1.0, "USD": 0.012}, "2026-10-26 10:00:00 UTC", "CachedSource")
        with patch("app.services.currency_service._fetch_from_primary") as mock_fetch:
            rates_info = get_exchange_rates(force_refresh=False)
            assert mock_fetch.call_count == 0
            assert rates_info["rates"]["USD"] == 0.012
            assert rates_info["source"] == "CachedSource"
            assert rates_info["is_stale"] is False

    def test_cache_ttl_expiration_triggers_refetch(self):
        _cache.set({"INR": 1.0, "USD": 0.010}, "2026-10-26 08:00:00 UTC", "OldSource")
        # Manually backdate fetched_at
        _cache.fetched_at = time.time() - 7200  # 2 hours ago (> 1 hour TTL)

        fresh_rates = {
            "rates": {"INR": 1.0, "USD": 0.011},
            "timestamp": "2026-10-26 10:00:00 UTC",
            "source": "FreshSource",
        }
        with patch("app.services.currency_service._fetch_from_primary", return_value=fresh_rates) as mock_fetch:
            rates_info = get_exchange_rates()
            assert mock_fetch.call_count == 1
            assert rates_info["rates"]["USD"] == 0.011
            assert rates_info["source"] == "FreshSource"
            assert rates_info["is_stale"] is False

    def test_provider_timeout_with_stale_cache_fallback(self):
        """When providers timeout or fail, stale cache is returned with is_stale=True and warning."""
        _cache.set({"INR": 1.0, "USD": 0.0105}, "2026-10-25 12:00:00 UTC", "PriorSource")
        _cache.fetched_at = time.time() - 86400  # 1 day old

        with patch("app.services.currency_service._fetch_from_primary", side_effect=Exception("Connection timeout")), \
             patch("app.services.currency_service._fetch_from_fallback", side_effect=Exception("Gateway unreachable")):
            rates_info = get_exchange_rates()

            assert rates_info["is_stale"] is True
            assert rates_info["stale_warning"] is not None
            assert "Live exchange rates temporarily unavailable" in rates_info["stale_warning"]
            assert rates_info["rates"]["USD"] == 0.0105
            assert rates_info["source"] == "PriorSource"

    def test_provider_failure_without_cache_never_invents_rates(self):
        """Never invent exchange rates when both providers fail and no cache exists."""
        _cache.clear()
        with patch("app.services.currency_service._fetch_from_primary", side_effect=Exception("Connection refused")), \
             patch("app.services.currency_service._fetch_from_fallback", side_effect=Exception("Host not found")):
            with pytest.raises(CurrencyServiceError) as exc_info:
                get_exchange_rates()
            assert "Exchange rate service unavailable" in str(exc_info.value)

    def test_convert_budget_data_preserves_original_inr(self):
        mock_budget = {
            "total_budget": 30000,
            "estimated_total": 29500,
            "remaining_budget": 500,
            "cost_per_traveler": 14750,
            "cost_per_day": 5900,
            "breakdown": {
                "hotel": 12000,
                "transportation": 6000,
                "food": 6000,
                "activities": 3500,
                "miscellaneous": 2000,
            },
            "status": "Within Budget",
        }
        mock_rates = {
            "rates": {"INR": 1.0, "USD": 0.012},
            "timestamp": "2026-10-26 12:00:00 UTC",
            "source": "MockProvider",
        }
        with patch("app.services.currency_service._fetch_from_primary", return_value=mock_rates):
            converted = convert_budget_data(mock_budget, "USD")

            assert converted["currency"] == "USD"
            assert converted["currency_symbol"] == "$"
            assert converted["exchange_rate"] == 0.012
            assert converted["converted_total_budget"] == 360.0  # 30000 * 0.012
            assert converted["converted_estimated_total"] == 354.0  # 29500 * 0.012
            assert converted["converted_remaining_budget"] == 6.0  # 500 * 0.012
            assert converted["converted_breakdown"]["hotel"] == 144.0  # 12000 * 0.012

            # Original INR numbers must be strictly preserved
            assert "original_inr" in converted
            assert converted["original_inr"]["total_budget"] == 30000
            assert converted["original_inr"]["estimated_total"] == 29500
            assert converted["original_inr"]["breakdown"]["hotel"] == 12000

            # Disclaimer and non-guarantee
            assert converted["disclaimer"] == DISCLAIMER_TEXT
            assert converted["price_guarantee"] is False


# ============================================================================
# 2. Advanced Budget Optimization Tests
# ============================================================================

class TestAdvancedBudgetOptimization:
    def test_solver_availability_check(self):
        assert is_solver_available() is True

    def test_scipy_linprog_optimization_exact_sum_and_floors(self):
        available = 10000.0
        weights = {"transport": 0.25, "food": 0.35, "activities": 0.25, "misc": 0.15}
        floors = {"transport": 1000.0, "food": 2000.0, "activities": 800.0, "misc": 500.0}

        alloc = solve_flexible_budget_lp(available, weights, floors)
        assert alloc is not None
        assert sum(alloc.values()) == round(available)
        assert alloc["transport"] >= floors["transport"]
        assert alloc["food"] >= floors["food"]
        assert alloc["activities"] >= floors["activities"]
        assert alloc["misc"] >= floors["misc"]
        # Misc is capped to avoid artificial inflation
        assert alloc["misc"] <= max(floors["misc"], 0.20 * available) + 5

    def test_analytical_fallback_logic(self):
        available = 8500.0
        weights = {"transport": 0.25, "food": 0.35, "activities": 0.25, "misc": 0.15}
        floors = {"transport": 800.0, "food": 1500.0, "activities": 600.0, "misc": 400.0}

        alloc = solve_flexible_budget_analytical(available, weights, floors)
        assert sum(alloc.values()) == round(available)
        for cat in floors:
            assert alloc[cat] >= floors[cat]

    def test_allocate_budget_uses_lp_solver_when_available(self, db=None):
        """Standard allocate_budget run selects scipy_linprog and includes planning disclaimer."""
        slots = {"budget": "35000", "travel_style": "relaxing"}
        mock_db = MagicMock()
        budget = allocate_budget(
            mock_db,
            slots=slots,
            duration_days=4,
            travelers=2,
            destination_id=None,
        )
        assert budget["optimization_method"] in ("scipy_linprog", "floor_constrained")
        assert budget["disclaimer"] == DISCLAIMER_TEXT
        assert budget["price_guarantee"] is False
        assert budget["estimated_total"] == sum(budget["breakdown"].values())

    def test_allocate_budget_graceful_fallback_when_lp_fails(self):
        """When LP solver returns None or fails, analytical fallback preserves non-zero estimates."""
        slots = {"budget": "35000", "travel_style": "adventure"}
        mock_db = MagicMock()

        with patch("app.services.budget_optimizer.solve_flexible_budget_lp", return_value=None):
            budget = allocate_budget(
                mock_db,
                slots=slots,
                duration_days=4,
                travelers=2,
                destination_id=None,
            )
            assert budget["optimization_method"] == "analytical_fallback"
            assert budget["estimated_total"] == sum(budget["breakdown"].values())
            for val in budget["breakdown"].values():
                assert val > 0


# ============================================================================
# 3. Currency API Endpoint Tests
# ============================================================================

class TestCurrencyEndpoints:
    def test_get_supported_currencies_endpoint(self, client):
        res = client.get("/currency/supported")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        codes = [item["code"] for item in data]
        assert "INR" in codes
        assert "USD" in codes
        assert "EUR" in codes

    def test_get_rates_endpoint_success(self, client):
        mock_rates = {
            "rates": {"INR": 1.0, "USD": 0.0105, "EUR": 0.0098},
            "timestamp": "2026-10-26 12:00:00 UTC",
            "source": "MockProvider",
        }
        with patch("app.services.currency_service._fetch_from_primary", return_value=mock_rates):
            res = client.get("/currency/rates?base=INR")
            assert res.status_code == 200
            data = res.json()
            assert data["base"] == "INR"
            assert "USD" in data["rates"]
            assert data["is_stale"] is False

    def test_get_rates_invalid_base(self, client):
        res = client.get("/currency/rates?base=USD")
        assert res.status_code == 400
        assert "Only 'INR' is currently supported" in res.json()["detail"]

    def test_convert_single_amount_endpoint(self, client):
        mock_rates = {
            "rates": {"INR": 1.0, "USD": 0.012},
            "timestamp": "2026-10-26 12:00:00 UTC",
            "source": "MockProvider",
        }
        with patch("app.services.currency_service._fetch_from_primary", return_value=mock_rates):
            res = client.post("/currency/convert", json={"amount": 5000, "target_currency": "USD"})
            assert res.status_code == 200
            data = res.json()
            assert data["original_amount"] == 5000.0
            assert data["converted_amount"] == 60.0  # 5000 * 0.012
            assert data["symbol"] == "$"
            assert data["disclaimer"] == DISCLAIMER_TEXT

    def test_convert_single_amount_invalid_currency(self, client):
        res = client.post("/currency/convert", json={"amount": 5000, "target_currency": "INVALID_CURR"})
        assert res.status_code == 400
        assert "Unsupported currency" in res.json()["detail"]

    def test_convert_budget_endpoint(self, client):
        mock_budget = {
            "total_budget": 20000,
            "estimated_total": 20000,
            "remaining_budget": 0,
            "cost_per_traveler": 10000,
            "cost_per_day": 5000,
            "breakdown": {
                "hotel": 8000,
                "transportation": 4000,
                "food": 4000,
                "activities": 2500,
                "miscellaneous": 1500,
            },
            "status": "Within Budget",
        }
        mock_rates = {
            "rates": {"INR": 1.0, "EUR": 0.011},
            "timestamp": "2026-10-26 12:00:00 UTC",
            "source": "MockProvider",
        }
        with patch("app.services.currency_service._fetch_from_primary", return_value=mock_rates):
            res = client.post("/currency/convert-budget", json={"budget": mock_budget, "target_currency": "EUR"})
            assert res.status_code == 200
            data = res.json()
            assert data["currency"] == "EUR"
            assert data["currency_symbol"] == "€"
            assert data["converted_total_budget"] == 220.0  # 20000 * 0.011
            assert data["converted_breakdown"]["hotel"] == 88.0  # 8000 * 0.011
            assert data["original_inr"]["total_budget"] == 20000
            assert data["disclaimer"] == DISCLAIMER_TEXT
            assert data["price_guarantee"] is False
