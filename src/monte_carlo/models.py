"""
Data models for Monte Carlo simulation
"""

from typing import Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class SimulationConfig(BaseModel):
    """Configuration for Monte Carlo simulation"""
    num_paths: int = Field(default=10000, ge=100, le=1000000)
    num_days: int = Field(default=30, ge=1, le=365)
    random_seed: Optional[int] = Field(default=None)
    risk_free_rate: float = Field(default=0.05)
    use_antithetic: bool = Field(default=True, description="Use antithetic variates for variance reduction")
    use_control_variate: bool = Field(default=False)


class PercentileResults(BaseModel):
    """Percentile distribution of simulation results"""
    p1: float = Field(description="1st percentile")
    p5: float = Field(description="5th percentile")
    p10: float = Field(description="10th percentile")
    p25: float = Field(description="25th percentile (Q1)")
    p50: float = Field(description="50th percentile (median)")
    p75: float = Field(description="75th percentile (Q3)")
    p90: float = Field(description="90th percentile")
    p95: float = Field(description="95th percentile")
    p99: float = Field(description="99th percentile")

    @classmethod
    def from_array(cls, values: np.ndarray) -> "PercentileResults":
        """Create from numpy array"""
        return cls(
            p1=float(np.percentile(values, 1)),
            p5=float(np.percentile(values, 5)),
            p10=float(np.percentile(values, 10)),
            p25=float(np.percentile(values, 25)),
            p50=float(np.percentile(values, 50)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99))
        )

    def to_dict(self) -> Dict[int, float]:
        return {
            1: self.p1,
            5: self.p5,
            10: self.p10,
            25: self.p25,
            50: self.p50,
            75: self.p75,
            90: self.p90,
            95: self.p95,
            99: self.p99
        }


class SimulationStatistics(BaseModel):
    """Statistical summary of simulation results"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mean: float = Field(description="Mean final value")
    std: float = Field(description="Standard deviation")
    min_value: float = Field(description="Minimum value")
    max_value: float = Field(description="Maximum value")
    var_95: float = Field(description="95% Value at Risk (loss at 5th percentile)")
    var_99: float = Field(description="99% Value at Risk (loss at 1st percentile)")
    cvar_95: float = Field(description="95% Conditional VaR (Expected Shortfall)")
    cvar_99: float = Field(description="99% Conditional VaR")
    max_drawdown: float = Field(description="Maximum drawdown observed")
    avg_drawdown: float = Field(description="Average drawdown")
    probability_loss: float = Field(description="Probability of loss (0-1)")
    probability_gain: float = Field(description="Probability of gain (0-1)")
    expected_return: float = Field(description="Expected return percentage")
    sharpe_ratio: float = Field(description="Annualized Sharpe ratio")
    sortino_ratio: float = Field(description="Sortino ratio (downside risk)")
    skewness: float = Field(description="Distribution skewness")
    kurtosis: float = Field(description="Distribution kurtosis")


class SimulationResult(BaseModel):
    """Complete results of Monte Carlo simulation"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Configuration used
    config: SimulationConfig = Field(default_factory=SimulationConfig)

    # Initial values
    initial_portfolio_value: float = Field(default=0.0)
    initial_prices: Dict[str, float] = Field(default_factory=dict)

    # Price paths (stored as list for JSON serialization, convert to numpy for computation)
    price_paths_by_symbol: Dict[str, List[List[float]]] = Field(
        default_factory=dict,
        description="Price paths by symbol: symbol -> [num_paths][num_days]"
    )

    # Portfolio value paths
    portfolio_value_paths: List[List[float]] = Field(
        default_factory=list,
        description="Portfolio value paths: [num_paths][num_days]"
    )

    # Final values distribution
    final_values: List[float] = Field(
        default_factory=list,
        description="Final portfolio values across all paths"
    )

    # P&L distribution
    pnl_distribution: List[float] = Field(
        default_factory=list,
        description="P&L for each path"
    )

    # Return distribution
    return_distribution: List[float] = Field(
        default_factory=list,
        description="Percentage return for each path"
    )

    # Statistics
    statistics: Optional[SimulationStatistics] = None

    # Percentiles
    percentiles: Optional[PercentileResults] = None

    # Daily statistics
    daily_mean: List[float] = Field(default_factory=list)
    daily_std: List[float] = Field(default_factory=list)
    daily_var_95: List[float] = Field(default_factory=list)

    def get_price_paths_array(self, symbol: str) -> np.ndarray:
        """Get price paths as numpy array"""
        if symbol in self.price_paths_by_symbol:
            return np.array(self.price_paths_by_symbol[symbol])
        return np.array([])

    def get_portfolio_paths_array(self) -> np.ndarray:
        """Get portfolio value paths as numpy array"""
        return np.array(self.portfolio_value_paths)

    def get_final_values_array(self) -> np.ndarray:
        """Get final values as numpy array"""
        return np.array(self.final_values)

    def get_pnl_array(self) -> np.ndarray:
        """Get P&L as numpy array"""
        return np.array(self.pnl_distribution)

    def summary(self) -> Dict:
        """Get summary dictionary"""
        if self.statistics is None:
            return {}

        stats = self.statistics
        return {
            "initial_value": round(self.initial_portfolio_value, 2),
            "expected_final_value": round(stats.mean, 2),
            "expected_pnl": round(stats.mean - self.initial_portfolio_value, 2),
            "expected_return_pct": round(stats.expected_return * 100, 2),
            "std_dev": round(stats.std, 2),
            "var_95": round(stats.var_95, 2),
            "var_99": round(stats.var_99, 2),
            "cvar_95": round(stats.cvar_95, 2),
            "max_drawdown_pct": round(stats.max_drawdown * 100, 2),
            "prob_loss_pct": round(stats.probability_loss * 100, 1),
            "prob_gain_pct": round(stats.probability_gain * 100, 1),
            "sharpe_ratio": round(stats.sharpe_ratio, 2),
            "best_case_p95": round(self.percentiles.p95, 2) if self.percentiles else 0,
            "worst_case_p5": round(self.percentiles.p5, 2) if self.percentiles else 0,
        }
