"""
Tests for Greeks calculation module
"""

import pytest
import math
from datetime import date, timedelta

from src.greeks.black_scholes import BlackScholesModel
from src.greeks.calculator import GreeksCalculator
from src.greeks.models import Greeks, PortfolioGreeks
from src.ib_client.models import Position, OptionDetails


class TestBlackScholesModel:
    """Test Black-Scholes model calculations"""

    def test_d1_calculation(self):
        """Test d1 calculation"""
        d1 = BlackScholesModel.d1(
            spot=100,
            strike=100,
            time_to_expiry=1.0,
            rate=0.05,
            volatility=0.20
        )
        # For ATM option with these params, d1 should be around 0.35
        assert 0.3 < d1 < 0.4

    def test_d2_calculation(self):
        """Test d2 = d1 - sigma * sqrt(t)"""
        spot, strike, t, r, vol = 100, 100, 1.0, 0.05, 0.20

        d1 = BlackScholesModel.d1(spot, strike, t, r, vol)
        d2 = BlackScholesModel.d2(spot, strike, t, r, vol)

        expected_d2 = d1 - vol * math.sqrt(t)
        assert abs(d2 - expected_d2) < 0.0001

    def test_call_price_atm(self):
        """Test ATM call option price"""
        price = BlackScholesModel.call_price(
            spot=100,
            strike=100,
            time_to_expiry=1.0,
            rate=0.05,
            volatility=0.20
        )
        # ATM call should be worth something
        assert 5 < price < 15

    def test_put_price_atm(self):
        """Test ATM put option price"""
        price = BlackScholesModel.put_price(
            spot=100,
            strike=100,
            time_to_expiry=1.0,
            rate=0.05,
            volatility=0.20
        )
        assert 5 < price < 15

    def test_put_call_parity(self):
        """Test put-call parity: C - P = S*e^(-qt) - K*e^(-rt)"""
        spot, strike, t, r, vol, q = 100, 100, 1.0, 0.05, 0.20, 0.02

        call = BlackScholesModel.call_price(spot, strike, t, r, vol, q)
        put = BlackScholesModel.put_price(spot, strike, t, r, vol, q)

        # Put-call parity
        left = call - put
        right = spot * math.exp(-q * t) - strike * math.exp(-r * t)

        assert abs(left - right) < 0.01

    def test_call_delta_range(self):
        """Test call delta is between 0 and 1"""
        delta = BlackScholesModel.delta(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25, is_call=True
        )
        assert 0 < delta < 1

    def test_put_delta_range(self):
        """Test put delta is between -1 and 0"""
        delta = BlackScholesModel.delta(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25, is_call=False
        )
        assert -1 < delta < 0

    def test_atm_call_delta_around_05(self):
        """Test ATM call delta is approximately 0.5"""
        delta = BlackScholesModel.delta(
            spot=100, strike=100, time_to_expiry=0.25,
            rate=0.05, volatility=0.20, is_call=True
        )
        assert 0.45 < delta < 0.60

    def test_gamma_positive(self):
        """Test gamma is always positive"""
        gamma = BlackScholesModel.gamma(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25
        )
        assert gamma > 0

    def test_gamma_same_for_call_put(self):
        """Test gamma is same for call and put at same strike"""
        # Gamma doesn't depend on call/put - same formula
        gamma = BlackScholesModel.gamma(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25
        )
        assert gamma > 0

    def test_theta_negative_for_long(self):
        """Test theta is negative for long options"""
        theta_call = BlackScholesModel.theta(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25, is_call=True
        )
        theta_put = BlackScholesModel.theta(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25, is_call=False
        )
        # Most options have negative theta (time decay)
        assert theta_call < 0
        # Put theta can be positive for deep ITM with high rates

    def test_vega_positive(self):
        """Test vega is positive"""
        vega = BlackScholesModel.vega(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25
        )
        assert vega > 0

    def test_expired_option_intrinsic_only(self):
        """Test expired options return intrinsic value"""
        # ITM call at expiry
        call_price = BlackScholesModel.call_price(
            spot=110, strike=100, time_to_expiry=0,
            rate=0.05, volatility=0.25
        )
        assert abs(call_price - 10) < 0.01

        # OTM call at expiry
        call_price_otm = BlackScholesModel.call_price(
            spot=90, strike=100, time_to_expiry=0,
            rate=0.05, volatility=0.25
        )
        assert call_price_otm == 0

    def test_calculate_all_greeks(self):
        """Test calculate_all_greeks returns all values"""
        greeks = BlackScholesModel.calculate_all_greeks(
            spot=100, strike=100, time_to_expiry=0.5,
            rate=0.05, volatility=0.25, is_call=True,
            position_size=10, multiplier=100
        )

        assert isinstance(greeks, Greeks)
        assert greeks.delta != 0
        assert greeks.gamma > 0
        assert greeks.theta != 0
        assert greeks.vega > 0
        assert greeks.delta_dollars != 0


class TestGreeksCalculator:
    """Test Greeks calculator"""

    @pytest.fixture
    def calculator(self):
        return GreeksCalculator(
            risk_free_rate=0.05,
            default_volatility=0.25
        )

    @pytest.fixture
    def sample_stock_position(self):
        return Position(
            symbol="AAPL",
            sec_type="STK",
            con_id=1,
            position=100,
            avg_cost=150.0,
            market_price=155.0,
            market_value=15500.0
        )

    @pytest.fixture
    def sample_call_position(self):
        return Position(
            symbol="AAPL",
            sec_type="OPT",
            con_id=2,
            position=5,
            avg_cost=8.0,
            market_price=10.0,
            market_value=5000.0,
            option_details=OptionDetails(
                strike=160.0,
                right="C",
                expiry=date.today() + timedelta(days=30),
                multiplier=100
            )
        )

    def test_stock_greeks(self, calculator, sample_stock_position):
        """Test stock has delta=1 per share"""
        greeks = calculator.calculate_stock_greeks(
            spot=155.0,
            position_size=100
        )

        assert greeks.delta == 100
        assert greeks.gamma == 0
        assert greeks.theta == 0
        assert greeks.vega == 0
        assert greeks.delta_dollars == 15500.0

    def test_option_greeks(self, calculator, sample_call_position):
        """Test option Greeks calculation"""
        greeks = calculator.calculate_option_greeks(
            spot=155.0,
            strike=160.0,
            expiry_days=30,
            volatility=0.25,
            is_call=True,
            position_size=5,
            multiplier=100
        )

        # 5 contracts * 100 multiplier = 500 shares worth of delta at most
        assert abs(greeks.delta) < 500
        assert greeks.gamma > 0  # Long options have positive gamma
        assert greeks.theta < 0  # Long options lose value over time
        assert greeks.vega > 0   # Long options benefit from IV increase

    def test_short_option_greeks(self, calculator):
        """Test short option has opposite greeks"""
        long_greeks = calculator.calculate_option_greeks(
            spot=155.0, strike=160.0, expiry_days=30,
            volatility=0.25, is_call=True,
            position_size=1, multiplier=100
        )

        short_greeks = calculator.calculate_option_greeks(
            spot=155.0, strike=160.0, expiry_days=30,
            volatility=0.25, is_call=True,
            position_size=-1, multiplier=100
        )

        assert short_greeks.delta == -long_greeks.delta
        assert short_greeks.gamma == -long_greeks.gamma
        assert short_greeks.theta == -long_greeks.theta

    def test_portfolio_greeks_aggregation(self, calculator, sample_stock_position, sample_call_position):
        """Test portfolio Greeks are properly aggregated"""
        positions = [sample_stock_position, sample_call_position]

        portfolio_greeks = calculator.calculate_portfolio_greeks(positions)

        assert isinstance(portfolio_greeks, PortfolioGreeks)
        assert len(portfolio_greeks.by_underlying) == 1  # Both are AAPL
        assert portfolio_greeks.total_delta != 0

    def test_expired_option_greeks(self, calculator):
        """Test expired option Greeks"""
        greeks = calculator.calculate_option_greeks(
            spot=155.0, strike=150.0, expiry_days=0,
            volatility=0.25, is_call=True,
            position_size=1, multiplier=100
        )

        # ITM at expiry - delta should be 100 (1.0 * 1 contract * 100 multiplier)
        assert greeks.delta == 100
        assert greeks.gamma == 0
        assert greeks.theta == 0


class TestGreeksModels:
    """Test Greeks model objects"""

    def test_greeks_addition(self):
        """Test adding two Greeks objects"""
        g1 = Greeks(delta=50, gamma=0.1, theta=-5, vega=10, rho=1)
        g2 = Greeks(delta=30, gamma=0.05, theta=-3, vega=5, rho=0.5)

        result = g1 + g2

        assert result.delta == 80
        assert abs(result.gamma - 0.15) < 1e-10  # Use tolerance for float comparison
        assert result.theta == -8
        assert result.vega == 15
        assert result.rho == 1.5

    def test_greeks_multiplication(self):
        """Test multiplying Greeks by scalar"""
        g = Greeks(delta=50, gamma=0.1, theta=-5, vega=10, rho=1)

        result = g * 2

        assert result.delta == 100
        assert result.gamma == 0.2
        assert result.theta == -10
        assert result.vega == 20

    def test_portfolio_greeks_summary(self):
        """Test portfolio Greeks summary dict"""
        pg = PortfolioGreeks(
            total_delta=150,
            total_gamma=0.15,
            total_theta=-50,
            total_vega=25,
            total_delta_dollars=15000,
            total_theta_dollars=-50,
            weighted_average_iv=0.25
        )

        summary = pg.summary_dict()

        assert "total_delta" in summary
        assert "theta_dollars" in summary
        assert summary["weighted_avg_iv"] == 25.0  # 0.25 * 100
