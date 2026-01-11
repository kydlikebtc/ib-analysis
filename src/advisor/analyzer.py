"""
Portfolio Advisor - Main analyzer for generating recommendations
"""

from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from ..ib_client.models import Position
from ..greeks.models import PortfolioGreeks
from ..monte_carlo.models import SimulationResult
from .models import (
    PortfolioAdvice, Recommendation, RiskAssessment, GreeksAssessment,
    ConcentrationWarning, TimeDecayAnalysis,
    RiskLevel, RecommendationType, Priority
)


class PortfolioAdvisor:
    """
    Portfolio Advisor

    Analyzes portfolio risk, Greeks, and simulation results to generate
    actionable investment recommendations.
    """

    def __init__(
        self,
        delta_neutral_threshold: float = 0.1,
        gamma_warning_threshold: float = 0.05,
        theta_warning_daily: float = -100,
        concentration_warning: float = 0.30,
        var_warning_threshold: float = 0.10
    ):
        """
        Initialize Portfolio Advisor

        Args:
            delta_neutral_threshold: Delta per $10k considered neutral
            gamma_warning_threshold: Gamma threshold for warning
            theta_warning_daily: Daily theta threshold for warning (negative)
            concentration_warning: Single position concentration warning (0.30 = 30%)
            var_warning_threshold: VaR as percentage of portfolio value
        """
        self.delta_neutral_threshold = delta_neutral_threshold
        self.gamma_warning_threshold = gamma_warning_threshold
        self.theta_warning_daily = theta_warning_daily
        self.concentration_warning = concentration_warning
        self.var_warning_threshold = var_warning_threshold

        logger.info("PortfolioAdvisor initialized with thresholds:")
        logger.info(f"  Delta neutral: {delta_neutral_threshold} per $10k")
        logger.info(f"  Gamma warning: {gamma_warning_threshold}")
        logger.info(f"  Theta warning: ${theta_warning_daily}/day")
        logger.info(f"  Concentration warning: {concentration_warning * 100}%")

    def analyze_risk(
        self,
        positions: List[Position],
        simulation: SimulationResult,
        greeks: PortfolioGreeks
    ) -> RiskAssessment:
        """
        Analyze overall portfolio risk

        Args:
            positions: List of positions
            simulation: Monte Carlo simulation results
            greeks: Portfolio Greeks

        Returns:
            RiskAssessment object
        """
        logger.info("Analyzing portfolio risk...")

        stats = simulation.statistics
        initial_value = simulation.initial_portfolio_value

        key_risks = []
        risk_score = 0

        # Market risk (based on delta exposure)
        delta_ratio = abs(greeks.total_delta_dollars) / initial_value if initial_value > 0 else 0
        if delta_ratio > 0.5:
            market_risk = RiskLevel.HIGH
            risk_score += 25
            key_risks.append(f"High delta exposure: {delta_ratio * 100:.1f}% of portfolio")
        elif delta_ratio > 0.25:
            market_risk = RiskLevel.MEDIUM
            risk_score += 15
        else:
            market_risk = RiskLevel.LOW
            risk_score += 5

        # Volatility risk (based on vega)
        vega_ratio = abs(greeks.total_vega_dollars) / initial_value if initial_value > 0 else 0
        if vega_ratio > 0.05:
            volatility_risk = RiskLevel.HIGH
            risk_score += 20
            key_risks.append(f"High vega exposure: ${greeks.total_vega_dollars:,.0f} per 1% IV")
        elif vega_ratio > 0.02:
            volatility_risk = RiskLevel.MEDIUM
            risk_score += 10
        else:
            volatility_risk = RiskLevel.LOW
            risk_score += 5

        # Time decay risk
        theta_ratio = abs(greeks.total_theta_dollars) / initial_value if initial_value > 0 else 0
        if greeks.total_theta_dollars < self.theta_warning_daily:
            time_decay_risk = RiskLevel.HIGH
            risk_score += 15
            key_risks.append(f"High theta decay: ${greeks.total_theta_dollars:.0f}/day")
        elif theta_ratio > 0.001:  # More than 0.1% per day
            time_decay_risk = RiskLevel.MEDIUM
            risk_score += 10
        else:
            time_decay_risk = RiskLevel.LOW
            risk_score += 5

        # Concentration risk
        total_value = sum(abs(p.market_value) for p in positions)
        max_concentration = 0
        if total_value > 0:
            for pos in positions:
                concentration = abs(pos.market_value) / total_value
                max_concentration = max(max_concentration, concentration)

        if max_concentration > self.concentration_warning:
            concentration_risk = RiskLevel.HIGH
            risk_score += 15
            key_risks.append(f"High concentration: {max_concentration * 100:.1f}% in single position")
        elif max_concentration > self.concentration_warning * 0.6:
            concentration_risk = RiskLevel.MEDIUM
            risk_score += 10
        else:
            concentration_risk = RiskLevel.LOW
            risk_score += 5

        # Liquidity risk (based on bid-ask spreads and volume - simplified)
        option_count = sum(1 for p in positions if p.is_option)
        total_positions = len(positions)
        option_ratio = option_count / total_positions if total_positions > 0 else 0

        if option_ratio > 0.7:
            liquidity_risk = RiskLevel.MEDIUM
            risk_score += 10
        else:
            liquidity_risk = RiskLevel.LOW
            risk_score += 5

        # VaR-based risk
        var_ratio = stats.var_95 / initial_value if initial_value > 0 else 0
        if var_ratio > self.var_warning_threshold:
            risk_score += 20
            key_risks.append(f"High VaR: {var_ratio * 100:.1f}% at 95% confidence")

        # Probability of loss
        if stats.probability_loss > 0.6:
            risk_score += 10
            key_risks.append(f"High loss probability: {stats.probability_loss * 100:.1f}%")

        # Determine overall level
        if risk_score >= 80:
            overall_level = RiskLevel.CRITICAL
        elif risk_score >= 60:
            overall_level = RiskLevel.HIGH
        elif risk_score >= 40:
            overall_level = RiskLevel.MEDIUM
        else:
            overall_level = RiskLevel.LOW

        risk_score = min(100, risk_score)

        assessment = RiskAssessment(
            overall_level=overall_level,
            risk_score=risk_score,
            market_risk=market_risk,
            volatility_risk=volatility_risk,
            time_decay_risk=time_decay_risk,
            concentration_risk=concentration_risk,
            liquidity_risk=liquidity_risk,
            var_95=stats.var_95,
            var_99=stats.var_99,
            max_loss_probability=stats.probability_loss,
            expected_shortfall=stats.cvar_95,
            key_risks=key_risks
        )

        logger.info(f"Risk assessment: {overall_level.value} (score: {risk_score})")
        for risk in key_risks:
            logger.warning(f"  - {risk}")

        return assessment

    def analyze_greeks(
        self,
        greeks: PortfolioGreeks,
        portfolio_value: float
    ) -> GreeksAssessment:
        """
        Analyze portfolio Greeks

        Args:
            greeks: Portfolio Greeks
            portfolio_value: Total portfolio value

        Returns:
            GreeksAssessment object
        """
        logger.info("Analyzing portfolio Greeks...")

        # Delta analysis
        delta_per_10k = (greeks.total_delta_dollars / portfolio_value * 10000) if portfolio_value > 0 else 0

        if abs(delta_per_10k) < self.delta_neutral_threshold * 10000:
            delta_neutral = True
            delta_bias = "neutral"
            delta_risk = RiskLevel.LOW
        else:
            delta_neutral = False
            delta_bias = "bullish" if greeks.total_delta > 0 else "bearish"
            if abs(delta_per_10k) > self.delta_neutral_threshold * 30000:
                delta_risk = RiskLevel.HIGH
            else:
                delta_risk = RiskLevel.MEDIUM

        # Gamma analysis
        gamma_dollars_pct = greeks.total_gamma_dollars / portfolio_value if portfolio_value > 0 else 0

        if abs(gamma_dollars_pct) > self.gamma_warning_threshold:
            gamma_risk = RiskLevel.HIGH
            gamma_warning = f"High gamma: ${greeks.total_gamma_dollars:,.0f} per 1% move"
        elif abs(gamma_dollars_pct) > self.gamma_warning_threshold * 0.5:
            gamma_risk = RiskLevel.MEDIUM
            gamma_warning = None
        else:
            gamma_risk = RiskLevel.LOW
            gamma_warning = None

        # Theta analysis
        theta_daily = greeks.total_theta_dollars
        if theta_daily < self.theta_warning_daily:
            theta_risk = RiskLevel.HIGH
            theta_assessment = f"Losing ${abs(theta_daily):.0f} daily to time decay. Consider adjusting short option positions."
        elif theta_daily < 0:
            theta_risk = RiskLevel.MEDIUM
            theta_assessment = f"Net theta decay of ${abs(theta_daily):.0f} daily."
        else:
            theta_risk = RiskLevel.LOW
            theta_assessment = f"Positive theta of ${theta_daily:.0f} daily from short options."

        # Vega analysis
        vega_pct = greeks.total_vega_dollars / portfolio_value if portfolio_value > 0 else 0

        if abs(vega_pct) > 0.05:
            vega_risk = RiskLevel.HIGH
            vega_warning = f"High vega: Portfolio {'gains' if greeks.total_vega_dollars > 0 else 'loses'} ${abs(greeks.total_vega_dollars):,.0f} per 1% IV change"
        elif abs(vega_pct) > 0.02:
            vega_risk = RiskLevel.MEDIUM
            vega_warning = None
        else:
            vega_risk = RiskLevel.LOW
            vega_warning = None

        assessment = GreeksAssessment(
            delta_neutral=delta_neutral,
            delta_bias=delta_bias,
            delta_risk_level=delta_risk,
            gamma_risk_level=gamma_risk,
            gamma_warning=gamma_warning,
            theta_daily=theta_daily,
            theta_assessment=theta_assessment,
            theta_risk_level=theta_risk,
            vega_exposure=greeks.total_vega_dollars,
            vega_risk_level=vega_risk,
            vega_warning=vega_warning
        )

        logger.info(f"Greeks assessment: Delta {delta_bias}, Theta ${theta_daily:.0f}/day")

        return assessment

    def analyze_concentration(
        self,
        positions: List[Position]
    ) -> List[ConcentrationWarning]:
        """
        Analyze position concentration

        Args:
            positions: List of positions

        Returns:
            List of ConcentrationWarning objects
        """
        logger.info("Analyzing concentration risk...")

        warnings = []
        total_value = sum(abs(p.market_value) for p in positions)

        if total_value == 0:
            return warnings

        # Symbol concentration
        symbol_values: Dict[str, float] = {}
        for pos in positions:
            symbol_values[pos.symbol] = symbol_values.get(pos.symbol, 0) + abs(pos.market_value)

        for symbol, value in symbol_values.items():
            pct = value / total_value
            if pct > self.concentration_warning:
                warnings.append(ConcentrationWarning(
                    type="symbol",
                    entity=symbol,
                    percentage=pct,
                    threshold=self.concentration_warning,
                    message=f"{symbol} represents {pct * 100:.1f}% of portfolio (threshold: {self.concentration_warning * 100:.0f}%)"
                ))

        # Expiry concentration (for options)
        expiry_values: Dict[str, float] = {}
        for pos in positions:
            if pos.is_option and pos.option_details:
                expiry = pos.option_details.expiry.strftime("%Y-%m-%d")
                expiry_values[expiry] = expiry_values.get(expiry, 0) + abs(pos.market_value)

        option_total = sum(expiry_values.values())
        if option_total > 0:
            for expiry, value in expiry_values.items():
                pct = value / option_total
                if pct > 0.5:  # 50% of options in one expiry
                    warnings.append(ConcentrationWarning(
                        type="expiry",
                        entity=expiry,
                        percentage=pct,
                        threshold=0.5,
                        message=f"{pct * 100:.1f}% of options expire on {expiry}"
                    ))

        for warning in warnings:
            logger.warning(f"Concentration: {warning.message}")

        return warnings

    def analyze_time_decay(
        self,
        positions: List[Position],
        greeks: PortfolioGreeks
    ) -> TimeDecayAnalysis:
        """
        Analyze time decay exposure

        Args:
            positions: List of positions
            greeks: Portfolio Greeks

        Returns:
            TimeDecayAnalysis object
        """
        logger.info("Analyzing time decay...")

        theta_daily = greeks.total_theta_dollars
        theta_weekly = theta_daily * 5  # Trading days

        # Find nearest expiry
        nearest_dte = None
        expiring_soon = 0

        for pos in positions:
            if pos.is_option and pos.option_details:
                dte = pos.option_details.days_to_expiry

                if nearest_dte is None or dte < nearest_dte:
                    nearest_dte = dte

                if dte <= 7:
                    expiring_soon += 1

        # Calculate theta to nearest expiry
        theta_to_expiry = theta_daily * nearest_dte if nearest_dte else 0

        # Roll recommendation
        roll_recommendation = None
        if expiring_soon > 0:
            roll_recommendation = f"Consider rolling {expiring_soon} position(s) expiring within 7 days to manage gamma risk"
        elif nearest_dte is not None and nearest_dte <= 14 and theta_daily < -50:
            roll_recommendation = f"Options expiring in {nearest_dte} days with significant theta. Consider rolling for premium capture."

        analysis = TimeDecayAnalysis(
            total_theta_daily=theta_daily,
            theta_per_week=theta_weekly,
            theta_to_expiry=theta_to_expiry,
            nearest_expiry_days=nearest_dte,
            expiring_soon_count=expiring_soon,
            roll_recommendation=roll_recommendation
        )

        logger.info(f"Time decay: ${theta_daily:.0f}/day, nearest expiry in {nearest_dte} days")

        return analysis

    def generate_recommendations(
        self,
        positions: List[Position],
        greeks: PortfolioGreeks,
        simulation: SimulationResult,
        risk_assessment: RiskAssessment,
        greeks_assessment: GreeksAssessment
    ) -> List[Recommendation]:
        """
        Generate investment recommendations

        Args:
            positions: List of positions
            greeks: Portfolio Greeks
            simulation: Simulation results
            risk_assessment: Risk assessment
            greeks_assessment: Greeks assessment

        Returns:
            List of Recommendation objects
        """
        logger.info("Generating recommendations...")

        recommendations = []
        stats = simulation.statistics

        # Delta hedging recommendation
        if not greeks_assessment.delta_neutral:
            if greeks_assessment.delta_risk_level == RiskLevel.HIGH:
                priority = Priority.HIGH
            else:
                priority = Priority.MEDIUM

            direction = "reduce long" if greeks.total_delta > 0 else "reduce short"
            hedge_shares = -int(greeks.total_delta)

            recommendations.append(Recommendation(
                type=RecommendationType.HEDGE,
                priority=priority,
                title="Delta Hedge Recommended",
                description=f"Portfolio has {greeks_assessment.delta_bias} delta bias of {greeks.total_delta:.0f} shares equivalent",
                reason=f"${greeks.total_delta_dollars:,.0f} directional exposure",
                suggested_action=f"{direction.title()} exposure by trading ~{abs(hedge_shares)} shares of SPY or underlying positions",
                potential_impact=f"Reduce directional risk by {abs(greeks.total_delta_dollars):,.0f}"
            ))

        # High theta warning
        if greeks_assessment.theta_risk_level == RiskLevel.HIGH:
            recommendations.append(Recommendation(
                type=RecommendationType.ADJUST,
                priority=Priority.HIGH,
                title="Reduce Time Decay",
                description=f"Portfolio losing ${abs(greeks.total_theta_dollars):.0f} daily to theta",
                reason="High negative theta eroding portfolio value",
                suggested_action="Consider closing or rolling long options, or selling options to offset theta",
                affected_positions=[p.symbol for p in positions if p.is_option and p.is_long],
                potential_impact=f"Save up to ${abs(greeks.total_theta_dollars * 5):.0f} per week"
            ))

        # High VaR warning
        var_pct = stats.var_95 / simulation.initial_portfolio_value * 100 if simulation.initial_portfolio_value > 0 else 0
        if var_pct > 10:
            recommendations.append(Recommendation(
                type=RecommendationType.HEDGE,
                priority=Priority.HIGH,
                title="Reduce Tail Risk",
                description=f"95% VaR is ${stats.var_95:,.0f} ({var_pct:.1f}% of portfolio)",
                reason="High potential loss in adverse scenarios",
                suggested_action="Consider buying protective puts or reducing position sizes",
                potential_impact=f"Limit worst-case losses to a smaller percentage"
            ))

        # High probability of loss
        if stats.probability_loss > 0.5:
            recommendations.append(Recommendation(
                type=RecommendationType.ADJUST,
                priority=Priority.MEDIUM,
                title="Improve Win Probability",
                description=f"{stats.probability_loss * 100:.1f}% probability of loss in {simulation.config.num_days} days",
                reason="Negative expected value in current configuration",
                suggested_action="Review position entry points and consider taking profits on winning positions"
            ))

        # Expiring options
        expiring_positions = [
            p for p in positions
            if p.is_option and p.option_details and p.option_details.days_to_expiry <= 7
        ]
        if expiring_positions:
            recommendations.append(Recommendation(
                type=RecommendationType.ROLL,
                priority=Priority.HIGH,
                title="Roll Expiring Options",
                description=f"{len(expiring_positions)} option(s) expiring within 7 days",
                reason="Options approaching expiry have accelerated theta and high gamma risk",
                suggested_action="Roll positions to later expirations or close",
                affected_positions=[p.symbol for p in expiring_positions],
                urgency_days=7
            ))

        # Vega warning
        if greeks_assessment.vega_risk_level == RiskLevel.HIGH:
            recommendations.append(Recommendation(
                type=RecommendationType.ADJUST,
                priority=Priority.MEDIUM,
                title="Manage Volatility Exposure",
                description=f"Portfolio {'gains' if greeks.total_vega_dollars > 0 else 'loses'} ${abs(greeks.total_vega_dollars):,.0f} per 1% IV change",
                reason="High sensitivity to volatility changes",
                suggested_action="Consider offsetting vega with opposite direction options or volatility products"
            ))

        # Take profit recommendation
        profitable_positions = [p for p in positions if p.unrealized_pnl > p.total_cost * 0.5]
        if profitable_positions:
            total_profit = sum(p.unrealized_pnl for p in profitable_positions)
            recommendations.append(Recommendation(
                type=RecommendationType.TAKE_PROFIT,
                priority=Priority.LOW,
                title="Consider Taking Profits",
                description=f"{len(profitable_positions)} position(s) with >50% unrealized gains",
                reason=f"Total unrealized profit of ${total_profit:,.0f}",
                suggested_action="Consider scaling out of profitable positions to lock in gains",
                affected_positions=[p.symbol for p in profitable_positions]
            ))

        # Stop loss recommendation
        losing_positions = [p for p in positions if p.unrealized_pnl < -p.total_cost * 0.3]
        if losing_positions:
            total_loss = sum(p.unrealized_pnl for p in losing_positions)
            recommendations.append(Recommendation(
                type=RecommendationType.STOP_LOSS,
                priority=Priority.MEDIUM,
                title="Review Losing Positions",
                description=f"{len(losing_positions)} position(s) with >30% loss",
                reason=f"Total unrealized loss of ${abs(total_loss):,.0f}",
                suggested_action="Evaluate if thesis is intact; consider cutting losses",
                affected_positions=[p.symbol for p in losing_positions]
            ))

        logger.info(f"Generated {len(recommendations)} recommendations")
        for rec in recommendations:
            logger.info(f"  [{rec.priority.value}] {rec.title}: {rec.description[:50]}...")

        return recommendations

    def generate_report(
        self,
        positions: List[Position],
        greeks: PortfolioGreeks,
        simulation: SimulationResult
    ) -> PortfolioAdvice:
        """
        Generate complete portfolio advice report

        Args:
            positions: List of positions
            greeks: Portfolio Greeks
            simulation: Simulation results

        Returns:
            PortfolioAdvice object
        """
        logger.info("=" * 60)
        logger.info("Generating Portfolio Advice Report")
        logger.info("=" * 60)

        portfolio_value = simulation.initial_portfolio_value

        # Run all analyses
        risk_assessment = self.analyze_risk(positions, simulation, greeks)
        greeks_assessment = self.analyze_greeks(greeks, portfolio_value)
        concentration_warnings = self.analyze_concentration(positions)
        time_decay_analysis = self.analyze_time_decay(positions, greeks)

        # Generate recommendations
        recommendations = self.generate_recommendations(
            positions, greeks, simulation,
            risk_assessment, greeks_assessment
        )

        # Generate summary
        stats = simulation.statistics
        summary = self._generate_summary(
            risk_assessment, greeks_assessment, stats, portfolio_value
        )

        # Compile immediate actions
        immediate_actions = []
        for rec in recommendations:
            if rec.priority == Priority.HIGH:
                immediate_actions.append(f"{rec.title}: {rec.suggested_action}")

        # Compile weekly review items
        weekly_review = [
            f"Review {len(positions)} positions for performance",
            f"Monitor theta decay: ${greeks.total_theta_dollars:.0f}/day",
            f"Track VaR: ${stats.var_95:,.0f} at 95% confidence",
        ]

        if greeks.days_to_nearest_expiry and greeks.days_to_nearest_expiry <= 14:
            weekly_review.append(f"Expiring options in {greeks.days_to_nearest_expiry} days - review roll strategy")

        advice = PortfolioAdvice(
            summary=summary,
            generated_at=datetime.now().isoformat(),
            risk_assessment=risk_assessment,
            greeks_assessment=greeks_assessment,
            concentration_warnings=concentration_warnings,
            time_decay_analysis=time_decay_analysis,
            recommendations=recommendations,
            immediate_actions=immediate_actions,
            weekly_review_items=weekly_review
        )

        logger.info("=" * 60)
        logger.info("Portfolio Advice Summary:")
        logger.info(f"  Risk Level: {risk_assessment.overall_level.value}")
        logger.info(f"  Risk Score: {risk_assessment.risk_score}/100")
        logger.info(f"  Recommendations: {len(recommendations)}")
        logger.info(f"  High Priority Actions: {len(immediate_actions)}")
        logger.info("=" * 60)

        return advice

    def _generate_summary(
        self,
        risk: RiskAssessment,
        greeks: GreeksAssessment,
        stats,
        portfolio_value: float
    ) -> str:
        """Generate executive summary text"""

        risk_text = {
            RiskLevel.LOW: "low risk profile",
            RiskLevel.MEDIUM: "moderate risk profile",
            RiskLevel.HIGH: "elevated risk profile requiring attention",
            RiskLevel.CRITICAL: "critical risk level requiring immediate action"
        }

        summary_parts = [
            f"Portfolio analysis indicates a {risk_text[risk.overall_level]}",
            f"with a risk score of {risk.risk_score}/100."
        ]

        if greeks.delta_bias != "neutral":
            summary_parts.append(f"The portfolio has a {greeks.delta_bias} bias.")

        if greeks.theta_daily < -50:
            summary_parts.append(f"Time decay is costing ${abs(greeks.theta_daily):.0f} per day.")

        expected_return = (stats.mean - portfolio_value) / portfolio_value * 100 if portfolio_value > 0 else 0
        if expected_return > 0:
            summary_parts.append(f"Expected return over simulation period is +{expected_return:.1f}%.")
        else:
            summary_parts.append(f"Expected return over simulation period is {expected_return:.1f}%.")

        if risk.key_risks:
            summary_parts.append(f"Key risks: {'; '.join(risk.key_risks[:3])}.")

        return " ".join(summary_parts)
