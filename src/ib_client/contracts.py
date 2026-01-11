"""
Contract building utilities for IB API
"""

from datetime import date
from typing import Optional
from loguru import logger

try:
    from ib_insync import Stock, Option, Future, Contract
except ImportError:
    logger.warning("ib_insync not installed, using mock contracts")
    # Mock classes for testing without ib_insync
    class Contract:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    Stock = Option = Future = Contract


def create_stock_contract(
    symbol: str,
    exchange: str = "SMART",
    currency: str = "USD"
) -> Contract:
    """
    Create a stock contract

    Args:
        symbol: Stock symbol
        exchange: Exchange (default: SMART)
        currency: Currency (default: USD)

    Returns:
        Stock contract
    """
    logger.debug(f"Creating stock contract: {symbol} on {exchange}")
    return Stock(symbol, exchange, currency)


def create_option_contract(
    symbol: str,
    expiry: date,
    strike: float,
    right: str,
    exchange: str = "SMART",
    currency: str = "USD",
    multiplier: int = 100
) -> Contract:
    """
    Create an option contract

    Args:
        symbol: Underlying symbol
        expiry: Expiration date
        strike: Strike price
        right: 'C' for Call, 'P' for Put
        exchange: Exchange (default: SMART)
        currency: Currency (default: USD)
        multiplier: Contract multiplier (default: 100)

    Returns:
        Option contract
    """
    expiry_str = expiry.strftime("%Y%m%d")
    right_str = right.upper()[0]  # Ensure 'C' or 'P'

    logger.debug(
        f"Creating option contract: {symbol} {strike} {right_str} "
        f"exp {expiry_str} mult {multiplier}"
    )

    return Option(
        symbol=symbol,
        lastTradeDateOrContractMonth=expiry_str,
        strike=strike,
        right=right_str,
        exchange=exchange,
        currency=currency,
        multiplier=str(multiplier)
    )


def create_future_contract(
    symbol: str,
    expiry: date,
    exchange: str,
    currency: str = "USD",
    multiplier: Optional[int] = None
) -> Contract:
    """
    Create a futures contract

    Args:
        symbol: Futures symbol
        expiry: Expiration date
        exchange: Exchange
        currency: Currency (default: USD)
        multiplier: Contract multiplier

    Returns:
        Futures contract
    """
    expiry_str = expiry.strftime("%Y%m%d")

    logger.debug(f"Creating futures contract: {symbol} exp {expiry_str} on {exchange}")

    contract = Future(
        symbol=symbol,
        lastTradeDateOrContractMonth=expiry_str,
        exchange=exchange,
        currency=currency
    )

    if multiplier:
        contract.multiplier = str(multiplier)

    return contract


def create_contract_from_position(position_data: dict) -> Contract:
    """
    Create a contract from position data

    Args:
        position_data: Dictionary with position information

    Returns:
        Appropriate contract type
    """
    sec_type = position_data.get("sec_type", "STK")
    symbol = position_data["symbol"]
    exchange = position_data.get("exchange", "SMART")
    currency = position_data.get("currency", "USD")

    if sec_type == "STK":
        return create_stock_contract(symbol, exchange, currency)

    elif sec_type == "OPT":
        option_details = position_data.get("option_details", {})
        return create_option_contract(
            symbol=symbol,
            expiry=option_details["expiry"],
            strike=option_details["strike"],
            right=option_details["right"],
            exchange=exchange,
            currency=currency,
            multiplier=option_details.get("multiplier", 100)
        )

    elif sec_type == "FUT":
        return create_future_contract(
            symbol=symbol,
            expiry=position_data.get("expiry"),
            exchange=exchange,
            currency=currency,
            multiplier=position_data.get("multiplier")
        )

    else:
        logger.warning(f"Unknown security type: {sec_type}, creating generic contract")
        return Contract(
            symbol=symbol,
            secType=sec_type,
            exchange=exchange,
            currency=currency
        )
