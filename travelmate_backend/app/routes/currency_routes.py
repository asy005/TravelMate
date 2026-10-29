"""
Currency API Routes — Phase 7
Exposes supported currencies, live/cached exchange rates,
single amount conversions, and budget multi-currency conversions.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.currency_service import (
    get_supported_currencies,
    get_exchange_rates,
    convert_amount,
    convert_budget_data,
    CurrencyServiceError,
    SUPPORTED_CURRENCIES,
)

router = APIRouter(prefix="/currency", tags=["currency"])


class ConvertRequest(BaseModel):
    amount: float = Field(..., description="Amount in base currency (INR)")
    target_currency: str = Field(..., description="Target currency code (e.g. USD, EUR, GBP)")
    base_currency: Optional[str] = Field("INR", description="Base currency code, default INR")


class ConvertBudgetRequest(BaseModel):
    budget: Dict[str, Any] = Field(..., description="Budget breakdown object from budget optimizer")
    target_currency: str = Field(..., description="Target currency code (e.g. USD, EUR, GBP)")


@router.get("/supported")
def supported_currencies():
    """Return all supported currencies with symbols and names."""
    return get_supported_currencies()


@router.get("/rates")
def exchange_rates(
    base: str = Query("INR", description="Base currency (currently INR)"),
    force_refresh: bool = Query(False, description="Bypass cache and fetch latest provider rates"),
):
    """
    Get exchange rates against INR.
    Returns rates, timestamp, provider source, and stale status.
    """
    base = (base or "INR").strip().upper()
    if base != "INR":
        raise HTTPException(status_code=400, detail="Only 'INR' is currently supported as base currency.")

    try:
        return get_exchange_rates(force_refresh=force_refresh)
    except CurrencyServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving rates: {exc}")


@router.post("/convert")
def convert_single_amount(payload: ConvertRequest):
    """
    Convert a monetary amount from INR to a target currency.
    Returns converted amount, exchange rate used, timestamp, provider, and disclaimer.
    """
    target = (payload.target_currency or "").strip().upper()
    if target not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency '{payload.target_currency}'. Supported: {', '.join(sorted(SUPPORTED_CURRENCIES.keys()))}",
        )

    try:
        return convert_amount(payload.amount, target)
    except CurrencyServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion error: {exc}")


@router.post("/convert-budget")
def convert_budget_endpoint(payload: ConvertBudgetRequest):
    """
    Convert a complete budget breakdown into a target currency.
    Preserves all original INR amounts under 'original_inr' and returns
    converted breakdown, totals, per-day/per-person rates, rate source/timestamp,
    and a planning estimate disclaimer.
    """
    target = (payload.target_currency or "").strip().upper()
    if target not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency '{payload.target_currency}'. Supported: {', '.join(sorted(SUPPORTED_CURRENCIES.keys()))}",
        )

    try:
        return convert_budget_data(payload.budget, target)
    except CurrencyServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Budget conversion error: {exc}")
