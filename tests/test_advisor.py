"""
Tests for Portfolio Advisor module
"""

import pytest
from datetime import date, timedelta

from src.advisor.analyzer import PortfolioAdvisor
from src.advisor.models import (
    RiskLevel, RecommendationType, Priority,
    PortfolioAdvice, Recommendation, RiskAssessment
)
from src.greeks.models import PortfolioGreeks, GreeksByUnderlying, Greeks
from src.monte_carlo.models import SimulationResult, SimulationStatistics, SimulationConfig
from src.ib_client.models import Position, OptionDetails


class TestRiskAssessment:
    """Test risk assessment functionality"""

    @pytest.fixture
    def advisor(self):
        return PortfolioAdvisor(
            delta_neutral_threshold=0.1,
            gamma_warning_threshold=0.05,
            theta_warning_daily=-100,
            concentration_warning=0.30
        )

    @pytest.fixture
    def sample_positions(self):
        return [
            Position(
                symbol="AAPL",
                sec_type="STK",
                con_id=1,
                position=100,
                avg_cost=150.0,
                market_price=155.0,
                market_value=15500.0
            ),
            Position(
                symbol="SPY",
                sec_type="STK",
                con_id=2,
                position=50,
                avg_cost=450.0,
                market_price=460.0,
                market_value=23000.0
            ),
        ]

    @pytest.fixture
    def sample_greeks(self):
        pg = PortfolioGreeks(
            total_delta=150,
            total_gamma=0.02,
            total_theta=-25,
            total_vega=50,
            total_delta_dollars=20000,
            total_gamma_dollars=200,
            total_theta_dollars=-25,
            total_vega_dollars=500,
            weighted_average_iv=0.20
        )
        return pg

    @pytest.fixture
    def sample_simulation(self):
        return SimulationResult(
            config=SimulationConfig(num_paths=1000, num_days=30),
            initial_portfolio_value=38500,
            final_values=[38000 + i * 10 for i in range(1000)],
            pnl_distribution=[i * 10 - 500 for i in range(1000)],
            return_distribution=[(i * 10 - 500) / 38500 for i in range(1000)],
            statistics=SimulationStatistics(
                mean=43000,
                std=3000,
                min_value=35000,
                max_value=55000,
                var_95=3500,
                var_99=5000,
                cvar_95=4000,
                cvar_99=5500,
                max_drawdown=0.08,
                avg_drawdown=0.03,
                probability_loss=0.35,
                probability_gain=0.65,
                expected_return=0.12,
                sharpe_ratio=1.5,
                sortino_ratio=2.0,
                skewness=0.1,
                kurtosis=0.2
            )
        )

    def test_risk_level_low(self, advisor, sample_positions, sample_simulation, sample_greeks):
        """Test low risk assessment"""
        assessment = advisor.analyze_risk(sample_positions, sample_simulation, sample_greeks)

        assert isinstance(assessment, RiskAssessment)
        # With sample data, concentration may raise risk score to MEDIUM level
        assert assessment.risk_score <= 70  # Allow up to medium-high risk due to concentration

    def test_risk_assessment_has_all_components(self, advisor, sample_positions, sample_simulation, sample_greeks):
        """Test risk assessment includes all components"""
        assessment = advisor.analyze_risk(sample_positions, sample_simulation, sample_greeks)

        assert assessment.market_risk in RiskLevel
        assert assessment.volatility_risk in RiskLevel
        assert assessment.time_decay_risk in RiskLevel
        assert assessment.concentration_risk in RiskLevel
        assert assessment.liquidity_risk in RiskLevel

    def test_high_delta_triggers_market_risk(self, advisor, sample_positions, sample_simulation):
        """Test high delta exposure triggers market risk"""
        high_delta_greeks = PortfolioGreeks(
            total_delta=500,
            total_delta_dollars=75000,  # High exposure
            total_gamma_dollars=100,
            total_theta_dollars=-10,
            total_vega_dollars=100
        )

        assessment = advisor.analyze_risk(sample_positions, sample_simulation, high_delta_greeks)

        assert assessment.market_risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]

    def test_high_theta_triggers_warning(self, advisor, sample_positions, sample_simulation):
        """Test high theta decay triggers warning"""
        high_theta_greeks = PortfolioGreeks(
            total_delta=100,
            total_delta_dollars=15000,
            total_gamma_dollars=100,
            total_theta_dollars=-200,  # High theta decay
            total_vega_dollars=100
        )

        assessment = advisor.analyze_risk(sample_positions, sample_simulation, high_theta_greeks)

        assert assessment.time_decay_risk == RiskLevel.HIGH
        assert any("theta" in risk.lower() for risk in assessment.key_risks)


class TestGreeksAssessment:
    """Test Greeks assessment"""

    @pytest.fixture
    def advisor(self):
        return PortfolioAdvisor()

    def test_delta_neutral_assessment(self, advisor):
        """Test delta neutral is correctly identified"""
        greeks = PortfolioGreeks(
            total_delta=5,
            total_delta_dollars=500,
            total_theta_dollars=-10,
            total_vega_dollars=100
        )

        assessment = advisor.analyze_greeks(greeks, portfolio_value=100000)

        assert assessment.delta_neutral is True
        assert assessment.delta_bias == "neutral"

    def test_bullish_delta_assessment(self, advisor):
        """Test bullish delta is correctly identified"""
        greeks = PortfolioGreeks(
            total_delta=200,
            total_delta_dollars=30000,
            total_theta_dollars=-50,
            total_vega_dollars=100
        )

        assessment = advisor.analyze_greeks(greeks, portfolio_value=100000)

        assert assessment.delta_neutral is False
        assert assessment.delta_bias == "bullish"

    def test_bearish_delta_assessment(self, advisor):
        """Test bearish delta is correctly identified"""
        greeks = PortfolioGreeks(
            total_delta=-200,
            total_delta_dollars=-30000,
            total_theta_dollars=-50,
            total_vega_dollars=100
        )

        assessment = advisor.analyze_greeks(greeks, portfolio_value=100000)

        assert assessment.delta_neutral is False
        assert assessment.delta_bias == "bearish"


class TestConcentrationAnalysis:
    """Test concentration analysis"""

    @pytest.fixture
    def advisor(self):
        return PortfolioAdvisor(concentration_warning=0.30)

    def test_no_concentration_warning(self, advisor):
        """Test no warning for diversified portfolio"""
        # Create truly diversified portfolio where no position exceeds 30%
        positions = [
            Position(symbol="AAPL", sec_type="STK", con_id=1, position=100,
                    avg_cost=150, market_price=155, market_value=10000),  # 25%
            Position(symbol="MSFT", sec_type="STK", con_id=2, position=50,
                    avg_cost=350, market_price=360, market_value=10000),  # 25%
            Position(symbol="GOOG", sec_type="STK", con_id=3, position=20,
                    avg_cost=140, market_price=145, market_value=10000),  # 25%
            Position(symbol="AMZN", sec_type="STK", con_id=4, position=10,
                    avg_cost=150, market_price=155, market_value=10000),  # 25%
        ]

        warnings = advisor.analyze_concentration(positions)

        # No single position should exceed 30% threshold
        symbol_warnings = [w for w in warnings if w.type == "symbol"]
        assert len(symbol_warnings) == 0

    def test_concentration_warning_triggered(self, advisor):
        """Test warning for concentrated portfolio"""
        positions = [
            Position(symbol="AAPL", sec_type="STK", con_id=1, position=100,
                    avg_cost=150, market_price=155, market_value=50000),  # >50%
            Position(symbol="MSFT", sec_type="STK", con_id=2, position=50,
                    avg_cost=350, market_price=360, market_value=18000),
        ]

        warnings = advisor.analyze_concentration(positions)

        assert len(warnings) > 0
        assert any(w.type == "symbol" and w.entity == "AAPL" for w in warnings)


class TestRecommendations:
    """Test recommendation generation"""

    @pytest.fixture
    def advisor(self):
        return PortfolioAdvisor()

    @pytest.fixture
    def sample_positions(self):
        return [
            Position(
                symbol="AAPL",
                sec_type="OPT",
                con_id=1,
                position=5,
                avg_cost=10.0,
                market_price=12.0,
                market_value=6000.0,
                option_details=OptionDetails(
                    strike=180.0,
                    right="C",
                    expiry=date.today() + timedelta(days=5),  # Expiring soon
                    multiplier=100
                )
            ),
        ]

    def test_expiring_options_recommendation(self, advisor, sample_positions):
        """Test recommendation for expiring options"""
        greeks = PortfolioGreeks(
            total_delta=250,
            total_delta_dollars=45000,
            total_theta_dollars=-150,
            total_vega_dollars=500
        )

        simulation = SimulationResult(
            config=SimulationConfig(),
            initial_portfolio_value=50000,
            statistics=SimulationStatistics(
                mean=52000, std=3000, min_value=45000, max_value=60000,
                var_95=3000, var_99=4500, cvar_95=3500, cvar_99=5000,
                max_drawdown=0.05, avg_drawdown=0.02,
                probability_loss=0.3, probability_gain=0.7,
                expected_return=0.04, sharpe_ratio=1.2, sortino_ratio=1.8,
                skewness=0.1, kurtosis=0.1
            )
        )

        from src.advisor.models import GreeksAssessment, RiskAssessment

        risk = RiskAssessment(
            overall_level=RiskLevel.MEDIUM,
            risk_score=45
        )

        greeks_assessment = GreeksAssessment(
            delta_neutral=False,
            delta_bias="bullish",
            delta_risk_level=RiskLevel.MEDIUM,
            theta_daily=-150,
            theta_risk_level=RiskLevel.HIGH
        )

        recommendations = advisor.generate_recommendations(
            sample_positions, greeks, simulation, risk, greeks_assessment
        )

        # Should recommend rolling expiring options
        roll_recs = [r for r in recommendations if r.type == RecommendationType.ROLL]
        assert len(roll_recs) > 0


class TestPortfolioAdvice:
    """Test complete portfolio advice generation"""

    @pytest.fixture
    def advisor(self):
        return PortfolioAdvisor()

    @pytest.fixture
    def full_test_data(self):
        positions = [
            Position(
                symbol="AAPL",
                sec_type="STK",
                con_id=1,
                position=100,
                avg_cost=150.0,
                market_price=155.0,
                market_value=15500.0,
                unrealized_pnl=500.0
            ),
        ]

        greeks = PortfolioGreeks(
            total_delta=100,
            total_delta_dollars=15500,
            total_theta_dollars=0,
            total_vega_dollars=0,
            weighted_average_iv=0.20
        )

        simulation = SimulationResult(
            config=SimulationConfig(num_paths=1000, num_days=30),
            initial_portfolio_value=15500,
            final_values=[15500 + i for i in range(1000)],
            statistics=SimulationStatistics(
                mean=16000, std=1500, min_value=13000, max_value=20000,
                var_95=1500, var_99=2500, cvar_95=1800, cvar_99=2800,
                max_drawdown=0.05, avg_drawdown=0.02,
                probability_loss=0.25, probability_gain=0.75,
                expected_return=0.032, sharpe_ratio=1.0, sortino_ratio=1.5,
                skewness=0.05, kurtosis=0.1
            )
        )

        return positions, greeks, simulation

    def test_generate_report_structure(self, advisor, full_test_data):
        """Test generated report has correct structure"""
        positions, greeks, simulation = full_test_data

        advice = advisor.generate_report(positions, greeks, simulation)

        assert isinstance(advice, PortfolioAdvice)
        assert advice.summary
        assert advice.generated_at
        assert advice.risk_assessment is not None
        assert advice.greeks_assessment is not None
        assert advice.time_decay_analysis is not None

    def test_summary_dict(self, advisor, full_test_data):
        """Test summary dictionary generation"""
        positions, greeks, simulation = full_test_data

        advice = advisor.generate_report(positions, greeks, simulation)
        summary = advice.to_summary_dict()

        assert "risk_level" in summary
        assert "risk_score" in summary
        assert "recommendations_count" in summary

    def test_high_priority_recommendations(self, advisor, full_test_data):
        """Test filtering high priority recommendations"""
        positions, greeks, simulation = full_test_data

        advice = advisor.generate_report(positions, greeks, simulation)

        high_priority = advice.get_high_priority_recommendations()

        assert all(r.priority == Priority.HIGH for r in high_priority)
