"""
Monte Carlo Simulator - Main simulation engine
"""

from datetime import date
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats as scipy_stats
from loguru import logger

from ..ib_client.models import Position, MarketData
from ..greeks.black_scholes import BlackScholesModel
from .models import (
    SimulationConfig, SimulationResult, SimulationStatistics,
    PercentileResults
)


class MonteCarloSimulator:
    """
    Monte Carlo Portfolio Simulator

    Simulates future price paths using Geometric Brownian Motion (GBM)
    and calculates portfolio values over time.
    """

    def __init__(
        self,
        num_paths: int = 10000,
        num_days: int = 30,
        random_seed: Optional[int] = None,
        risk_free_rate: float = 0.05
    ):
        """
        Initialize Monte Carlo Simulator

        Args:
            num_paths: Number of simulation paths
            num_days: Number of days to simulate
            random_seed: Random seed for reproducibility
            risk_free_rate: Annual risk-free rate
        """
        self.config = SimulationConfig(
            num_paths=num_paths,
            num_days=num_days,
            random_seed=random_seed,
            risk_free_rate=risk_free_rate
        )

        # Use local random generator for reproducibility
        self.rng = np.random.default_rng(random_seed)

        self.bs_model = BlackScholesModel()

        logger.info(
            f"MonteCarloSimulator initialized: "
            f"{num_paths} paths, {num_days} days, seed={random_seed}"
        )

    def simulate_price_paths(
        self,
        current_price: float,
        volatility: float,
        drift: Optional[float] = None,
        dividend_yield: float = 0.0
    ) -> np.ndarray:
        """
        Simulate price paths using Geometric Brownian Motion

        GBM: dS = μSdt + σSdW
        Discrete: S(t+dt) = S(t) * exp((μ - 0.5σ²)dt + σ√dt * Z)

        Args:
            current_price: Current spot price
            volatility: Annualized volatility
            drift: Drift rate (defaults to risk-free - dividend)
            dividend_yield: Continuous dividend yield

        Returns:
            Array of shape (num_paths, num_days + 1) with price paths
        """
        num_paths = self.config.num_paths
        num_days = self.config.num_days

        if drift is None:
            drift = self.config.risk_free_rate - dividend_yield

        dt = 1 / 252  # Daily time step (trading days)

        logger.debug(
            f"Simulating {num_paths} paths for {num_days} days: "
            f"S0={current_price:.2f}, σ={volatility:.2%}, μ={drift:.4f}"
        )

        # Generate random numbers using local RNG for reproducibility
        if self.config.use_antithetic:
            # Antithetic variates for variance reduction
            half_paths = num_paths // 2
            z_half = self.rng.standard_normal((half_paths, num_days))
            z = np.concatenate([z_half, -z_half], axis=0)
            if num_paths % 2 == 1:
                z = np.concatenate([z, self.rng.standard_normal((1, num_days))], axis=0)
        else:
            z = self.rng.standard_normal((num_paths, num_days))

        # Calculate daily returns
        # ln(S(t+1)/S(t)) = (μ - 0.5σ²)dt + σ√dt * Z
        daily_drift = (drift - 0.5 * volatility ** 2) * dt
        daily_vol = volatility * np.sqrt(dt)

        log_returns = daily_drift + daily_vol * z

        # Cumulative returns
        cumulative_returns = np.cumsum(log_returns, axis=1)

        # Initialize price paths with current price at day 0
        paths = np.zeros((num_paths, num_days + 1))
        paths[:, 0] = current_price
        paths[:, 1:] = current_price * np.exp(cumulative_returns)

        return paths

    def simulate_correlated_prices(
        self,
        prices: Dict[str, float],
        volatilities: Dict[str, float],
        correlation_matrix: Optional[np.ndarray] = None,
        dividend_yields: Optional[Dict[str, float]] = None
    ) -> Dict[str, np.ndarray]:
        """
        Simulate correlated price paths for multiple assets

        Args:
            prices: Dictionary of symbol -> current price
            volatilities: Dictionary of symbol -> volatility
            correlation_matrix: Correlation matrix (if None, assumes independence)
            dividend_yields: Dictionary of symbol -> dividend yield

        Returns:
            Dictionary of symbol -> price paths array
        """
        symbols = list(prices.keys())
        n_assets = len(symbols)

        if dividend_yields is None:
            dividend_yields = {s: 0.0 for s in symbols}

        # Generate correlated random numbers if correlation matrix provided
        if correlation_matrix is not None:
            # Cholesky decomposition for correlated sampling
            cholesky = np.linalg.cholesky(correlation_matrix)
            z_independent = self.rng.standard_normal(
                (self.config.num_paths, self.config.num_days, n_assets)
            )
            z_correlated = np.einsum('ijk,lk->ijl', z_independent, cholesky)
        else:
            z_correlated = self.rng.standard_normal(
                (self.config.num_paths, self.config.num_days, n_assets)
            )

        # Simulate each asset
        result = {}
        dt = 1 / 252

        for i, symbol in enumerate(symbols):
            price = prices[symbol]
            vol = volatilities[symbol]
            div = dividend_yields.get(symbol, 0.0)
            drift = self.config.risk_free_rate - div

            daily_drift = (drift - 0.5 * vol ** 2) * dt
            daily_vol = vol * np.sqrt(dt)

            log_returns = daily_drift + daily_vol * z_correlated[:, :, i]
            cumulative_returns = np.cumsum(log_returns, axis=1)

            paths = np.zeros((self.config.num_paths, self.config.num_days + 1))
            paths[:, 0] = price
            paths[:, 1:] = price * np.exp(cumulative_returns)

            result[symbol] = paths

            logger.debug(f"Simulated {symbol}: initial=${price:.2f}, final_mean=${paths[:, -1].mean():.2f}")

        return result

    def calculate_option_values(
        self,
        price_paths: np.ndarray,
        strike: float,
        is_call: bool,
        initial_dte: int,
        volatility: float,
        position_size: float,
        multiplier: int = 100
    ) -> np.ndarray:
        """
        Calculate option values along price paths

        Args:
            price_paths: Underlying price paths (num_paths, num_days + 1)
            strike: Option strike price
            is_call: True for call, False for put
            initial_dte: Initial days to expiration
            volatility: Implied volatility (assumed constant)
            position_size: Number of contracts (positive=long, negative=short)
            multiplier: Contract multiplier

        Returns:
            Option value paths (num_paths, num_days + 1)
        """
        num_paths, num_steps = price_paths.shape
        option_values = np.zeros_like(price_paths)

        for day in range(num_steps):
            dte = max(0, initial_dte - day)
            time_to_expiry = dte / 365.0

            if time_to_expiry <= 0:
                # At expiry - intrinsic value only
                if is_call:
                    intrinsic = np.maximum(price_paths[:, day] - strike, 0)
                else:
                    intrinsic = np.maximum(strike - price_paths[:, day], 0)
                option_values[:, day] = intrinsic * position_size * multiplier
            else:
                # Use Black-Scholes
                for path in range(num_paths):
                    spot = price_paths[path, day]
                    if is_call:
                        price = self.bs_model.call_price(
                            spot, strike, time_to_expiry,
                            self.config.risk_free_rate, volatility
                        )
                    else:
                        price = self.bs_model.put_price(
                            spot, strike, time_to_expiry,
                            self.config.risk_free_rate, volatility
                        )
                    option_values[path, day] = price * position_size * multiplier

        return option_values

    def simulate_portfolio(
        self,
        positions: List[Position],
        market_data: Optional[Dict[int, MarketData]] = None,
        correlation_matrix: Optional[np.ndarray] = None
    ) -> SimulationResult:
        """
        Simulate portfolio value over time

        Args:
            positions: List of Position objects
            market_data: Dictionary of conId -> MarketData
            correlation_matrix: Correlation matrix for underlying assets

        Returns:
            SimulationResult with all paths and statistics
        """
        logger.info(f"Starting portfolio simulation with {len(positions)} positions")

        # Group positions by underlying
        underlying_positions: Dict[str, List[Position]] = {}
        underlying_prices: Dict[str, float] = {}
        underlying_vols: Dict[str, float] = {}

        for pos in positions:
            symbol = pos.symbol
            if symbol not in underlying_positions:
                underlying_positions[symbol] = []
            underlying_positions[symbol].append(pos)

            # Get underlying price
            if symbol not in underlying_prices:
                if market_data and pos.con_id in market_data:
                    md = market_data[pos.con_id]
                    if pos.is_stock:
                        underlying_prices[symbol] = md.mid
                    elif md.underlying_price:
                        underlying_prices[symbol] = md.underlying_price
                    else:
                        underlying_prices[symbol] = pos.market_price or pos.avg_cost
                else:
                    underlying_prices[symbol] = pos.market_price or pos.avg_cost

            # Get volatility (use highest IV for the underlying)
            if symbol not in underlying_vols:
                underlying_vols[symbol] = 0.25  # Default

            if pos.is_option and market_data and pos.con_id in market_data:
                md = market_data[pos.con_id]
                if md.implied_volatility:
                    underlying_vols[symbol] = max(underlying_vols[symbol], md.implied_volatility)

        # Simulate underlying price paths
        logger.info(f"Simulating price paths for {len(underlying_prices)} underlyings")
        price_paths = self.simulate_correlated_prices(
            underlying_prices,
            underlying_vols,
            correlation_matrix
        )

        # Calculate initial portfolio value
        initial_value = sum(abs(pos.market_value) for pos in positions)

        # Initialize result arrays
        num_paths = self.config.num_paths
        num_days = self.config.num_days
        portfolio_paths = np.zeros((num_paths, num_days + 1))

        # Calculate portfolio value for each path and day
        logger.info("Calculating portfolio values along paths...")

        for symbol, symbol_positions in underlying_positions.items():
            symbol_paths = price_paths[symbol]

            for pos in symbol_positions:
                if pos.is_stock:
                    # Stock value = shares * price
                    stock_values = pos.position * symbol_paths
                    portfolio_paths += stock_values

                elif pos.is_option and pos.option_details:
                    opt = pos.option_details
                    option_values = self.calculate_option_values(
                        symbol_paths,
                        strike=opt.strike,
                        is_call=opt.is_call,
                        initial_dte=opt.days_to_expiry,
                        volatility=underlying_vols[symbol],
                        position_size=pos.position,
                        multiplier=opt.multiplier
                    )
                    portfolio_paths += option_values

        # Calculate final values and P&L
        final_values = portfolio_paths[:, -1]
        pnl = final_values - initial_value
        returns = pnl / initial_value if initial_value > 0 else np.zeros_like(pnl)

        # Calculate statistics
        statistics = self._calculate_statistics(
            portfolio_paths, initial_value, final_values, pnl, returns
        )

        # Calculate percentiles
        percentiles = PercentileResults.from_array(final_values)

        # Calculate daily statistics
        daily_mean = portfolio_paths.mean(axis=0).tolist()
        daily_std = portfolio_paths.std(axis=0).tolist()
        daily_var_95 = np.percentile(portfolio_paths, 5, axis=0).tolist()

        # Create result
        result = SimulationResult(
            config=self.config,
            initial_portfolio_value=initial_value,
            initial_prices=underlying_prices,
            price_paths_by_symbol={s: paths.tolist() for s, paths in price_paths.items()},
            portfolio_value_paths=portfolio_paths.tolist(),
            final_values=final_values.tolist(),
            pnl_distribution=pnl.tolist(),
            return_distribution=returns.tolist(),
            statistics=statistics,
            percentiles=percentiles,
            daily_mean=daily_mean,
            daily_std=daily_std,
            daily_var_95=daily_var_95
        )

        logger.info("=" * 60)
        logger.info("Monte Carlo Simulation Complete:")
        logger.info(f"  Initial Value: ${initial_value:,.2f}")
        logger.info(f"  Expected Final: ${statistics.mean:,.2f}")
        logger.info(f"  Expected P&L: ${statistics.mean - initial_value:,.2f}")
        logger.info(f"  Expected Return: {statistics.expected_return * 100:.2f}%")
        logger.info(f"  95% VaR: ${statistics.var_95:,.2f}")
        logger.info(f"  99% VaR: ${statistics.var_99:,.2f}")
        logger.info(f"  Max Drawdown: {statistics.max_drawdown * 100:.2f}%")
        logger.info(f"  Prob of Loss: {statistics.probability_loss * 100:.1f}%")
        logger.info(f"  Sharpe Ratio: {statistics.sharpe_ratio:.2f}")
        logger.info("=" * 60)

        return result

    def _calculate_statistics(
        self,
        portfolio_paths: np.ndarray,
        initial_value: float,
        final_values: np.ndarray,
        pnl: np.ndarray,
        returns: np.ndarray
    ) -> SimulationStatistics:
        """Calculate comprehensive statistics from simulation results"""

        # Basic statistics
        mean = float(np.mean(final_values))
        std = float(np.std(final_values))

        # VaR (Value at Risk) - loss at percentile
        var_95 = float(initial_value - np.percentile(final_values, 5))
        var_99 = float(initial_value - np.percentile(final_values, 1))

        # CVaR (Conditional VaR / Expected Shortfall)
        var_95_threshold = np.percentile(final_values, 5)
        var_99_threshold = np.percentile(final_values, 1)
        cvar_95 = float(initial_value - np.mean(final_values[final_values <= var_95_threshold]))
        cvar_99 = float(initial_value - np.mean(final_values[final_values <= var_99_threshold]))

        # Drawdown analysis
        drawdowns = []
        for path in portfolio_paths:
            running_max = np.maximum.accumulate(path)
            dd = (running_max - path) / running_max
            drawdowns.append(np.max(dd))

        max_drawdown = float(np.max(drawdowns))
        avg_drawdown = float(np.mean(drawdowns))

        # Probability metrics
        prob_loss = float(np.mean(pnl < 0))
        prob_gain = float(np.mean(pnl > 0))

        # Expected return
        expected_return = float(np.mean(returns))

        # Risk-adjusted returns
        # Sharpe Ratio (annualized)
        trading_days = self.config.num_days
        annualization_factor = np.sqrt(252 / trading_days)
        daily_returns = np.diff(portfolio_paths, axis=1) / portfolio_paths[:, :-1]
        avg_daily_return = np.mean(daily_returns)
        std_daily_return = np.std(daily_returns)

        if std_daily_return > 0:
            sharpe_ratio = float(avg_daily_return / std_daily_return * annualization_factor)
        else:
            sharpe_ratio = 0.0

        # Sortino Ratio (downside risk only)
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = float(avg_daily_return / downside_std * annualization_factor)
            else:
                sortino_ratio = 0.0
        else:
            sortino_ratio = float('inf') if avg_daily_return > 0 else 0.0

        # Higher moments
        skewness = float(scipy_stats.skew(pnl))
        kurtosis = float(scipy_stats.kurtosis(pnl))

        return SimulationStatistics(
            mean=mean,
            std=std,
            min_value=float(np.min(final_values)),
            max_value=float(np.max(final_values)),
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_drawdown=max_drawdown,
            avg_drawdown=avg_drawdown,
            probability_loss=prob_loss,
            probability_gain=prob_gain,
            expected_return=expected_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            skewness=skewness,
            kurtosis=kurtosis
        )

    def stress_test(
        self,
        positions: List[Position],
        market_data: Optional[Dict[int, MarketData]] = None,
        scenarios: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, SimulationResult]:
        """
        Run stress test scenarios

        Args:
            positions: List of positions
            market_data: Market data dictionary
            scenarios: Dictionary of scenario_name -> {symbol: price_shock}
                       e.g., {"market_crash": {"SPY": -0.20, "AAPL": -0.30}}

        Returns:
            Dictionary of scenario_name -> SimulationResult
        """
        if scenarios is None:
            # Default stress scenarios
            scenarios = {
                "market_crash_10pct": {"_all": -0.10},
                "market_crash_20pct": {"_all": -0.20},
                "market_rally_10pct": {"_all": 0.10},
                "volatility_spike": {"_vol_mult": 1.5},
                "volatility_collapse": {"_vol_mult": 0.5},
            }

        results = {}

        for scenario_name, adjustments in scenarios.items():
            logger.info(f"Running stress scenario: {scenario_name}")

            # Apply adjustments to market data
            adjusted_market_data = self._apply_scenario(market_data, adjustments)

            # Run simulation
            result = self.simulate_portfolio(positions, adjusted_market_data)
            results[scenario_name] = result

            logger.info(f"  Scenario {scenario_name}: E[P&L]=${result.statistics.mean - result.initial_portfolio_value:,.2f}")

        return results

    def _apply_scenario(
        self,
        market_data: Optional[Dict[int, MarketData]],
        adjustments: Dict[str, float]
    ) -> Dict[int, MarketData]:
        """Apply scenario adjustments to market data"""
        if market_data is None:
            return {}

        adjusted = {}
        all_shock = adjustments.get("_all", 0)
        vol_mult = adjustments.get("_vol_mult", 1.0)

        for con_id, md in market_data.items():
            new_md = md.model_copy()

            # Apply price shock
            symbol_shock = adjustments.get(md.symbol, all_shock)
            if symbol_shock != 0:
                factor = 1 + symbol_shock
                new_md.bid = md.bid * factor
                new_md.ask = md.ask * factor
                new_md.last = md.last * factor
                if md.underlying_price:
                    new_md.underlying_price = md.underlying_price * factor

            # Apply volatility adjustment
            if md.implied_volatility and vol_mult != 1.0:
                new_md.implied_volatility = md.implied_volatility * vol_mult

            adjusted[con_id] = new_md

        return adjusted
