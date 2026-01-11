"""
Data models for Portfolio Advisor
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationType(str, Enum):
    HEDGE = "HEDGE"
    ADJUST = "ADJUST"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    ROLL = "ROLL"
    CLOSE = "CLOSE"
    REBALANCE = "REBALANCE"
    MONITOR = "MONITOR"


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Recommendation(BaseModel):
    """Investment recommendation"""
    type: RecommendationType
    priority: Priority
    title: str = Field(..., description="Short title for the recommendation")
    description: str = Field(..., description="Detailed description")
    reason: str = Field(..., description="Why this recommendation is made")
    suggested_action: str = Field(..., description="Specific action to take")
    affected_positions: List[str] = Field(default_factory=list)
    potential_impact: Optional[str] = None
    urgency_days: Optional[int] = Field(default=None, description="Days until action needed")


class GreeksAssessment(BaseModel):
    """Assessment of portfolio Greeks"""
    delta_neutral: bool = Field(default=False, description="Is portfolio delta neutral?")
    delta_bias: str = Field(default="neutral", description="bullish/bearish/neutral")
    delta_risk_level: RiskLevel = RiskLevel.LOW

    gamma_risk_level: RiskLevel = RiskLevel.LOW
    gamma_warning: Optional[str] = None

    theta_daily: float = Field(default=0.0, description="Daily theta in dollars")
    theta_assessment: str = Field(default="", description="Theta assessment text")
    theta_risk_level: RiskLevel = RiskLevel.LOW

    vega_exposure: float = Field(default=0.0)
    vega_risk_level: RiskLevel = RiskLevel.LOW
    vega_warning: Optional[str] = None


class ConcentrationWarning(BaseModel):
    """Warning about position concentration"""
    type: str = Field(..., description="Type of concentration: symbol/sector/expiry")
    entity: str = Field(..., description="The concentrated entity")
    percentage: float = Field(..., description="Concentration percentage")
    threshold: float = Field(..., description="Warning threshold")
    message: str


class TimeDecayAnalysis(BaseModel):
    """Analysis of time decay in portfolio"""
    total_theta_daily: float = Field(default=0.0, description="Total daily theta")
    theta_per_week: float = Field(default=0.0)
    theta_to_expiry: float = Field(default=0.0, description="Total theta until nearest expiry")
    nearest_expiry_days: Optional[int] = None
    expiring_soon_count: int = Field(default=0, description="Options expiring within 7 days")
    roll_recommendation: Optional[str] = None


class RiskAssessment(BaseModel):
    """Overall risk assessment"""
    overall_level: RiskLevel = RiskLevel.LOW
    risk_score: int = Field(default=0, ge=0, le=100, description="0-100 risk score")

    # Individual risk components
    market_risk: RiskLevel = RiskLevel.LOW
    volatility_risk: RiskLevel = RiskLevel.LOW
    time_decay_risk: RiskLevel = RiskLevel.LOW
    concentration_risk: RiskLevel = RiskLevel.LOW
    liquidity_risk: RiskLevel = RiskLevel.LOW

    # Risk metrics
    var_95: float = Field(default=0.0)
    var_99: float = Field(default=0.0)
    max_loss_probability: float = Field(default=0.0)
    expected_shortfall: float = Field(default=0.0)

    key_risks: List[str] = Field(default_factory=list)


class PortfolioAdvice(BaseModel):
    """Complete portfolio advice output"""
    # Summary
    summary: str = Field(..., description="Executive summary of portfolio status")
    generated_at: str = Field(..., description="Timestamp of advice generation")

    # Risk assessment
    risk_assessment: RiskAssessment

    # Detailed assessments
    greeks_assessment: GreeksAssessment
    concentration_warnings: List[ConcentrationWarning] = Field(default_factory=list)
    time_decay_analysis: TimeDecayAnalysis

    # Recommendations
    recommendations: List[Recommendation] = Field(default_factory=list)

    # Action items
    immediate_actions: List[str] = Field(default_factory=list)
    weekly_review_items: List[str] = Field(default_factory=list)

    def get_high_priority_recommendations(self) -> List[Recommendation]:
        """Get high priority recommendations"""
        return [r for r in self.recommendations if r.priority == Priority.HIGH]

    def get_urgent_recommendations(self, days: int = 7) -> List[Recommendation]:
        """Get recommendations with urgency within specified days"""
        return [r for r in self.recommendations
                if r.urgency_days is not None and r.urgency_days <= days]

    def to_summary_dict(self) -> dict:
        """Get summary as dictionary"""
        return {
            "risk_level": self.risk_assessment.overall_level.value,
            "risk_score": self.risk_assessment.risk_score,
            "key_risks_count": len(self.risk_assessment.key_risks),
            "recommendations_count": len(self.recommendations),
            "high_priority_count": len(self.get_high_priority_recommendations()),
            "concentration_warnings_count": len(self.concentration_warnings),
            "daily_theta": self.time_decay_analysis.total_theta_daily,
            "delta_bias": self.greeks_assessment.delta_bias,
        }
