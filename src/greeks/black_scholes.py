"""
Black-Scholes Option Pricing Model

Implements the Black-Scholes-Merton model for European option pricing
and Greeks calculation.
"""

import math
from typing import Tuple
from scipy import stats
from loguru import logger

from .models import Greeks


class BlackScholesModel:
    """
    Black-Scholes-Merton Option Pricing Model

    Calculates option prices and Greeks using the BSM model.
    Supports dividend-adjusted calculations.
    """

    @staticmethod
    def d1(
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate d1 parameter for Black-Scholes formula

        Args:
            spot: Current spot price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            rate: Risk-free interest rate (annualized)
            volatility: Implied volatility (annualized)
            dividend_yield: Continuous dividend yield

        Returns:
            d1 value
        """
        if time_to_expiry <= 0 or volatility <= 0 or spot <= 0 or strike <= 0:
            return 0.0

        numerator = (
            math.log(spot / strike) +
            (rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        )
        denominator = volatility * math.sqrt(time_to_expiry)

        return numerator / denominator

    @staticmethod
    def d2(
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """Calculate d2 parameter (d1 - sigma * sqrt(t))"""
        d1_val = BlackScholesModel.d1(
            spot, strike, time_to_expiry, rate, volatility, dividend_yield
        )
        if time_to_expiry <= 0 or volatility <= 0:
            return 0.0
        return d1_val - volatility * math.sqrt(time_to_expiry)

    @classmethod
    def call_price(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate Black-Scholes call option price

        Args:
            spot: Current spot price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            rate: Risk-free interest rate
            volatility: Implied volatility
            dividend_yield: Continuous dividend yield

        Returns:
            Call option price
        """
        if time_to_expiry <= 0:
            return max(0, spot - strike)

        d1_val = cls.d1(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        d2_val = cls.d2(spot, strike, time_to_expiry, rate, volatility, dividend_yield)

        call = (
            spot * math.exp(-dividend_yield * time_to_expiry) * stats.norm.cdf(d1_val) -
            strike * math.exp(-rate * time_to_expiry) * stats.norm.cdf(d2_val)
        )

        return max(0, call)

    @classmethod
    def put_price(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate Black-Scholes put option price

        Uses put-call parity: P = C - S*e^(-q*t) + K*e^(-r*t)
        """
        if time_to_expiry <= 0:
            return max(0, strike - spot)

        d1_val = cls.d1(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        d2_val = cls.d2(spot, strike, time_to_expiry, rate, volatility, dividend_yield)

        put = (
            strike * math.exp(-rate * time_to_expiry) * stats.norm.cdf(-d2_val) -
            spot * math.exp(-dividend_yield * time_to_expiry) * stats.norm.cdf(-d1_val)
        )

        return max(0, put)

    @classmethod
    def delta(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        is_call: bool,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option delta

        Delta measures the rate of change of option price with respect to
        changes in the underlying asset's price.

        Call delta: N(d1) * e^(-q*t)
        Put delta: (N(d1) - 1) * e^(-q*t)
        """
        if time_to_expiry <= 0:
            if is_call:
                return 1.0 if spot > strike else 0.0
            else:
                return -1.0 if spot < strike else 0.0

        d1_val = cls.d1(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        discount = math.exp(-dividend_yield * time_to_expiry)

        if is_call:
            return stats.norm.cdf(d1_val) * discount
        else:
            return (stats.norm.cdf(d1_val) - 1) * discount

    @classmethod
    def gamma(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option gamma

        Gamma measures the rate of change of delta with respect to
        changes in the underlying price.

        Gamma = n(d1) * e^(-q*t) / (S * sigma * sqrt(t))
        where n(x) is the standard normal PDF
        """
        if time_to_expiry <= 0 or volatility <= 0 or spot <= 0:
            return 0.0

        d1_val = cls.d1(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        discount = math.exp(-dividend_yield * time_to_expiry)

        numerator = stats.norm.pdf(d1_val) * discount
        denominator = spot * volatility * math.sqrt(time_to_expiry)

        return numerator / denominator

    @classmethod
    def theta(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        is_call: bool,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option theta (daily time decay)

        Returns theta as daily value (negative for long options).
        Divide by 365 to convert from annual.
        """
        if time_to_expiry <= 0:
            return 0.0

        d1_val = cls.d1(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        d2_val = cls.d2(spot, strike, time_to_expiry, rate, volatility, dividend_yield)

        sqrt_t = math.sqrt(time_to_expiry)
        discount_q = math.exp(-dividend_yield * time_to_expiry)
        discount_r = math.exp(-rate * time_to_expiry)

        # First term (same for calls and puts)
        term1 = -(spot * volatility * discount_q * stats.norm.pdf(d1_val)) / (2 * sqrt_t)

        if is_call:
            term2 = dividend_yield * spot * discount_q * stats.norm.cdf(d1_val)
            term3 = -rate * strike * discount_r * stats.norm.cdf(d2_val)
        else:
            term2 = -dividend_yield * spot * discount_q * stats.norm.cdf(-d1_val)
            term3 = rate * strike * discount_r * stats.norm.cdf(-d2_val)

        annual_theta = term1 + term2 + term3

        # Convert to daily theta
        return annual_theta / 365

    @classmethod
    def vega(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option vega

        Vega measures the rate of change of option price with respect to
        changes in volatility. Returns vega per 1% (0.01) change in volatility.

        Vega = S * sqrt(t) * n(d1) * e^(-q*t)
        """
        if time_to_expiry <= 0 or spot <= 0:
            return 0.0

        d1_val = cls.d1(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        discount = math.exp(-dividend_yield * time_to_expiry)

        # Vega per 1% change (multiply by 0.01)
        vega = spot * math.sqrt(time_to_expiry) * stats.norm.pdf(d1_val) * discount * 0.01

        return vega

    @classmethod
    def rho(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        is_call: bool,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option rho

        Rho measures the rate of change of option price with respect to
        changes in the risk-free interest rate.
        Returns rho per 1% (0.01) change in rate.
        """
        if time_to_expiry <= 0:
            return 0.0

        d2_val = cls.d2(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        discount = math.exp(-rate * time_to_expiry)

        if is_call:
            rho = strike * time_to_expiry * discount * stats.norm.cdf(d2_val) * 0.01
        else:
            rho = -strike * time_to_expiry * discount * stats.norm.cdf(-d2_val) * 0.01

        return rho

    @classmethod
    def calculate_all_greeks(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        is_call: bool,
        dividend_yield: float = 0.0,
        position_size: float = 1.0,
        multiplier: int = 100
    ) -> Greeks:
        """
        Calculate all Greeks for an option

        Args:
            spot: Current spot price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            rate: Risk-free interest rate
            volatility: Implied volatility
            is_call: True for call, False for put
            dividend_yield: Continuous dividend yield
            position_size: Number of contracts (positive=long, negative=short)
            multiplier: Contract multiplier (usually 100)

        Returns:
            Greeks object with all calculated values
        """
        logger.debug(
            f"Calculating Greeks: S={spot:.2f}, K={strike:.2f}, "
            f"T={time_to_expiry:.4f}, r={rate:.4f}, σ={volatility:.4f}, "
            f"{'Call' if is_call else 'Put'}, qty={position_size}"
        )

        # Calculate base Greeks (per share)
        delta = cls.delta(spot, strike, time_to_expiry, rate, volatility, is_call, dividend_yield)
        gamma = cls.gamma(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        theta = cls.theta(spot, strike, time_to_expiry, rate, volatility, is_call, dividend_yield)
        vega = cls.vega(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        rho = cls.rho(spot, strike, time_to_expiry, rate, volatility, is_call, dividend_yield)

        # Scale by position size and multiplier
        total_multiplier = position_size * multiplier

        greeks = Greeks(
            delta=delta * total_multiplier,
            gamma=gamma * total_multiplier,
            theta=theta * total_multiplier,
            vega=vega * total_multiplier,
            rho=rho * total_multiplier,
            # Dollar-denominated Greeks
            delta_dollars=delta * total_multiplier * spot,
            gamma_dollars=gamma * total_multiplier * spot * 0.01,  # Per 1% move
            theta_dollars=theta * total_multiplier,
            vega_dollars=vega * total_multiplier
        )

        logger.debug(
            f"Greeks calculated: Δ={greeks.delta:.2f}, Γ={greeks.gamma:.4f}, "
            f"Θ={greeks.theta:.2f}, V={greeks.vega:.2f}"
        )

        return greeks

    @classmethod
    def implied_volatility(
        cls,
        option_price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        is_call: bool,
        dividend_yield: float = 0.0,
        precision: float = 0.0001,
        max_iterations: int = 100
    ) -> float:
        """
        Calculate implied volatility using Newton-Raphson method

        Args:
            option_price: Market price of the option
            spot: Current spot price
            strike: Strike price
            time_to_expiry: Time to expiration in years
            rate: Risk-free rate
            is_call: True for call, False for put
            dividend_yield: Dividend yield
            precision: Target precision
            max_iterations: Maximum iterations

        Returns:
            Implied volatility
        """
        if time_to_expiry <= 0 or option_price <= 0:
            return 0.0

        # Initial guess using Brenner-Subrahmanyam approximation
        iv = math.sqrt(2 * math.pi / time_to_expiry) * option_price / spot

        for i in range(max_iterations):
            price_func = cls.call_price if is_call else cls.put_price
            price = price_func(spot, strike, time_to_expiry, rate, iv, dividend_yield)
            vega = cls.vega(spot, strike, time_to_expiry, rate, iv, dividend_yield) * 100

            diff = price - option_price

            if abs(diff) < precision:
                logger.debug(f"IV converged after {i + 1} iterations: {iv:.4f}")
                return iv

            if abs(vega) < 1e-10:
                break

            iv = iv - diff / vega
            iv = max(0.01, min(5.0, iv))  # Keep IV between 1% and 500%

        logger.warning(f"IV did not converge. Last estimate: {iv:.4f}")
        return iv
