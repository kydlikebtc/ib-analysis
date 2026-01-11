"""
Data models for Greeks calculation
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class Greeks(BaseModel):
    """Greeks for a single option or position"""
    delta: float = Field(default=0.0, description="Delta - price sensitivity")
    gamma: float = Field(default=0.0, description="Gamma - delta sensitivity")
    theta: float = Field(default=0.0, description="Theta - time decay (daily)")
    vega: float = Field(default=0.0, description="Vega - volatility sensitivity (per 1%)")
    rho: float = Field(default=0.0, description="Rho - interest rate sensitivity")

    # Extended metrics
    delta_dollars: float = Field(default=0.0, description="Dollar delta exposure")
    gamma_dollars: float = Field(default=0.0, description="Dollar gamma exposure")
    theta_dollars: float = Field(default=0.0, description="Daily theta in dollars")
    vega_dollars: float = Field(default=0.0, description="Vega in dollars per 1% IV change")

    def __add__(self, other: "Greeks") -> "Greeks":
        """Add two Greeks objects together"""
        return Greeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            theta=self.theta + other.theta,
            vega=self.vega + other.vega,
            rho=self.rho + other.rho,
            delta_dollars=self.delta_dollars + other.delta_dollars,
            gamma_dollars=self.gamma_dollars + other.gamma_dollars,
            theta_dollars=self.theta_dollars + other.theta_dollars,
            vega_dollars=self.vega_dollars + other.vega_dollars
        )

    def __mul__(self, scalar: float) -> "Greeks":
        """Multiply Greeks by a scalar"""
        return Greeks(
            delta=self.delta * scalar,
            gamma=self.gamma * scalar,
            theta=self.theta * scalar,
            vega=self.vega * scalar,
            rho=self.rho * scalar,
            delta_dollars=self.delta_dollars * scalar,
            gamma_dollars=self.gamma_dollars * scalar,
            theta_dollars=self.theta_dollars * scalar,
            vega_dollars=self.vega_dollars * scalar
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "rho": round(self.rho, 4),
            "delta_dollars": round(self.delta_dollars, 2),
            "gamma_dollars": round(self.gamma_dollars, 2),
            "theta_dollars": round(self.theta_dollars, 2),
            "vega_dollars": round(self.vega_dollars, 2)
        }


class GreeksByUnderlying(BaseModel):
    """Greeks grouped by underlying symbol"""
    symbol: str
    underlying_price: float = 0.0
    position_count: int = 0
    greeks: Greeks = Field(default_factory=Greeks)
    stock_equivalent_shares: float = Field(
        default=0.0,
        description="Number of shares equivalent based on delta"
    )

    @property
    def beta_adjusted_delta(self) -> float:
        """Beta-adjusted delta (placeholder for future implementation)"""
        return self.greeks.delta  # TODO: Implement beta adjustment


class PortfolioGreeks(BaseModel):
    """Aggregated Greeks for entire portfolio"""
    # Total raw Greeks
    total_delta: float = Field(default=0.0, description="Total portfolio delta")
    total_gamma: float = Field(default=0.0, description="Total portfolio gamma")
    total_theta: float = Field(default=0.0, description="Total daily theta")
    total_vega: float = Field(default=0.0, description="Total vega")
    total_rho: float = Field(default=0.0, description="Total rho")

    # Dollar-denominated Greeks
    total_delta_dollars: float = Field(default=0.0, description="Total delta in dollars")
    total_gamma_dollars: float = Field(default=0.0, description="Total gamma in dollars")
    total_theta_dollars: float = Field(default=0.0, description="Total daily theta in dollars")
    total_vega_dollars: float = Field(default=0.0, description="Total vega in dollars per 1% IV")

    # Breakdown by underlying
    by_underlying: Dict[str, GreeksByUnderlying] = Field(
        default_factory=dict,
        description="Greeks grouped by underlying symbol"
    )

    # Additional metrics
    net_delta_exposure: float = Field(
        default=0.0,
        description="Net delta as equivalent shares of SPY"
    )
    weighted_average_iv: float = Field(
        default=0.0,
        description="Weighted average implied volatility"
    )
    days_to_nearest_expiry: Optional[int] = Field(
        default=None,
        description="Days to nearest option expiration"
    )
    weighted_dte: float = Field(
        default=0.0,
        description="Value-weighted days to expiration"
    )

    def add_underlying_greeks(self, symbol: str, greeks: GreeksByUnderlying) -> None:
        """Add Greeks for an underlying"""
        self.by_underlying[symbol] = greeks

        # Update totals
        self.total_delta += greeks.greeks.delta
        self.total_gamma += greeks.greeks.gamma
        self.total_theta += greeks.greeks.theta
        self.total_vega += greeks.greeks.vega
        self.total_rho += greeks.greeks.rho

        self.total_delta_dollars += greeks.greeks.delta_dollars
        self.total_gamma_dollars += greeks.greeks.gamma_dollars
        self.total_theta_dollars += greeks.greeks.theta_dollars
        self.total_vega_dollars += greeks.greeks.vega_dollars

    def summary_dict(self) -> Dict[str, float]:
        """Get summary as dictionary"""
        return {
            "total_delta": round(self.total_delta, 2),
            "total_gamma": round(self.total_gamma, 4),
            "total_theta": round(self.total_theta, 2),
            "total_vega": round(self.total_vega, 2),
            "total_rho": round(self.total_rho, 2),
            "delta_dollars": round(self.total_delta_dollars, 2),
            "gamma_dollars": round(self.total_gamma_dollars, 2),
            "theta_dollars": round(self.total_theta_dollars, 2),
            "vega_dollars": round(self.total_vega_dollars, 2),
            "weighted_avg_iv": round(self.weighted_average_iv * 100, 2),
            "weighted_dte": round(self.weighted_dte, 1),
        }
