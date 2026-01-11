"""
Data models for IB Client module
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger


class SecType:
    """IB 证券类型常量"""
    STOCK = "STK"       # 股票 (Stock)
    OPTION = "OPT"      # 期权 (Option)
    FUTURES = "FUT"     # 期货 (Futures)
    FOREX = "CASH"      # 外汇 (Forex)
    BOND = "BOND"       # 债券 (Bond)
    CFD = "CFD"         # 差价合约 (Contract for Difference)
    FUT_OPT = "FOP"     # 期货期权 (Futures Option)
    WARRANT = "WAR"     # 权证 (Warrant)
    FUND = "FUND"       # 基金 (Mutual Fund/ETF)
    CRYPTO = "CRYPTO"   # 加密货币 (Cryptocurrency)
    INDEX = "IND"       # 指数 (Index)
    COMMODITY = "CMDTY" # 商品 (Commodity)

    @classmethod
    def all_types(cls) -> list:
        """返回所有支持的证券类型"""
        return [
            cls.STOCK, cls.OPTION, cls.FUTURES, cls.FOREX,
            cls.BOND, cls.CFD, cls.FUT_OPT, cls.WARRANT,
            cls.FUND, cls.CRYPTO, cls.INDEX, cls.COMMODITY
        ]

    @classmethod
    def display_name(cls, sec_type: str) -> str:
        """返回证券类型的显示名称"""
        names = {
            cls.STOCK: "股票",
            cls.OPTION: "期权",
            cls.FUTURES: "期货",
            cls.FOREX: "外汇",
            cls.BOND: "债券",
            cls.CFD: "差价合约",
            cls.FUT_OPT: "期货期权",
            cls.WARRANT: "权证",
            cls.FUND: "基金",
            cls.CRYPTO: "加密货币",
            cls.INDEX: "指数",
            cls.COMMODITY: "商品",
        }
        return names.get(sec_type, sec_type)


class OptionDetails(BaseModel):
    """Option-specific details"""
    strike: float = Field(..., description="Strike price")
    right: str = Field(..., description="Option right: C for Call, P for Put")
    expiry: date = Field(..., description="Expiration date")
    multiplier: int = Field(default=100, description="Contract multiplier")

    @property
    def is_call(self) -> bool:
        return self.right.upper() == "C"

    @property
    def is_put(self) -> bool:
        return self.right.upper() == "P"

    @property
    def days_to_expiry(self) -> int:
        """Calculate days until expiration"""
        delta = self.expiry - date.today()
        return max(0, delta.days)


class FuturesDetails(BaseModel):
    """Futures-specific details 期货详情"""
    expiry: date = Field(..., description="Contract expiration date")
    multiplier: float = Field(default=1.0, description="Contract multiplier")
    contract_month: Optional[str] = Field(default=None, description="Contract month (YYYYMM)")
    underlying: Optional[str] = Field(default=None, description="Underlying symbol")

    @property
    def days_to_expiry(self) -> int:
        """Calculate days until expiration"""
        delta = self.expiry - date.today()
        return max(0, delta.days)


class ForexDetails(BaseModel):
    """Forex-specific details 外汇详情"""
    base_currency: str = Field(..., description="Base currency (e.g., EUR)")
    quote_currency: str = Field(..., description="Quote currency (e.g., USD)")
    pip_value: float = Field(default=0.0001, description="Pip value")

    @property
    def pair(self) -> str:
        """Return currency pair string"""
        return f"{self.base_currency}/{self.quote_currency}"


class BondDetails(BaseModel):
    """Bond-specific details 债券详情"""
    maturity_date: date = Field(..., description="Bond maturity date")
    coupon_rate: float = Field(default=0.0, description="Annual coupon rate")
    face_value: float = Field(default=1000.0, description="Face/Par value")
    rating: Optional[str] = Field(default=None, description="Credit rating (e.g., AAA)")
    yield_to_maturity: Optional[float] = Field(default=None, description="YTM")

    @property
    def days_to_maturity(self) -> int:
        """Calculate days until maturity"""
        delta = self.maturity_date - date.today()
        return max(0, delta.days)


class CryptoDetails(BaseModel):
    """Cryptocurrency-specific details 加密货币详情"""
    base_currency: str = Field(..., description="Crypto symbol (e.g., BTC)")
    quote_currency: str = Field(default="USD", description="Quote currency")


class FundDetails(BaseModel):
    """Fund-specific details 基金详情"""
    fund_type: str = Field(default="ETF", description="Fund type: ETF, MutualFund, etc.")
    expense_ratio: Optional[float] = Field(default=None, description="Expense ratio")
    nav: Optional[float] = Field(default=None, description="Net Asset Value")


class Position(BaseModel):
    """Represents a portfolio position"""
    symbol: str = Field(..., description="Underlying symbol")
    sec_type: str = Field(..., description="Security type: STK, OPT, FUT, etc.")
    con_id: int = Field(..., description="IB contract ID")
    position: float = Field(..., description="Position quantity (positive=long, negative=short)")
    avg_cost: float = Field(default=0.0, description="Average cost per unit")
    market_price: float = Field(default=0.0, description="Current market price")
    market_value: float = Field(default=0.0, description="Current market value")
    unrealized_pnl: float = Field(default=0.0, description="Unrealized P&L")
    realized_pnl: float = Field(default=0.0, description="Realized P&L")
    currency: str = Field(default="USD", description="Currency")
    exchange: str = Field(default="SMART", description="Exchange")

    # 资产类型详情
    option_details: Optional[OptionDetails] = Field(default=None, description="Option details if applicable")
    futures_details: Optional[FuturesDetails] = Field(default=None, description="Futures details if applicable")
    forex_details: Optional[ForexDetails] = Field(default=None, description="Forex details if applicable")
    bond_details: Optional[BondDetails] = Field(default=None, description="Bond details if applicable")
    crypto_details: Optional[CryptoDetails] = Field(default=None, description="Crypto details if applicable")
    fund_details: Optional[FundDetails] = Field(default=None, description="Fund details if applicable")

    # 基本类型判断
    @property
    def is_option(self) -> bool:
        return self.sec_type == SecType.OPTION

    @property
    def is_stock(self) -> bool:
        return self.sec_type == SecType.STOCK

    @property
    def is_futures(self) -> bool:
        return self.sec_type == SecType.FUTURES

    @property
    def is_forex(self) -> bool:
        return self.sec_type == SecType.FOREX

    @property
    def is_bond(self) -> bool:
        return self.sec_type == SecType.BOND

    @property
    def is_cfd(self) -> bool:
        return self.sec_type == SecType.CFD

    @property
    def is_futures_option(self) -> bool:
        return self.sec_type == SecType.FUT_OPT

    @property
    def is_warrant(self) -> bool:
        return self.sec_type == SecType.WARRANT

    @property
    def is_fund(self) -> bool:
        return self.sec_type == SecType.FUND

    @property
    def is_crypto(self) -> bool:
        return self.sec_type == SecType.CRYPTO

    # 分类判断
    @property
    def is_derivative(self) -> bool:
        """是否为衍生品"""
        return self.sec_type in [SecType.OPTION, SecType.FUTURES, SecType.FUT_OPT, SecType.CFD, SecType.WARRANT]

    @property
    def is_cash_like(self) -> bool:
        """是否为现金类资产（股票、基金、加密货币等）"""
        return self.sec_type in [SecType.STOCK, SecType.FUND, SecType.CRYPTO]

    @property
    def is_fixed_income(self) -> bool:
        """是否为固定收益类"""
        return self.sec_type == SecType.BOND

    # 方向判断
    @property
    def is_long(self) -> bool:
        return self.position > 0

    @property
    def is_short(self) -> bool:
        return self.position < 0

    # 计算属性
    @property
    def total_cost(self) -> float:
        """Total cost basis"""
        return abs(self.position) * self.avg_cost

    @property
    def multiplier(self) -> float:
        """获取合约乘数"""
        if self.option_details:
            return self.option_details.multiplier
        if self.futures_details:
            return self.futures_details.multiplier
        return 1.0

    @property
    def sec_type_display(self) -> str:
        """返回证券类型的显示名称"""
        return SecType.display_name(self.sec_type)

    def log_details(self) -> None:
        """Log position details for debugging"""
        logger.debug(
            f"Position: {self.symbol} | Type: {self.sec_type} ({self.sec_type_display}) | "
            f"Qty: {self.position} | Price: {self.market_price:.2f} | "
            f"Value: {self.market_value:.2f} | P&L: {self.unrealized_pnl:.2f}"
        )
        if self.option_details:
            logger.debug(
                f"  Option: {self.option_details.strike} "
                f"{self.option_details.right} exp {self.option_details.expiry} "
                f"({self.option_details.days_to_expiry} days)"
            )
        if self.futures_details:
            logger.debug(
                f"  Futures: multiplier={self.futures_details.multiplier} "
                f"exp {self.futures_details.expiry} "
                f"({self.futures_details.days_to_expiry} days)"
            )
        if self.forex_details:
            logger.debug(f"  Forex: {self.forex_details.pair}")
        if self.bond_details:
            logger.debug(
                f"  Bond: coupon={self.bond_details.coupon_rate:.2%} "
                f"maturity={self.bond_details.maturity_date} "
                f"rating={self.bond_details.rating or 'N/A'}"
            )
        if self.crypto_details:
            logger.debug(f"  Crypto: {self.crypto_details.base_currency}/{self.crypto_details.quote_currency}")
        if self.fund_details:
            logger.debug(f"  Fund: type={self.fund_details.fund_type}")


class MarketData(BaseModel):
    """Market data for a security"""
    symbol: str
    con_id: int
    bid: float = Field(default=0.0)
    ask: float = Field(default=0.0)
    last: float = Field(default=0.0)
    close: float = Field(default=0.0)
    high: float = Field(default=0.0)
    low: float = Field(default=0.0)
    volume: int = Field(default=0)
    open_interest: Optional[int] = Field(default=None, description="Open interest for options")
    implied_volatility: Optional[float] = Field(default=None, description="Implied volatility")
    underlying_price: Optional[float] = Field(default=None, description="Underlying price for options")
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def mid(self) -> float:
        """Mid price"""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last if self.last > 0 else self.close

    @property
    def spread(self) -> float:
        """Bid-ask spread"""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0

    @property
    def spread_pct(self) -> float:
        """Bid-ask spread as percentage of mid"""
        mid = self.mid
        if mid > 0:
            return self.spread / mid * 100
        return 0.0


class AccountSummary(BaseModel):
    """Account summary information"""
    account_id: str = Field(..., description="Account identifier")
    net_liquidation: float = Field(default=0.0, description="Net liquidation value")
    total_cash: float = Field(default=0.0, description="Total cash balance")
    settled_cash: float = Field(default=0.0, description="Settled cash")
    buying_power: float = Field(default=0.0, description="Buying power")
    equity_with_loan: float = Field(default=0.0, description="Equity with loan value")
    gross_position_value: float = Field(default=0.0, description="Gross position value")
    maintenance_margin: float = Field(default=0.0, description="Maintenance margin requirement")
    initial_margin: float = Field(default=0.0, description="Initial margin requirement")
    available_funds: float = Field(default=0.0, description="Available funds")
    excess_liquidity: float = Field(default=0.0, description="Excess liquidity")
    sma: float = Field(default=0.0, description="Special Memorandum Account")
    unrealized_pnl: float = Field(default=0.0, description="Total unrealized P&L")
    realized_pnl: float = Field(default=0.0, description="Total realized P&L")
    currency: str = Field(default="USD")
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def margin_usage(self) -> float:
        """Margin usage percentage"""
        if self.net_liquidation > 0:
            return self.maintenance_margin / self.net_liquidation * 100
        return 0.0

    def log_summary(self) -> None:
        """Log account summary for debugging"""
        logger.info(f"Account: {self.account_id}")
        logger.info(f"  Net Liquidation: ${self.net_liquidation:,.2f}")
        logger.info(f"  Total Cash: ${self.total_cash:,.2f}")
        logger.info(f"  Buying Power: ${self.buying_power:,.2f}")
        logger.info(f"  Margin Usage: {self.margin_usage:.1f}%")
        logger.info(f"  Unrealized P&L: ${self.unrealized_pnl:,.2f}")
