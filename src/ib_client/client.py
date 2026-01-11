"""
IB Client - Main client class for Interactive Brokers API
"""

import asyncio
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from loguru import logger

try:
    from ib_insync import IB, Contract, util
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    logger.warning("ib_insync not installed. Using simulation mode.")

from .models import Position, AccountSummary, MarketData, OptionDetails


class IBClient:
    """
    Interactive Brokers API Client

    Provides methods to connect to IB TWS/Gateway, retrieve positions,
    account data, and market data.
    """

    def __init__(self, simulation_mode: bool = False):
        """
        Initialize IB Client

        Args:
            simulation_mode: If True, use simulated data instead of real IB connection
        """
        self._ib: Optional[Any] = None
        self._connected: bool = False
        self._simulation_mode = simulation_mode or not IB_INSYNC_AVAILABLE
        self._account_id: str = ""
        self._positions_cache: List[Position] = []
        self._market_data_cache: Dict[int, MarketData] = {}

        if self._simulation_mode:
            logger.info("IBClient initialized in SIMULATION mode")
        else:
            logger.info("IBClient initialized for real IB connection")

    @property
    def is_connected(self) -> bool:
        """Check if connected to IB"""
        if self._simulation_mode:
            return self._connected
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
        if self._simulation_mode:
            logger.info(f"Simulation mode: Simulating connection to {host}:{port}")
            self._connected = True
            self._account_id = account or "DU1234567"
            logger.info(f"Connected to simulated account: {self._account_id}")
            return True

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

            self._connected = True
            accounts = self._ib.managedAccounts()
            self._account_id = account if account else accounts[0] if accounts else ""

            logger.info(f"Successfully connected to IB. Account: {self._account_id}")
            logger.debug(f"Available accounts: {accounts}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to IB: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from IB"""
        if self._simulation_mode:
            logger.info("Simulation mode: Disconnecting")
            self._connected = False
            return

        if self._ib and self._ib.isConnected():
            logger.info("Disconnecting from IB...")
            self._ib.disconnect()
            logger.info("Disconnected from IB")

        self._connected = False

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
        """Convert IB position to our Position model"""
        try:
            option_details = None

            if contract.secType == "OPT":
                expiry_str = contract.lastTradeDateOrContractMonth
                expiry_date = datetime.strptime(expiry_str, "%Y%m%d").date()

                option_details = OptionDetails(
                    strike=float(contract.strike),
                    right=contract.right,
                    expiry=expiry_date,
                    multiplier=int(contract.multiplier or 100)
                )

            return Position(
                symbol=contract.symbol,
                sec_type=contract.secType,
                con_id=contract.conId,
                position=float(pos.position),
                avg_cost=float(pos.avgCost),
                market_price=0.0,  # Will be updated with market data
                market_value=0.0,
                currency=contract.currency,
                exchange=contract.exchange or "SMART",
                option_details=option_details
            )

        except Exception as e:
            logger.error(f"Error converting position for {contract.symbol}: {e}")
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
