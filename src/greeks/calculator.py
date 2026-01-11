"""
Greeks Calculator - Main calculator for portfolio Greeks

支持的资产类型:
- STK (股票): Delta = 持仓数
- OPT (期权): Black-Scholes 模型
- FUT (期货): Delta = 合约乘数 × 持仓数
- CASH (外汇): Delta = 持仓金额
- CFD (差价合约): Delta = 持仓数
- FOP (期货期权): Black-Scholes 模型 (简化处理)
- WAR (权证): Black-Scholes 模型
- FUND (基金): Delta = 持仓数
- CRYPTO (加密货币): Delta = 持仓数
- BOND (债券): 特殊处理 - 使用久期代替 Delta
"""

from datetime import date
from typing import Dict, List, Optional
from loguru import logger

from ..ib_client.models import Position, MarketData, SecType
from .black_scholes import BlackScholesModel
from .models import Greeks, PortfolioGreeks, GreeksByUnderlying


class GreeksCalculator:
    """
    Portfolio Greeks Calculator

    Calculates individual option Greeks and aggregates them for the entire portfolio.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.05,
        default_volatility: float = 0.25,
        default_dividend_yield: float = 0.0
    ):
        """
        Initialize Greeks Calculator

        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
            default_volatility: Default IV if not available (default 25%)
            default_dividend_yield: Default dividend yield (default 0%)
        """
        self.risk_free_rate = risk_free_rate
        self.default_volatility = default_volatility
        self.default_dividend_yield = default_dividend_yield
        self.bs_model = BlackScholesModel()

        logger.info(
            f"GreeksCalculator initialized: r={risk_free_rate:.2%}, "
            f"default_iv={default_volatility:.2%}, q={default_dividend_yield:.2%}"
        )

    def calculate_option_greeks(
        self,
        spot: float,
        strike: float,
        expiry_days: int,
        volatility: float,
        is_call: bool,
        position_size: float = 1.0,
        multiplier: int = 100,
        dividend_yield: Optional[float] = None
    ) -> Greeks:
        """
        Calculate Greeks for a single option position

        Args:
            spot: Underlying spot price
            strike: Option strike price
            expiry_days: Days to expiration
            volatility: Implied volatility (annualized)
            is_call: True for call, False for put
            position_size: Number of contracts (positive=long, negative=short)
            multiplier: Contract multiplier
            dividend_yield: Override dividend yield

        Returns:
            Greeks object
        """
        if expiry_days <= 0:
            logger.warning(f"Option expired or expiring today (DTE={expiry_days})")
            # Return at-expiry Greeks
            intrinsic_delta = 1.0 if (is_call and spot > strike) or (not is_call and spot < strike) else 0.0
            return Greeks(
                delta=intrinsic_delta * position_size * multiplier,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                delta_dollars=intrinsic_delta * position_size * multiplier * spot,
                gamma_dollars=0.0,
                theta_dollars=0.0,
                vega_dollars=0.0
            )

        # Convert days to years
        time_to_expiry = expiry_days / 365.0

        # Use provided or default dividend yield
        q = dividend_yield if dividend_yield is not None else self.default_dividend_yield

        # Use provided or default volatility
        vol = volatility if volatility > 0 else self.default_volatility

        return self.bs_model.calculate_all_greeks(
            spot=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            rate=self.risk_free_rate,
            volatility=vol,
            is_call=is_call,
            dividend_yield=q,
            position_size=position_size,
            multiplier=multiplier
        )

    def calculate_stock_greeks(
        self,
        spot: float,
        position_size: float
    ) -> Greeks:
        """
        Calculate Greeks for a stock position

        Stocks have:
        - Delta = 1.0 per share
        - All other Greeks = 0

        Args:
            spot: Current stock price
            position_size: Number of shares (positive=long, negative=short)

        Returns:
            Greeks object
        """
        return Greeks(
            delta=position_size,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_dollars=position_size * spot,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_futures_greeks(
        self,
        spot: float,
        position_size: float,
        multiplier: float = 1.0
    ) -> Greeks:
        """
        Calculate Greeks for a futures position

        Futures have:
        - Delta = contract_multiplier × position_size
        - All other Greeks = 0

        Args:
            spot: Current futures price
            position_size: Number of contracts (positive=long, negative=short)
            multiplier: Contract multiplier (e.g., 50 for ES)

        Returns:
            Greeks object
        """
        effective_delta = position_size * multiplier
        logger.debug(f"Futures Greeks: position={position_size}, multiplier={multiplier}, delta={effective_delta}")

        return Greeks(
            delta=effective_delta,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_dollars=effective_delta * spot,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_forex_greeks(
        self,
        spot: float,
        position_size: float
    ) -> Greeks:
        """
        Calculate Greeks for a forex position

        Forex positions:
        - Delta = position_amount (notional value in base currency)
        - All other Greeks = 0

        Args:
            spot: Current exchange rate
            position_size: Position amount in base currency

        Returns:
            Greeks object
        """
        return Greeks(
            delta=position_size,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_dollars=position_size * spot,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_fund_greeks(
        self,
        spot: float,
        position_size: float
    ) -> Greeks:
        """
        Calculate Greeks for a fund (ETF/Mutual Fund) position

        Funds behave like stocks:
        - Delta = 1.0 per share
        - All other Greeks = 0

        Args:
            spot: Current fund price/NAV
            position_size: Number of shares

        Returns:
            Greeks object
        """
        return Greeks(
            delta=position_size,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_dollars=position_size * spot,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_crypto_greeks(
        self,
        spot: float,
        position_size: float
    ) -> Greeks:
        """
        Calculate Greeks for a cryptocurrency position

        Crypto behaves like stocks:
        - Delta = 1.0 per unit
        - All other Greeks = 0

        Args:
            spot: Current crypto price
            position_size: Number of units

        Returns:
            Greeks object
        """
        return Greeks(
            delta=position_size,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_dollars=position_size * spot,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_cfd_greeks(
        self,
        spot: float,
        position_size: float
    ) -> Greeks:
        """
        Calculate Greeks for a CFD position

        CFDs behave like the underlying:
        - Delta = 1.0 per contract
        - All other Greeks = 0

        Args:
            spot: Current CFD price
            position_size: Number of contracts

        Returns:
            Greeks object
        """
        return Greeks(
            delta=position_size,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            delta_dollars=position_size * spot,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_bond_greeks(
        self,
        market_price: float,
        position_size: float,
        duration: float = 5.0
    ) -> Greeks:
        """
        Calculate Greeks for a bond position

        Bonds use duration as a proxy for interest rate sensitivity:
        - Delta represents price sensitivity (using duration)
        - Rho is more relevant for bonds
        - Other Greeks = 0

        Args:
            market_price: Current bond price
            position_size: Number of bonds
            duration: Modified duration (default 5 years)

        Returns:
            Greeks object with duration-based sensitivity
        """
        # For bonds, we use duration as the primary risk measure
        # Delta here represents the price sensitivity, scaled by duration
        market_value = market_price * position_size
        # Approximate: a 1% rate change moves price by -duration%
        rho_sensitivity = -duration * market_value / 100

        return Greeks(
            delta=position_size,  # Raw position for accounting
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=rho_sensitivity,  # Bond price sensitivity to rates
            delta_dollars=market_value,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )

    def calculate_position_greeks(
        self,
        position: Position,
        market_data: Optional[MarketData] = None
    ) -> Greeks:
        """
        Calculate Greeks for a single position

        Supports all IB asset types:
        - STK (Stock): Delta = position_size
        - OPT (Option): Black-Scholes model
        - FUT (Futures): Delta = multiplier × position_size
        - CASH (Forex): Delta = position_amount
        - CFD: Delta = position_size
        - FOP (Futures Option): Black-Scholes model
        - WAR (Warrant): Black-Scholes model
        - FUND (ETF/Mutual Fund): Delta = position_size
        - CRYPTO: Delta = position_size
        - BOND: Duration-based sensitivity

        Args:
            position: Position object
            market_data: Optional market data for the position

        Returns:
            Greeks object
        """
        spot = self._get_spot_price(position, market_data)

        # 股票 (Stock)
        if position.is_stock:
            return self.calculate_stock_greeks(spot, position.position)

        # 期权 (Option)
        elif position.is_option and position.option_details:
            return self._calculate_option_position_greeks(position, market_data, spot)

        # 期货 (Futures)
        elif position.is_futures:
            multiplier = position.futures_details.multiplier if position.futures_details else 1.0
            return self.calculate_futures_greeks(spot, position.position, multiplier)

        # 外汇 (Forex)
        elif position.is_forex:
            return self.calculate_forex_greeks(spot, position.position)

        # 差价合约 (CFD)
        elif position.is_cfd:
            return self.calculate_cfd_greeks(spot, position.position)

        # 期货期权 (Futures Option) - 使用 Black-Scholes 简化处理
        elif position.is_futures_option and position.option_details:
            return self._calculate_option_position_greeks(position, market_data, spot)

        # 权证 (Warrant) - 类似期权处理
        elif position.is_warrant and position.option_details:
            return self._calculate_option_position_greeks(position, market_data, spot)

        # 基金 (ETF/Mutual Fund)
        elif position.is_fund:
            return self.calculate_fund_greeks(spot, position.position)

        # 加密货币 (Cryptocurrency)
        elif position.is_crypto:
            return self.calculate_crypto_greeks(spot, position.position)

        # 债券 (Bond)
        elif position.is_bond:
            duration = 5.0  # 默认久期
            if position.bond_details:
                # 可以根据到期日估算久期
                years_to_maturity = position.bond_details.days_to_maturity / 365.0
                duration = min(years_to_maturity * 0.8, 10.0)  # 简化估算
            return self.calculate_bond_greeks(spot, position.position, duration)

        # 未知类型 - 按现货处理
        else:
            logger.warning(
                f"Unknown position type for {position.symbol}: {position.sec_type}. "
                f"Treating as spot asset with Delta = position_size."
            )
            return self.calculate_stock_greeks(spot, position.position)

    def _get_spot_price(self, position: Position, market_data: Optional[MarketData]) -> float:
        """获取标的价格"""
        if market_data:
            if market_data.mid > 0:
                return market_data.mid
            if market_data.underlying_price and market_data.underlying_price > 0:
                return market_data.underlying_price

        if position.market_price > 0:
            return position.market_price

        if position.avg_cost > 0:
            return position.avg_cost

        return 100.0  # 默认值

    def _calculate_option_position_greeks(
        self,
        position: Position,
        market_data: Optional[MarketData],
        spot: float
    ) -> Greeks:
        """计算期权类持仓的希腊值（期权、期货期权、权证）"""
        opt = position.option_details

        # 确定标的价格
        if market_data and market_data.underlying_price:
            underlying_spot = market_data.underlying_price
        else:
            # 尝试从期权价格反推
            underlying_spot = spot

        # 获取隐含波动率
        volatility = self.default_volatility
        if market_data and market_data.implied_volatility:
            volatility = market_data.implied_volatility

        return self.calculate_option_greeks(
            spot=underlying_spot,
            strike=opt.strike,
            expiry_days=opt.days_to_expiry,
            volatility=volatility,
            is_call=opt.is_call,
            position_size=position.position,
            multiplier=opt.multiplier
        )

    def calculate_portfolio_greeks(
        self,
        positions: List[Position],
        market_data: Optional[Dict[int, MarketData]] = None
    ) -> PortfolioGreeks:
        """
        Calculate aggregated Greeks for the entire portfolio

        Args:
            positions: List of Position objects
            market_data: Dictionary mapping conId to MarketData

        Returns:
            PortfolioGreeks object with totals and breakdown by underlying
        """
        logger.info(f"Calculating portfolio Greeks for {len(positions)} positions")

        portfolio_greeks = PortfolioGreeks()
        underlying_groups: Dict[str, List[tuple]] = {}  # symbol -> [(position, greeks, market_data)]

        # Calculate Greeks for each position and group by underlying
        for position in positions:
            md = market_data.get(position.con_id) if market_data else None
            greeks = self.calculate_position_greeks(position, md)

            symbol = position.symbol
            if symbol not in underlying_groups:
                underlying_groups[symbol] = []
            underlying_groups[symbol].append((position, greeks, md))

            logger.debug(
                f"Position {symbol} ({position.sec_type}): "
                f"Δ={greeks.delta:.2f}, Θ=${greeks.theta_dollars:.2f}"
            )

        # Aggregate by underlying
        total_vega_weighted_iv = 0.0
        total_vega = 0.0
        min_dte = None
        total_value_weighted_dte = 0.0
        total_option_value = 0.0

        for symbol, group in underlying_groups.items():
            underlying_greeks = Greeks()
            underlying_price = 0.0
            position_count = len(group)

            for position, greeks, md in group:
                underlying_greeks = underlying_greeks + greeks

                # Track underlying price
                if md:
                    if position.is_stock:
                        underlying_price = md.mid
                    elif md.underlying_price:
                        underlying_price = md.underlying_price

                # Track IV for weighted average
                if position.is_option and md and md.implied_volatility:
                    abs_vega = abs(greeks.vega_dollars)
                    total_vega_weighted_iv += md.implied_volatility * abs_vega
                    total_vega += abs_vega

                # Track DTE for weighted average
                if position.is_option and position.option_details:
                    dte = position.option_details.days_to_expiry
                    option_value = abs(position.market_value)

                    if min_dte is None or dte < min_dte:
                        min_dte = dte

                    total_value_weighted_dte += dte * option_value
                    total_option_value += option_value

            # Create underlying summary
            underlying_summary = GreeksByUnderlying(
                symbol=symbol,
                underlying_price=underlying_price,
                position_count=position_count,
                greeks=underlying_greeks,
                stock_equivalent_shares=underlying_greeks.delta
            )

            portfolio_greeks.add_underlying_greeks(symbol, underlying_summary)

            logger.info(
                f"Underlying {symbol}: {position_count} positions, "
                f"Δ={underlying_greeks.delta:.2f}, Θ=${underlying_greeks.theta_dollars:.2f}/day"
            )

        # Calculate weighted metrics
        if total_vega > 0:
            portfolio_greeks.weighted_average_iv = total_vega_weighted_iv / total_vega

        if total_option_value > 0:
            portfolio_greeks.weighted_dte = total_value_weighted_dte / total_option_value

        portfolio_greeks.days_to_nearest_expiry = min_dte

        logger.info("=" * 60)
        logger.info("Portfolio Greeks Summary:")
        logger.info(f"  Total Delta: {portfolio_greeks.total_delta:.2f} shares equivalent")
        logger.info(f"  Delta Dollars: ${portfolio_greeks.total_delta_dollars:,.2f}")
        logger.info(f"  Total Gamma: {portfolio_greeks.total_gamma:.4f}")
        logger.info(f"  Gamma Dollars: ${portfolio_greeks.total_gamma_dollars:,.2f} per 1% move")
        logger.info(f"  Total Theta: ${portfolio_greeks.total_theta_dollars:,.2f}/day")
        logger.info(f"  Total Vega: ${portfolio_greeks.total_vega_dollars:,.2f} per 1% IV")
        logger.info(f"  Weighted Avg IV: {portfolio_greeks.weighted_average_iv * 100:.1f}%")
        logger.info(f"  Weighted DTE: {portfolio_greeks.weighted_dte:.1f} days")
        if min_dte is not None:
            logger.info(f"  Nearest Expiry: {min_dte} days")
        logger.info("=" * 60)

        return portfolio_greeks

    def calculate_delta_hedge(
        self,
        portfolio_greeks: PortfolioGreeks,
        target_delta: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculate shares needed to delta hedge the portfolio

        Args:
            portfolio_greeks: Current portfolio Greeks
            target_delta: Target delta (0 for neutral)

        Returns:
            Dictionary of symbol -> shares to trade
        """
        hedge_trades = {}

        for symbol, underlying in portfolio_greeks.by_underlying.items():
            current_delta = underlying.greeks.delta
            delta_to_hedge = target_delta - current_delta

            if abs(delta_to_hedge) > 0.5:  # Minimum 0.5 share threshold
                hedge_trades[symbol] = round(delta_to_hedge)

                logger.info(
                    f"Delta hedge for {symbol}: "
                    f"current={current_delta:.2f}, "
                    f"trade={hedge_trades[symbol]:+d} shares"
                )

        return hedge_trades

    def scenario_analysis(
        self,
        positions: List[Position],
        market_data: Optional[Dict[int, MarketData]] = None,
        spot_changes: List[float] = None,
        iv_changes: List[float] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Run scenario analysis on portfolio

        Args:
            positions: List of positions
            market_data: Market data dictionary
            spot_changes: List of spot price change percentages (e.g., [-10, -5, 0, 5, 10])
            iv_changes: List of IV change percentages (e.g., [-20, -10, 0, 10, 20])

        Returns:
            Nested dictionary of scenario results
        """
        if spot_changes is None:
            spot_changes = [-10, -5, -2, 0, 2, 5, 10]
        if iv_changes is None:
            iv_changes = [-20, -10, 0, 10, 20]

        results = {}

        # Get base portfolio greeks for comparison
        base_greeks = self.calculate_portfolio_greeks(positions, market_data)

        for spot_pct in spot_changes:
            spot_key = f"spot_{spot_pct:+d}%"
            results[spot_key] = {}

            for iv_pct in iv_changes:
                iv_key = f"iv_{iv_pct:+d}%"

                # Estimate P&L using Greeks
                # P&L ≈ delta * dS + 0.5 * gamma * dS^2 + vega * dIV
                delta_pnl = base_greeks.total_delta_dollars * (spot_pct / 100)
                gamma_pnl = 0.5 * base_greeks.total_gamma_dollars * (spot_pct ** 2)
                vega_pnl = base_greeks.total_vega_dollars * (iv_pct / 100)

                total_pnl = delta_pnl + gamma_pnl + vega_pnl

                results[spot_key][iv_key] = round(total_pnl, 2)

        return results
