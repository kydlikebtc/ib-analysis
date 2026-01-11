"""
Tests for IB Client module
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock

from src.ib_client.client import (
    IBClient,
    ConnectionState,
    ConnectionError,
    AuthenticationError,
    TimeoutError
)
from src.ib_client.models import (
    Position, AccountSummary, MarketData,
    OptionDetails, FuturesDetails, ForexDetails,
    BondDetails, CryptoDetails, FundDetails, SecType
)


class TestConnectionState:
    """Test ConnectionState enum"""

    def test_connection_states_exist(self):
        """Test all expected connection states exist"""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.ERROR.value == "error"


class TestConnectionExceptions:
    """Test custom exception classes"""

    def test_connection_error_inheritance(self):
        """Test ConnectionError is base Exception"""
        error = ConnectionError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_authentication_error_inheritance(self):
        """Test AuthenticationError inherits from ConnectionError"""
        error = AuthenticationError("auth failed")
        assert isinstance(error, ConnectionError)
        assert isinstance(error, Exception)

    def test_timeout_error_inheritance(self):
        """Test TimeoutError inherits from ConnectionError"""
        error = TimeoutError("timeout")
        assert isinstance(error, ConnectionError)


class TestIBClientInitialization:
    """Test IBClient initialization"""

    def test_default_initialization(self):
        """Test client initializes with defaults"""
        client = IBClient(simulation_mode=True)

        assert client.state == ConnectionState.DISCONNECTED
        assert client.last_error is None
        assert not client.is_connected
        assert client._max_reconnect_attempts == 3
        assert client._reconnect_delay == 2.0

    def test_custom_reconnect_params(self):
        """Test custom reconnection parameters"""
        client = IBClient(
            simulation_mode=True,
            max_reconnect_attempts=5,
            reconnect_delay=5.0
        )

        assert client._max_reconnect_attempts == 5
        assert client._reconnect_delay == 5.0


class TestIBClientStateManagement:
    """Test connection state management"""

    @pytest.fixture
    def client(self):
        return IBClient(simulation_mode=True)

    def test_state_property(self, client):
        """Test state property returns current state"""
        assert client.state == ConnectionState.DISCONNECTED

    def test_last_error_initially_none(self, client):
        """Test last_error is None initially"""
        assert client.last_error is None

    def test_set_state_updates_state(self, client):
        """Test _set_state updates the state"""
        client._set_state(ConnectionState.CONNECTING)
        assert client.state == ConnectionState.CONNECTING

    def test_set_state_with_error(self, client):
        """Test _set_state with error message"""
        client._set_state(ConnectionState.ERROR, "Test error")
        assert client.state == ConnectionState.ERROR
        assert client.last_error == "Test error"

    def test_state_change_callback(self, client):
        """Test state change callback is called"""
        callback_called = []

        def on_state_change(new_state):
            callback_called.append(new_state)

        client.on_state_change(on_state_change)
        client._set_state(ConnectionState.CONNECTING)

        assert len(callback_called) == 1
        assert callback_called[0] == ConnectionState.CONNECTING

    def test_error_callback(self, client):
        """Test error callback is called"""
        errors = []

        def on_error(msg):
            errors.append(msg)

        client.on_error(on_error)
        client._on_error("Test error")

        assert len(errors) == 1
        assert errors[0] == "Test error"


class TestIBClientConnection:
    """Test connection methods"""

    @pytest.fixture
    def client(self):
        return IBClient(simulation_mode=True)

    def test_connect_simulation_mode(self, client):
        """Test connect in simulation mode"""
        result = client.connect(port=7497)

        assert result is True
        assert client.state == ConnectionState.CONNECTED
        assert client.is_connected

    def test_connect_caches_params(self, client):
        """Test connect caches connection parameters"""
        client.connect(
            host="192.168.1.1",
            port=7496,
            client_id=5,
            timeout=60
        )

        assert client._connection_params["host"] == "192.168.1.1"
        assert client._connection_params["port"] == 7496
        assert client._connection_params["client_id"] == 5
        assert client._connection_params["timeout"] == 60

    def test_disconnect_simulation_mode(self, client):
        """Test disconnect in simulation mode"""
        client.connect()
        client.disconnect()

        assert client.state == ConnectionState.DISCONNECTED
        assert not client.is_connected

    def test_disconnect_resets_reconnect_attempts(self, client):
        """Test disconnect resets reconnect counter"""
        client.connect()
        client._reconnect_attempts = 2
        client.disconnect()

        assert client._reconnect_attempts == 0


class TestIBClientReconnection:
    """Test reconnection logic"""

    @pytest.fixture
    def client(self):
        client = IBClient(
            simulation_mode=True,
            max_reconnect_attempts=3,
            reconnect_delay=0.01  # Fast for tests
        )
        # Pre-connect to cache params
        client.connect(port=7497)
        client.disconnect()
        return client

    def test_reconnect_without_cached_params(self):
        """Test reconnect fails without cached params"""
        client = IBClient(simulation_mode=True)
        result = client.reconnect()
        assert result is False

    def test_reconnect_success(self, client):
        """Test successful reconnection"""
        result = client.reconnect()

        assert result is True
        assert client.state == ConnectionState.CONNECTED

    def test_reconnect_increments_attempts(self, client):
        """Test reconnect increments attempt counter"""
        client.reconnect()
        assert client._reconnect_attempts == 1

    def test_reconnect_max_attempts_reached(self, client):
        """Test reconnect fails after max attempts"""
        client._reconnect_attempts = 3

        result = client.reconnect()

        assert result is False
        assert client.state == ConnectionState.ERROR

    def test_ensure_connected_when_connected(self, client):
        """Test ensure_connected returns True when already connected"""
        client.connect()
        assert client.ensure_connected() is True

    def test_ensure_connected_triggers_reconnect(self, client):
        """Test ensure_connected triggers reconnect when disconnected"""
        result = client.ensure_connected()
        assert result is True
        assert client.state == ConnectionState.CONNECTED


class TestIBClientSimulation:
    """Test simulation mode data"""

    @pytest.fixture
    def connected_client(self):
        client = IBClient(simulation_mode=True)
        client.connect()
        return client

    def test_get_simulated_positions(self, connected_client):
        """Test getting simulated positions"""
        positions = connected_client.get_positions()

        assert len(positions) > 0
        assert all(isinstance(p, Position) for p in positions)

    def test_simulated_positions_have_required_fields(self, connected_client):
        """Test simulated positions have required fields"""
        positions = connected_client.get_positions()

        for pos in positions:
            assert pos.symbol is not None
            assert pos.sec_type is not None
            assert pos.position != 0

    def test_get_simulated_account_summary(self, connected_client):
        """Test getting simulated account summary"""
        summary = connected_client.get_account_summary()

        assert summary is not None
        assert isinstance(summary, AccountSummary)
        assert summary.net_liquidation > 0

    def test_get_simulated_market_data(self, connected_client):
        """Test getting simulated market data"""
        positions = connected_client.get_positions()
        market_data = connected_client.get_market_data(positions)

        assert len(market_data) > 0
        for con_id, md in market_data.items():
            assert isinstance(md, MarketData)
            assert md.last > 0 or md.bid > 0


class TestPositionConversion:
    """Test IB position conversion"""

    @pytest.fixture
    def client(self):
        return IBClient(simulation_mode=True)

    def test_parse_option_details(self, client):
        """Test parsing option contract details"""
        mock_contract = Mock()
        mock_contract.strike = 150.0
        mock_contract.right = "C"
        mock_contract.lastTradeDateOrContractMonth = "20260221"
        mock_contract.multiplier = "100"

        details = client._parse_option_details(mock_contract)

        assert details is not None
        assert details.strike == 150.0
        assert details.right == "C"
        assert details.expiry == date(2026, 2, 21)
        assert details.multiplier == 100

    def test_parse_futures_details(self, client):
        """Test parsing futures contract details"""
        mock_contract = Mock()
        mock_contract.lastTradeDateOrContractMonth = "202603"
        mock_contract.multiplier = "50"
        mock_contract.underSymbol = None

        details = client._parse_futures_details(mock_contract)

        assert details is not None
        assert details.expiry.year == 2026
        assert details.expiry.month == 3
        assert details.multiplier == 50.0

    def test_parse_forex_details(self, client):
        """Test parsing forex pair details"""
        mock_contract = Mock()
        mock_contract.symbol = "EUR"
        mock_contract.currency = "USD"

        details = client._parse_forex_details(mock_contract)

        assert details is not None
        assert details.base_currency == "EUR"
        assert details.quote_currency == "USD"

    def test_parse_crypto_details(self, client):
        """Test parsing crypto details"""
        mock_contract = Mock()
        mock_contract.symbol = "BTC"
        mock_contract.currency = "USD"

        details = client._parse_crypto_details(mock_contract)

        assert details is not None
        assert details.base_currency == "BTC"
        assert details.quote_currency == "USD"

    def test_parse_fund_details(self, client):
        """Test parsing fund details"""
        mock_contract = Mock()
        mock_contract.secIdType = None
        mock_contract.symbol = "SPY"

        details = client._parse_fund_details(mock_contract)

        assert details is not None
        assert details.fund_type == "ETF"


class TestSecType:
    """Test SecType constants"""

    def test_sec_type_values(self):
        """Test SecType constant values"""
        assert SecType.STOCK == "STK"
        assert SecType.OPTION == "OPT"
        assert SecType.FUTURES == "FUT"
        assert SecType.FOREX == "CASH"
        assert SecType.BOND == "BOND"
        assert SecType.CFD == "CFD"
        assert SecType.FUT_OPT == "FOP"
        assert SecType.WARRANT == "WAR"
        assert SecType.FUND == "FUND"
        assert SecType.CRYPTO == "CRYPTO"

    def test_sec_type_display_name(self):
        """Test SecType display names"""
        assert SecType.display_name(SecType.STOCK) == "股票"
        assert SecType.display_name(SecType.OPTION) == "期权"
        assert SecType.display_name(SecType.FUTURES) == "期货"
        assert SecType.display_name(SecType.CRYPTO) == "加密货币"

    def test_sec_type_all_types(self):
        """Test all_types returns list of all supported types"""
        all_types = SecType.all_types()
        assert isinstance(all_types, list)
        assert SecType.STOCK in all_types
        assert SecType.OPTION in all_types
        assert len(all_types) >= 10


class TestPositionModel:
    """Test Position model"""

    def test_stock_position_creation(self):
        """Test creating stock position"""
        pos = Position(
            symbol="AAPL",
            sec_type="STK",
            con_id=12345,
            position=100,
            avg_cost=150.0,
            market_price=155.0,
            market_value=15500.0
        )

        assert pos.symbol == "AAPL"
        assert pos.sec_type == "STK"
        assert pos.is_option is False
        assert pos.is_long is True

    def test_option_position_creation(self):
        """Test creating option position"""
        pos = Position(
            symbol="AAPL",
            sec_type="OPT",
            con_id=12346,
            position=5,
            avg_cost=5.0,
            market_value=2500.0,
            option_details=OptionDetails(
                strike=160.0,
                right="C",
                expiry=date(2026, 2, 21),
                multiplier=100
            )
        )

        assert pos.is_option is True
        assert pos.option_details is not None
        assert pos.option_details.is_call is True

    def test_short_position(self):
        """Test short position detection"""
        pos = Position(
            symbol="AAPL",
            sec_type="OPT",
            con_id=12347,
            position=-2,
            avg_cost=10.0,
            market_value=-2000.0,
            option_details=OptionDetails(
                strike=150.0,
                right="P",
                expiry=date(2026, 1, 31),
                multiplier=100
            )
        )

        assert pos.is_long is False
        assert pos.option_details.is_call is False

    def test_position_unrealized_pnl(self):
        """Test unrealized PnL calculation"""
        pos = Position(
            symbol="AAPL",
            sec_type="STK",
            con_id=12345,
            position=100,
            avg_cost=150.0,
            market_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0
        )

        assert pos.unrealized_pnl == 500.0


class TestAccountSummary:
    """Test AccountSummary model"""

    def test_account_summary_creation(self):
        """Test creating account summary"""
        summary = AccountSummary(
            account_id="DU123456",
            net_liquidation=150000.0,
            total_cash=50000.0,
            buying_power=100000.0
        )

        assert summary.account_id == "DU123456"
        assert summary.net_liquidation == 150000.0

    def test_account_summary_margin_available(self):
        """Test margin availability calculation"""
        summary = AccountSummary(
            account_id="DU123456",
            net_liquidation=150000.0,
            buying_power=100000.0,
            maintenance_margin=25000.0
        )

        assert summary.buying_power == 100000.0
        assert summary.maintenance_margin == 25000.0
