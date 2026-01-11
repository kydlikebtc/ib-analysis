"""
Data models for IB Client module
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger


class OptionDetails(BaseModel):
    """Option-specific details"""
    strike: float = Field(..., description="Strike price")
    right: str = Field(..., description="Option right: C for Call, P for Put")
    expiry: date = Field(..., description="Expiration date")
    multiplier: int = Field(default=100, description="Contract multiplier")

    @property
    def is_call(self) -> bool:
        return self.right.upper() == "C"

    @property
    def is_put(self) -> bool:
        return self.right.upper() == "P"

    @property
    def days_to_expiry(self) -> int:
        """Calculate days until expiration"""
        delta = self.expiry - date.today()
        return max(0, delta.days)


class Position(BaseModel):
    """Represents a portfolio position"""
    symbol: str = Field(..., description="Underlying symbol")
    sec_type: str = Field(..., description="Security type: STK, OPT, FUT, etc.")
    con_id: int = Field(..., description="IB contract ID")
    position: float = Field(..., description="Position quantity (positive=long, negative=short)")
    avg_cost: float = Field(default=0.0, description="Average cost per unit")
    market_price: float = Field(default=0.0, description="Current market price")
    market_value: float = Field(default=0.0, description="Current market value")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized P&L")
    realized_pnl: float = Field(default=0.0, description="Realized P&L")
    currency: str = Field(default="USD", description="Currency")
    exchange: str = Field(default="SMART", description="Exchange")
    option_details: Optional[OptionDetails] = Field(default=None, description="Option details if applicable")

    @property
    def is_option(self) -> bool:
        return self.sec_type == "OPT"

    @property
    def is_stock(self) -> bool:
        return self.sec_type == "STK"

    @property
    def is_long(self) -> bool:
        return self.position > 0

    @property
    def is_short(self) -> bool:
        return self.position < 0

    @property
    def total_cost(self) -> float:
        """Total cost basis"""
        return abs(self.position) * self.avg_cost

    def log_details(self) -> None:
        """Log position details for debugging"""
        logger.debug(
            f"Position: {self.symbol} | Type: {self.sec_type} | "
            f"Qty: {self.position} | Price: {self.market_price:.2f} | "
            f"Value: {self.market_value:.2f} | P&L: {self.unrealized_pnl:.2f}"
        )
        if self.option_details:
            logger.debug(
                f"  Option: {self.option_details.strike} "
                f"{self.option_details.right} exp {self.option_details.expiry} "
                f"({self.option_details.days_to_expiry} days)"
            )


class MarketData(BaseModel):
    """Market data for a security"""
    symbol: str
    con_id: int
    bid: float = Field(default=0.0)
    ask: float = Field(default=0.0)
    last: float = Field(default=0.0)
    close: float = Field(default=0.0)
    high: float = Field(default=0.0)
    low: float = Field(default=0.0)
    volume: int = Field(default=0)
    open_interest: Optional[int] = Field(default=None, description="Open interest for options")
    implied_volatility: Optional[float] = Field(default=None, description="Implied volatility")
    underlying_price: Optional[float] = Field(default=None, description="Underlying price for options")
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def mid(self) -> float:
        """Mid price"""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last if self.last > 0 else self.close

    @property
    def spread(self) -> float:
        """Bid-ask spread"""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0

    @property
    def spread_pct(self) -> float:
        """Bid-ask spread as percentage of mid"""
        mid = self.mid
        if mid > 0:
            return self.spread / mid * 100
        return 0.0


class AccountSummary(BaseModel):
    """Account summary information"""
    account_id: str = Field(..., description="Account identifier")
    net_liquidation: float = Field(default=0.0, description="Net liquidation value")
    total_cash: float = Field(default=0.0, description="Total cash balance")
    settled_cash: float = Field(default=0.0, description="Settled cash")
    buying_power: float = Field(default=0.0, description="Buying power")
    equity_with_loan: float = Field(default=0.0, description="Equity with loan value")
    gross_position_value: float = Field(default=0.0, description="Gross position value")
    maintenance_margin: float = Field(default=0.0, description="Maintenance margin requirement")
    initial_margin: float = Field(default=0.0, description="Initial margin requirement")
    available_funds: float = Field(default=0.0, description="Available funds")
    excess_liquidity: float = Field(default=0.0, description="Excess liquidity")
    sma: float = Field(default=0.0, description="Special Memorandum Account")
    unrealized_pnl: float = Field(default=0.0, description="Total unrealized P&L")
    realized_pnl: float = Field(default=0.0, description="Total realized P&L")
    currency: str = Field(default="USD")
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def margin_usage(self) -> float:
        """Margin usage percentage"""
        if self.net_liquidation > 0:
            return self.maintenance_margin / self.net_liquidation * 100
        return 0.0

    def log_summary(self) -> None:
        """Log account summary for debugging"""
        logger.info(f"Account: {self.account_id}")
        logger.info(f"  Net Liquidation: ${self.net_liquidation:,.2f}")
        logger.info(f"  Total Cash: ${self.total_cash:,.2f}")
        logger.info(f"  Buying Power: ${self.buying_power:,.2f}")
        logger.info(f"  Margin Usage: {self.margin_usage:.1f}%")
        logger.info(f"  Unrealized P&L: ${self.unrealized_pnl:,.2f}")
