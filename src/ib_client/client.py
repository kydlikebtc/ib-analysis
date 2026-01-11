"""
IB Client - Main client class for Interactive Brokers API
"""

import asyncio
import time
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from loguru import logger

try:
    from ib_insync import IB, Contract, util
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    logger.warning("ib_insync not installed. Using simulation mode.")

from .models import (
    Position, AccountSummary, MarketData,
    OptionDetails, FuturesDetails, ForexDetails,
    BondDetails, CryptoDetails, FundDetails, SecType
)


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class ConnectionError(Exception):
    """连接错误基类"""
    pass


class AuthenticationError(ConnectionError):
    """认证错误"""
    pass


class TimeoutError(ConnectionError):
    """超时错误"""
    pass


class IBClient:
    """
    Interactive Brokers API Client

    Provides methods to connect to IB TWS/Gateway, retrieve positions,
    account data, and market data.
    """

    def __init__(
        self,
        simulation_mode: bool = False,
        max_reconnect_attempts: int = 3,
        reconnect_delay: float = 2.0
    ):
        """
        Initialize IB Client

        Args:
            simulation_mode: If True, use simulated data instead of real IB connection
            max_reconnect_attempts: Maximum number of reconnection attempts
            reconnect_delay: Base delay between reconnection attempts (exponential backoff)
        """
        self._ib: Optional[Any] = None
        self._simulation_mode = simulation_mode or not IB_INSYNC_AVAILABLE
        self._account_id: str = ""
        self._positions_cache: List[Position] = []
        self._market_data_cache: Dict[int, MarketData] = {}

        # 连接状态管理
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._last_error: Optional[str] = None
        self._reconnect_attempts: int = 0
        self._max_reconnect_attempts: int = max_reconnect_attempts
        self._reconnect_delay: float = reconnect_delay

        # 连接参数缓存 (用于重连)
        self._connection_params: Dict[str, Any] = {}

        # 回调函数
        self._on_state_change: Optional[Callable[[ConnectionState], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None

        if self._simulation_mode:
            logger.info("IBClient initialized in SIMULATION mode")
        else:
            logger.info("IBClient initialized for real IB connection")

    @property
    def state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._state

    @property
    def last_error(self) -> Optional[str]:
        """获取最后一次错误信息"""
        return self._last_error

    def _set_state(self, new_state: ConnectionState, error_msg: Optional[str] = None) -> None:
        """更新连接状态"""
        old_state = self._state
        self._state = new_state
        if error_msg:
            self._last_error = error_msg
            logger.error(f"Connection state: {old_state.value} -> {new_state.value}, error: {error_msg}")
        else:
            logger.info(f"Connection state: {old_state.value} -> {new_state.value}")

        if self._on_state_change:
            try:
                self._on_state_change(new_state)
            except Exception as e:
                logger.warning(f"Error in state change callback: {e}")

    def on_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """设置状态变化回调"""
        self._on_state_change = callback

    def on_error(self, callback: Callable[[str], None]) -> None:
        """设置错误回调"""
        self._on_error = callback

    @property
    def is_connected(self) -> bool:
        """Check if connected to IB"""
        if self._simulation_mode:
            return self._state == ConnectionState.CONNECTED
        return self._ib is not None and self._ib.isConnected()

    def connect(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        timeout: int = 30,
        readonly: bool = True,
        account: str = ""
    ) -> bool:
        """
        Connect to IB TWS or Gateway

        Args:
            host: IB host address
            port: IB port (7497=TWS Paper, 7496=TWS Live, 4001=Gateway Paper, 4002=Gateway Live)
            client_id: Client ID for connection
            timeout: Connection timeout in seconds
            readonly: If True, connect in read-only mode
            account: Account ID to use (empty for default)

        Returns:
            True if connected successfully
        """
        # 缓存连接参数用于重连
        self._connection_params = {
            "host": host,
            "port": port,
            "client_id": client_id,
            "timeout": timeout,
            "readonly": readonly,
            "account": account
        }

        if self._simulation_mode:
            logger.info(f"Simulation mode: Simulating connection to {host}:{port}")
            self._set_state(ConnectionState.CONNECTED)
            self._account_id = account or "DU1234567"
            logger.info(f"Connected to simulated account: {self._account_id}")
            return True

        self._set_state(ConnectionState.CONNECTING)

        try:
            logger.info(f"Connecting to IB at {host}:{port} with client_id={client_id}")

            self._ib = IB()
            self._ib.connect(
                host=host,
                port=port,
                clientId=client_id,
                timeout=timeout,
                readonly=readonly,
                account=account
            )

            accounts = self._ib.managedAccounts()
            self._account_id = account if account else accounts[0] if accounts else ""

            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempts = 0  # 重置重连计数
            logger.info(f"Successfully connected to IB. Account: {self._account_id}")
            logger.debug(f"Available accounts: {accounts}")

            return True

        except Exception as e:
            error_msg = f"Failed to connect to IB: {e}"
            self._set_state(ConnectionState.ERROR, error_msg)

            # 触发错误回调
            if self._on_error:
                try:
                    self._on_error(error_msg)
                except Exception as cb_error:
                    logger.warning(f"Error in error callback: {cb_error}")

            return False

    def reconnect(self) -> bool:
        """
        尝试重新连接到 IB

        使用缓存的连接参数和指数退避策略进行重连

        Returns:
            True if reconnected successfully
        """
        if not self._connection_params:
            logger.error("No cached connection parameters. Call connect() first.")
            return False

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            error_msg = f"Max reconnection attempts ({self._max_reconnect_attempts}) reached"
            self._set_state(ConnectionState.ERROR, error_msg)
            logger.error(error_msg)
            return False

        self._reconnect_attempts += 1
        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))

        logger.info(
            f"Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts} "
            f"in {delay:.1f}s..."
        )
        self._set_state(ConnectionState.RECONNECTING)

        # 等待后重试
        time.sleep(delay)

        # 使用缓存的参数重新连接
        return self.connect(**self._connection_params)

    def disconnect(self) -> None:
        """Disconnect from IB"""
        if self._simulation_mode:
            logger.info("Simulation mode: Disconnecting")
            self._set_state(ConnectionState.DISCONNECTED)
            self._reconnect_attempts = 0  # 重置重连计数
            return

        if self._ib and self._ib.isConnected():
            logger.info("Disconnecting from IB...")
            self._ib.disconnect()
            logger.info("Disconnected from IB")

        self._set_state(ConnectionState.DISCONNECTED)
        self._reconnect_attempts = 0  # 重置重连计数

    def ensure_connected(self) -> bool:
        """
        确保已连接，如果断开则尝试重连

        Returns:
            True if connected (or reconnected successfully)
        """
        if self.is_connected:
            return True

        if self._state == ConnectionState.DISCONNECTED:
            logger.warning("Connection lost. Attempting to reconnect...")
            return self.reconnect()

        if self._state == ConnectionState.ERROR:
            # 如果之前出错，重置重连计数后重试
            self._reconnect_attempts = 0
            return self.reconnect()

        return False

    def check_connection(self) -> bool:
        """
        检查连接状态（心跳检测）

        Returns:
            True if connection is healthy
        """
        if self._simulation_mode:
            return self._state == ConnectionState.CONNECTED

        if not self._ib:
            return False

        try:
            # 通过请求当前时间来检查连接是否存活
            if self._ib.isConnected():
                # 尝试一个轻量级操作来验证连接
                self._ib.reqCurrentTime()
                return True
            else:
                self._set_state(ConnectionState.DISCONNECTED)
                return False
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            self._set_state(ConnectionState.ERROR, str(e))
            return False

    def get_positions(self) -> List[Position]:
        """
        Get all portfolio positions

        Returns:
            List of Position objects
        """
        if not self.is_connected:
            logger.error("Not connected to IB. Cannot get positions.")
            return []

        if self._simulation_mode:
            return self._get_simulated_positions()

        try:
            logger.info("Fetching positions from IB...")
            ib_positions = self._ib.positions(self._account_id)
            positions = []

            for pos in ib_positions:
                contract = pos.contract
                position = self._convert_ib_position(pos, contract)
                if position:
                    positions.append(position)
                    position.log_details()

            logger.info(f"Retrieved {len(positions)} positions")
            self._positions_cache = positions
            return positions

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def _convert_ib_position(self, pos: Any, contract: Any) -> Optional[Position]:
        """
        Convert IB position to our Position model

        Supports all IB asset types:
        - STK (Stock)
        - OPT (Option)
        - FUT (Futures)
        - CASH (Forex)
        - BOND (Bond)
        - CFD (Contract for Difference)
        - FOP (Futures Option)
        - WAR (Warrant)
        - FUND (Mutual Fund/ETF)
        - CRYPTO (Cryptocurrency)
        """
        try:
            sec_type = contract.secType
            option_details = None
            futures_details = None
            forex_details = None
            bond_details = None
            crypto_details = None
            fund_details = None

            # 期权 (Option)
            if sec_type == SecType.OPTION:
                option_details = self._parse_option_details(contract)

            # 期货期权 (Futures Option) - 与期权类似
            elif sec_type == SecType.FUT_OPT:
                option_details = self._parse_option_details(contract)

            # 权证 (Warrant) - 与期权类似
            elif sec_type == SecType.WARRANT:
                option_details = self._parse_option_details(contract)

            # 期货 (Futures)
            elif sec_type == SecType.FUTURES:
                futures_details = self._parse_futures_details(contract)

            # 外汇 (Forex)
            elif sec_type == SecType.FOREX:
                forex_details = self._parse_forex_details(contract)

            # 债券 (Bond)
            elif sec_type == SecType.BOND:
                bond_details = self._parse_bond_details(contract)

            # 加密货币 (Crypto)
            elif sec_type == SecType.CRYPTO:
                crypto_details = self._parse_crypto_details(contract)

            # 基金 (Fund/ETF)
            elif sec_type == SecType.FUND:
                fund_details = self._parse_fund_details(contract)

            return Position(
                symbol=contract.symbol,
                sec_type=sec_type,
                con_id=contract.conId,
                position=float(pos.position),
                avg_cost=float(pos.avgCost),
                market_price=0.0,  # Will be updated with market data
                market_value=0.0,
                currency=contract.currency,
                exchange=contract.exchange or "SMART",
                option_details=option_details,
                futures_details=futures_details,
                forex_details=forex_details,
                bond_details=bond_details,
                crypto_details=crypto_details,
                fund_details=fund_details
            )

        except Exception as e:
            logger.error(f"Error converting position for {contract.symbol}: {e}")
            return None

    def _parse_option_details(self, contract: Any) -> Optional[OptionDetails]:
        """解析期权详情"""
        try:
            expiry_str = contract.lastTradeDateOrContractMonth
            expiry_date = datetime.strptime(expiry_str, "%Y%m%d").date()

            return OptionDetails(
                strike=float(contract.strike),
                right=contract.right,
                expiry=expiry_date,
                multiplier=int(contract.multiplier or 100)
            )
        except Exception as e:
            logger.warning(f"Error parsing option details for {contract.symbol}: {e}")
            return None

    def _parse_futures_details(self, contract: Any) -> Optional[FuturesDetails]:
        """解析期货详情"""
        try:
            expiry_str = contract.lastTradeDateOrContractMonth
            # 期货到期日可能是 YYYYMM 或 YYYYMMDD 格式
            if len(expiry_str) == 6:
                expiry_date = datetime.strptime(expiry_str + "01", "%Y%m%d").date()
            else:
                expiry_date = datetime.strptime(expiry_str, "%Y%m%d").date()

            return FuturesDetails(
                expiry=expiry_date,
                multiplier=float(contract.multiplier or 1.0),
                contract_month=expiry_str[:6] if len(expiry_str) >= 6 else None,
                underlying=getattr(contract, 'underSymbol', None)
            )
        except Exception as e:
            logger.warning(f"Error parsing futures details for {contract.symbol}: {e}")
            return None

    def _parse_forex_details(self, contract: Any) -> Optional[ForexDetails]:
        """解析外汇详情"""
        try:
            symbol = contract.symbol
            # 外汇通常格式为 EUR.USD 或 EURUSD
            if '.' in symbol:
                parts = symbol.split('.')
                base = parts[0]
                quote = parts[1] if len(parts) > 1 else contract.currency
            else:
                base = symbol[:3] if len(symbol) >= 3 else symbol
                quote = symbol[3:] if len(symbol) >= 6 else contract.currency

            return ForexDetails(
                base_currency=base,
                quote_currency=quote
            )
        except Exception as e:
            logger.warning(f"Error parsing forex details for {contract.symbol}: {e}")
            return None

    def _parse_bond_details(self, contract: Any) -> Optional[BondDetails]:
        """解析债券详情"""
        try:
            maturity_str = getattr(contract, 'maturity', None) or getattr(contract, 'lastTradeDateOrContractMonth', None)
            if maturity_str:
                if len(maturity_str) == 6:
                    maturity_date = datetime.strptime(maturity_str + "01", "%Y%m%d").date()
                else:
                    maturity_date = datetime.strptime(maturity_str, "%Y%m%d").date()
            else:
                # 默认 5 年后到期
                maturity_date = date.today().replace(year=date.today().year + 5)

            coupon = getattr(contract, 'coupon', 0.0)

            return BondDetails(
                maturity_date=maturity_date,
                coupon_rate=float(coupon) if coupon else 0.0,
                face_value=1000.0,
                rating=getattr(contract, 'rating', None)
            )
        except Exception as e:
            logger.warning(f"Error parsing bond details for {contract.symbol}: {e}")
            return None

    def _parse_crypto_details(self, contract: Any) -> Optional[CryptoDetails]:
        """解析加密货币详情"""
        try:
            return CryptoDetails(
                base_currency=contract.symbol,
                quote_currency=contract.currency or "USD"
            )
        except Exception as e:
            logger.warning(f"Error parsing crypto details for {contract.symbol}: {e}")
            return None

    def _parse_fund_details(self, contract: Any) -> Optional[FundDetails]:
        """解析基金详情"""
        try:
            # 尝试判断是 ETF 还是共同基金
            fund_type = "ETF"  # 默认为 ETF
            # 如果有特定标识，可以进一步判断
            if hasattr(contract, 'secIdType') and contract.secIdType == 'CUSIP':
                fund_type = "MutualFund"

            return FundDetails(
                fund_type=fund_type,
                expense_ratio=None,  # IB 通常不提供这个信息
                nav=None
            )
        except Exception as e:
            logger.warning(f"Error parsing fund details for {contract.symbol}: {e}")
            return None

    def get_account_summary(self) -> Optional[AccountSummary]:
        """
        Get account summary information

        Returns:
            AccountSummary object or None
        """
        if not self.is_connected:
            logger.error("Not connected to IB. Cannot get account summary.")
            return None

        if self._simulation_mode:
            return self._get_simulated_account_summary()

        try:
            logger.info("Fetching account summary...")
            account_values = self._ib.accountSummary(self._account_id)

            summary_dict = {}
            for av in account_values:
                summary_dict[av.tag] = float(av.value) if av.value else 0.0

            summary = AccountSummary(
                account_id=self._account_id,
                net_liquidation=summary_dict.get("NetLiquidation", 0),
                total_cash=summary_dict.get("TotalCashValue", 0),
                settled_cash=summary_dict.get("SettledCash", 0),
                buying_power=summary_dict.get("BuyingPower", 0),
                equity_with_loan=summary_dict.get("EquityWithLoanValue", 0),
                gross_position_value=summary_dict.get("GrossPositionValue", 0),
                maintenance_margin=summary_dict.get("MaintMarginReq", 0),
                initial_margin=summary_dict.get("InitMarginReq", 0),
                available_funds=summary_dict.get("AvailableFunds", 0),
                excess_liquidity=summary_dict.get("ExcessLiquidity", 0),
                sma=summary_dict.get("SMA", 0),
                unrealized_pnl=summary_dict.get("UnrealizedPnL", 0),
                realized_pnl=summary_dict.get("RealizedPnL", 0)
            )

            summary.log_summary()
            return summary

        except Exception as e:
            logger.error(f"Error fetching account summary: {e}")
            return None

    def get_market_data(
        self,
        positions: Optional[List[Position]] = None,
        timeout: int = 10
    ) -> Dict[int, MarketData]:
        """
        Get market data for positions

        Args:
            positions: List of positions (uses cache if None)
            timeout: Timeout for data request

        Returns:
            Dictionary mapping conId to MarketData
        """
        if not self.is_connected:
            logger.error("Not connected to IB. Cannot get market data.")
            return {}

        if positions is None:
            positions = self._positions_cache

        if self._simulation_mode:
            return self._get_simulated_market_data(positions)

        try:
            logger.info(f"Fetching market data for {len(positions)} positions...")
            market_data = {}

            for pos in positions:
                contract = self._create_contract_from_position(pos)

                try:
                    self._ib.qualifyContracts(contract)
                    ticker = self._ib.reqMktData(contract, snapshot=True)
                    self._ib.sleep(timeout / len(positions) if positions else 1)

                    md = MarketData(
                        symbol=pos.symbol,
                        con_id=pos.con_id,
                        bid=ticker.bid if ticker.bid > 0 else 0,
                        ask=ticker.ask if ticker.ask > 0 else 0,
                        last=ticker.last if ticker.last > 0 else 0,
                        close=ticker.close if ticker.close > 0 else 0,
                        high=ticker.high if ticker.high > 0 else 0,
                        low=ticker.low if ticker.low > 0 else 0,
                        volume=int(ticker.volume) if ticker.volume else 0
                    )

                    # Get option-specific data
                    if pos.is_option and hasattr(ticker, 'modelGreeks'):
                        if ticker.modelGreeks:
                            md.implied_volatility = ticker.modelGreeks.impliedVol
                            md.underlying_price = ticker.modelGreeks.undPrice

                    market_data[pos.con_id] = md
                    logger.debug(f"Got market data for {pos.symbol}: mid={md.mid:.2f}")

                    self._ib.cancelMktData(contract)

                except Exception as e:
                    logger.warning(f"Error getting market data for {pos.symbol}: {e}")

            self._market_data_cache = market_data
            return market_data

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return {}

    def _create_contract_from_position(self, pos: Position) -> Any:
        """Create IB contract from Position"""
        from ib_insync import Stock, Option, Contract

        if pos.sec_type == "STK":
            return Stock(pos.symbol, pos.exchange, pos.currency)

        elif pos.sec_type == "OPT" and pos.option_details:
            return Option(
                symbol=pos.symbol,
                lastTradeDateOrContractMonth=pos.option_details.expiry.strftime("%Y%m%d"),
                strike=pos.option_details.strike,
                right=pos.option_details.right,
                exchange=pos.exchange,
                currency=pos.currency,
                multiplier=str(pos.option_details.multiplier)
            )

        else:
            contract = Contract()
            contract.conId = pos.con_id
            return contract

    # ========== Simulation Methods ==========

    def _get_simulated_positions(self) -> List[Position]:
        """Generate simulated positions for testing"""
        logger.info("Generating simulated positions...")

        positions = [
            # Stock positions
            Position(
                symbol="AAPL",
                sec_type="STK",
                con_id=265598,
                position=100,
                avg_cost=175.50,
                market_price=182.30,
                market_value=18230.00,
                unrealized_pnl=680.00,
                currency="USD"
            ),
            Position(
                symbol="SPY",
                sec_type="STK",
                con_id=756733,
                position=50,
                avg_cost=445.00,
                market_price=472.50,
                market_value=23625.00,
                unrealized_pnl=1375.00,
                currency="USD"
            ),
            # Call option (long)
            Position(
                symbol="AAPL",
                sec_type="OPT",
                con_id=600001,
                position=5,
                avg_cost=8.50,
                market_price=12.30,
                market_value=6150.00,
                unrealized_pnl=1900.00,
                currency="USD",
                option_details=OptionDetails(
                    strike=180.0,
                    right="C",
                    expiry=date(2026, 2, 21),
                    multiplier=100
                )
            ),
            # Put option (long, hedge)
            Position(
                symbol="SPY",
                sec_type="OPT",
                con_id=600002,
                position=2,
                avg_cost=5.20,
                market_price=3.80,
                market_value=760.00,
                unrealized_pnl=-280.00,
                currency="USD",
                option_details=OptionDetails(
                    strike=460.0,
                    right="P",
                    expiry=date(2026, 2, 14),
                    multiplier=100
                )
            ),
            # Covered call (short)
            Position(
                symbol="AAPL",
                sec_type="OPT",
                con_id=600003,
                position=-1,
                avg_cost=3.20,
                market_price=2.50,
                market_value=-250.00,
                unrealized_pnl=70.00,
                currency="USD",
                option_details=OptionDetails(
                    strike=190.0,
                    right="C",
                    expiry=date(2026, 1, 31),
                    multiplier=100
                )
            ),
            # Cash-secured put (short)
            Position(
                symbol="NVDA",
                sec_type="OPT",
                con_id=600004,
                position=-2,
                avg_cost=15.00,
                market_price=12.50,
                market_value=-2500.00,
                unrealized_pnl=500.00,
                currency="USD",
                option_details=OptionDetails(
                    strike=850.0,
                    right="P",
                    expiry=date(2026, 2, 21),
                    multiplier=100
                )
            ),
        ]

        for pos in positions:
            pos.log_details()

        logger.info(f"Generated {len(positions)} simulated positions")
        return positions

    def _get_simulated_account_summary(self) -> AccountSummary:
        """Generate simulated account summary"""
        summary = AccountSummary(
            account_id=self._account_id or "DU1234567",
            net_liquidation=150000.00,
            total_cash=50000.00,
            settled_cash=48000.00,
            buying_power=100000.00,
            equity_with_loan=150000.00,
            gross_position_value=100000.00,
            maintenance_margin=25000.00,
            initial_margin=30000.00,
            available_funds=70000.00,
            excess_liquidity=75000.00,
            sma=80000.00,
            unrealized_pnl=4245.00,
            realized_pnl=2500.00
        )
        summary.log_summary()
        return summary

    def _get_simulated_market_data(self, positions: List[Position]) -> Dict[int, MarketData]:
        """Generate simulated market data"""
        import random

        market_data = {}

        # Underlying prices
        underlying_prices = {
            "AAPL": 182.30,
            "SPY": 472.50,
            "NVDA": 875.00,
            "QQQ": 410.00,
        }

        for pos in positions:
            base_price = pos.market_price if pos.market_price > 0 else pos.avg_cost
            underlying = underlying_prices.get(pos.symbol, base_price)

            # Add some random variation for bid/ask
            spread = base_price * 0.002  # 0.2% spread
            bid = base_price - spread / 2
            ask = base_price + spread / 2

            md = MarketData(
                symbol=pos.symbol,
                con_id=pos.con_id,
                bid=round(bid, 2),
                ask=round(ask, 2),
                last=round(base_price, 2),
                close=round(base_price * 0.998, 2),
                high=round(base_price * 1.01, 2),
                low=round(base_price * 0.99, 2),
                volume=random.randint(10000, 500000),
                underlying_price=underlying if pos.is_option else None,
                implied_volatility=random.uniform(0.20, 0.45) if pos.is_option else None
            )

            market_data[pos.con_id] = md
            logger.debug(f"Simulated market data for {pos.symbol}: mid={md.mid:.2f}")

        return market_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
