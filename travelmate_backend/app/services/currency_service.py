"""
Currency Conversion Service — Phase 7
Provides real-time exchange rates, caching with stale fallback handling,
multi-currency conversions against INR base, and budget localization.

Never fabricates exchange rates or silently presents stale rates as live.
"""
import time
import logging
from typing import Dict, Any, List, Optional
import requests

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES: Dict[str, Dict[str, str]] = {
    "INR": {"name": "Indian Rupee", "symbol": "₹"},
    "USD": {"name": "US Dollar", "symbol": "$"},
    "EUR": {"name": "Euro", "symbol": "€"},
    "GBP": {"name": "British Pound", "symbol": "£"},
    "AED": {"name": "UAE Dirham", "symbol": "AED"},
    "SGD": {"name": "Singapore Dollar", "symbol": "S$"},
    "AUD": {"name": "Australian Dollar", "symbol": "A$"},
    "CAD": {"name": "Canadian Dollar", "symbol": "C$"},
    "JPY": {"name": "Japanese Yen", "symbol": "¥"},
    "THB": {"name": "Thai Baht", "symbol": "฿"},
    "MYR": {"name": "Malaysian Ringgit", "symbol": "RM"},
    "CHF": {"name": "Swiss Franc", "symbol": "CHF"},
    "CNY": {"name": "Chinese Yuan", "symbol": "¥"},
    "SAR": {"name": "Saudi Riyal", "symbol": "SAR"},
}

DISCLAIMER_TEXT = (
    "Estimates are for planning purposes only and not confirmed booking prices. "
    "Actual costs may vary based on seasonal rates, availability, and specific vendor selections."
)


class CurrencyServiceError(Exception):
    """Raised when currency conversion or rate retrieval cannot be completed."""
    pass


class CurrencyRateCache:
    """Thread-safe in-memory cache for exchange rates."""
    def __init__(self):
        self.rates: Dict[str, float] = {}
        self.timestamp: Optional[str] = None
        self.source: Optional[str] = None
        self.fetched_at: float = 0.0

    def is_fresh(self, ttl_seconds: int) -> bool:
        if not self.rates or not self.timestamp:
            return False
        return (time.time() - self.fetched_at) < ttl_seconds

    def has_any(self) -> bool:
        return bool(self.rates) and bool(self.timestamp)

    def set(self, rates: Dict[str, float], timestamp: str, source: str):
        self.rates = rates
        self.timestamp = timestamp
        self.source = source
        self.fetched_at = time.time()

    def clear(self):
        self.rates = {}
        self.timestamp = None
        self.source = None
        self.fetched_at = 0.0


_cache = CurrencyRateCache()


def get_supported_currencies() -> List[Dict[str, str]]:
    """Return all supported currency definitions."""
    return [
        {"code": code, "name": meta["name"], "symbol": meta["symbol"]}
        for code, meta in SUPPORTED_CURRENCIES.items()
    ]


def _fetch_from_primary(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Fetch rates from ExchangeRate-API (authenticated or open endpoint)."""
    if api_key:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/INR"
        source_name = "ExchangeRate-API (Key)"
    else:
        url = "https://open.er-api.com/v6/latest/INR"
        source_name = "ExchangeRate-API (Open)"

    response = requests.get(url, timeout=6)
    response.raise_for_status()
    data = response.json()

    if data.get("result") != "success":
        error_type = data.get("error-type", "Unknown error")
        raise CurrencyServiceError(f"Primary provider error: {error_type}")

    raw_rates = data.get("rates", {})
    timestamp = data.get("time_last_update_utc") or time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    filtered_rates: Dict[str, float] = {"INR": 1.0}
    for code in SUPPORTED_CURRENCIES:
        if code in raw_rates and isinstance(raw_rates[code], (int, float)):
            filtered_rates[code] = float(raw_rates[code])

    return {
        "rates": filtered_rates,
        "timestamp": str(timestamp),
        "source": source_name,
    }


def _fetch_from_fallback() -> Dict[str, Any]:
    """Fallback fetch from Frankfurter / ECB open rates."""
    url = "https://api.frankfurter.dev/v1/latest?base=INR"
    source_name = "Frankfurter (ECB)"

    response = requests.get(url, timeout=6)
    response.raise_for_status()
    data = response.json()

    raw_rates = data.get("rates", {})
    timestamp = data.get("date") or time.strftime("%Y-%m-%d", time.gmtime())

    filtered_rates: Dict[str, float] = {"INR": 1.0}
    for code in SUPPORTED_CURRENCIES:
        if code == "INR":
            filtered_rates[code] = 1.0
        elif code in raw_rates and isinstance(raw_rates[code], (int, float)):
            filtered_rates[code] = float(raw_rates[code])

    return {
        "rates": filtered_rates,
        "timestamp": f"{timestamp} (Frankfurter)",
        "source": source_name,
    }


def get_exchange_rates(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get exchange rates for base INR.
    Returns:
        {
            "base": "INR",
            "rates": {"USD": 0.0105, ...},
            "timestamp": "Mon, 26 Oct 2026 00:02:31 +0000",
            "source": "ExchangeRate-API (Open)",
            "is_stale": False,
            "stale_warning": None,
            "supported_currencies": [...]
        }
    """
    ttl = getattr(settings, "EXCHANGE_RATE_CACHE_TTL_SECONDS", 3600)
    api_key = getattr(settings, "EXCHANGE_RATE_API_KEY", "") or None

    # Check fresh cache
    if not force_refresh and _cache.is_fresh(ttl):
        return {
            "base": "INR",
            "rates": dict(_cache.rates),
            "timestamp": _cache.timestamp,
            "source": _cache.source,
            "is_stale": False,
            "stale_warning": None,
            "supported_currencies": get_supported_currencies(),
        }

    # Try fetching fresh rates from primary then fallback
    last_error: Optional[Exception] = None
    fetched: Optional[Dict[str, Any]] = None

    try:
        fetched = _fetch_from_primary(api_key=api_key)
    except Exception as exc:
        logger.warning("Primary exchange-rate fetch failed: %s. Trying fallback...", exc)
        last_error = exc
        try:
            fetched = _fetch_from_fallback()
        except Exception as exc_fb:
            logger.warning("Fallback exchange-rate fetch failed: %s", exc_fb)
            last_error = exc_fb

    if fetched:
        _cache.set(fetched["rates"], fetched["timestamp"], fetched["source"])
        return {
            "base": "INR",
            "rates": dict(fetched["rates"]),
            "timestamp": fetched["timestamp"],
            "source": fetched["source"],
            "is_stale": False,
            "stale_warning": None,
            "supported_currencies": get_supported_currencies(),
        }

    # Both failed: Handle stale cache or error transparently
    if _cache.has_any():
        warning_msg = (
            f"Live exchange rates temporarily unavailable ({last_error}). "
            f"Using cached rates from {_cache.timestamp} ({_cache.source})."
        )
        logger.warning(warning_msg)
        return {
            "base": "INR",
            "rates": dict(_cache.rates),
            "timestamp": _cache.timestamp,
            "source": _cache.source,
            "is_stale": True,
            "stale_warning": warning_msg,
            "supported_currencies": get_supported_currencies(),
        }

    # No cache and no network
    raise CurrencyServiceError(
        f"Exchange rate service unavailable. Live providers could not be reached ({last_error}) "
        "and no cached rates are available."
    )


def convert_amount(amount_inr: float, target_currency: str) -> Dict[str, Any]:
    """Convert an amount from INR to a target currency."""
    target_currency = (target_currency or "").strip().upper()
    if target_currency not in SUPPORTED_CURRENCIES:
        raise CurrencyServiceError(
            f"Unsupported currency '{target_currency}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_CURRENCIES.keys()))}"
        )

    if amount_inr is None:
        raise CurrencyServiceError("Amount to convert cannot be None.")

    try:
        amount_inr = float(amount_inr)
    except (TypeError, ValueError):
        raise CurrencyServiceError(f"Invalid amount '{amount_inr}'.")

    if target_currency == "INR":
        return {
            "original_amount": round(amount_inr, 2),
            "original_currency": "INR",
            "converted_amount": round(amount_inr, 2),
            "target_currency": "INR",
            "symbol": "₹",
            "rate": 1.0,
            "rate_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "source": "Base Currency",
            "is_stale": False,
            "stale_warning": None,
            "disclaimer": DISCLAIMER_TEXT,
            "price_guarantee": False,
        }

    rates_info = get_exchange_rates()
    rates = rates_info["rates"]

    if target_currency not in rates:
        raise CurrencyServiceError(
            f"Rate for '{target_currency}' is currently unavailable from {rates_info['source']}."
        )

    rate = rates[target_currency]
    converted = round(amount_inr * rate, 2)
    symbol = SUPPORTED_CURRENCIES[target_currency]["symbol"]

    return {
        "original_amount": round(amount_inr, 2),
        "original_currency": "INR",
        "converted_amount": converted,
        "target_currency": target_currency,
        "symbol": symbol,
        "rate": rate,
        "rate_timestamp": rates_info["timestamp"],
        "source": rates_info["source"],
        "is_stale": rates_info["is_stale"],
        "stale_warning": rates_info.get("stale_warning"),
        "disclaimer": DISCLAIMER_TEXT,
        "price_guarantee": False,
    }


def convert_budget_data(budget: Dict[str, Any], target_currency: str) -> Dict[str, Any]:
    """
    Take a budget dictionary (output from allocate_budget) and augment it
    with converted figures in the target currency while keeping all original
    INR values completely preserved and visible.
    """
    if not isinstance(budget, dict):
        raise CurrencyServiceError("Invalid budget data format.")

    target_currency = (target_currency or "INR").strip().upper()
    if target_currency not in SUPPORTED_CURRENCIES:
        raise CurrencyServiceError(
            f"Unsupported currency '{target_currency}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_CURRENCIES.keys()))}"
        )

    result = dict(budget)
    # Always include the non-guarantee disclaimer and price guarantee flag
    result["disclaimer"] = DISCLAIMER_TEXT
    result["price_guarantee"] = False

    if target_currency == "INR":
        result["currency"] = "INR"
        result["currency_symbol"] = "₹"
        result["rate"] = 1.0
        result["is_stale_rate"] = False
        result["rate_source"] = "Base Currency (INR)"
        result["rate_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        return result

    rates_info = get_exchange_rates()
    rates = rates_info["rates"]
    if target_currency not in rates:
        raise CurrencyServiceError(f"Rate for '{target_currency}' not available.")

    rate = rates[target_currency]
    symbol = SUPPORTED_CURRENCIES[target_currency]["symbol"]

    # Preserve original INR numbers in a distinct nested structure for unambiguous access
    result["original_inr"] = {
        "total_budget": budget.get("total_budget", 0),
        "estimated_total": budget.get("estimated_total", 0),
        "remaining_budget": budget.get("remaining_budget", 0),
        "cost_per_traveler": budget.get("cost_per_traveler", 0),
        "cost_per_day": budget.get("cost_per_day", 0),
        "breakdown": dict(budget.get("breakdown") or {}),
    }

    # Converted breakdown
    orig_breakdown = budget.get("breakdown") or {}
    converted_breakdown = {
        k: round(float(v) * rate, 2)
        for k, v in orig_breakdown.items()
    }

    result["currency"] = target_currency
    result["currency_symbol"] = symbol
    result["base_currency"] = "INR"
    result["exchange_rate"] = rate
    result["rate_timestamp"] = rates_info["timestamp"]
    result["rate_source"] = rates_info["source"]
    result["is_stale_rate"] = rates_info["is_stale"]
    result["stale_warning"] = rates_info.get("stale_warning")

    result["converted_breakdown"] = converted_breakdown
    result["converted_total_budget"] = round(float(budget.get("total_budget", 0)) * rate, 2)
    result["converted_estimated_total"] = round(float(budget.get("estimated_total", 0)) * rate, 2)
    result["converted_remaining_budget"] = round(float(budget.get("remaining_budget", 0)) * rate, 2)
    result["converted_cost_per_traveler"] = round(float(budget.get("cost_per_traveler", 0)) * rate, 2)
    result["converted_cost_per_day"] = round(float(budget.get("cost_per_day", 0)) * rate, 2)

    return result
