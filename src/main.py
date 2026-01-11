#!/usr/bin/env python3
"""
IB Portfolio Analysis System - Main Entry Point

盈透账户仓位分析系统主程序
- 读取IB账户仓位
- 计算希腊值
- 蒙特卡洛模拟
- 可视化输出
- 生成投资建议
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"

    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {}

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded configuration from {config_path}")
    return config


def run_analysis(
    simulation_mode: bool = True,
    num_paths: int = 10000,
    num_days: int = 30,
    output_dir: str = "output",
    config_path: str = None
) -> dict:
    """
    Run complete portfolio analysis

    Args:
        simulation_mode: Use simulated data instead of real IB connection
        num_paths: Number of Monte Carlo paths
        num_days: Number of days to simulate
        output_dir: Directory for output files
        config_path: Path to configuration file

    Returns:
        Dictionary with analysis results
    """
    from .ib_client import IBClient
    from .greeks import GreeksCalculator
    from .monte_carlo import MonteCarloSimulator
    from .visualizer import Visualizer
    from .advisor import PortfolioAdvisor

    logger.info("=" * 70)
    logger.info("  IB Portfolio Analysis System / 盈透账户仓位分析系统")
    logger.info("=" * 70)
    logger.info(f"  Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Mode: {'Simulation' if simulation_mode else 'Live IB Connection'}")
    logger.info(f"  Monte Carlo: {num_paths:,} paths x {num_days} days")
    logger.info("=" * 70)

    # Load configuration
    config = load_config(config_path)

    # Create output directories
    charts_dir = os.path.join(output_dir, "charts")
    reports_dir = os.path.join(output_dir, "reports")
    os.makedirs(charts_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    results = {}

    # Step 1: Connect to IB and get positions
    logger.info("\n" + "=" * 50)
    logger.info("Step 1: Connecting to IB and fetching positions")
    logger.info("=" * 50)

    ib_config = config.get("ib", {})
    client = IBClient(simulation_mode=simulation_mode)

    if not simulation_mode:
        connected = client.connect(
            host=ib_config.get("host", "127.0.0.1"),
            port=ib_config.get("port", 7497),
            client_id=ib_config.get("client_id", 1),
            timeout=ib_config.get("timeout", 30),
            readonly=ib_config.get("readonly", True)
        )
        if not connected:
            logger.error("Failed to connect to IB. Switching to simulation mode.")
            client = IBClient(simulation_mode=True)
            client.connect()
    else:
        client.connect()

    positions = client.get_positions()
    account_summary = client.get_account_summary()
    market_data = client.get_market_data(positions)

    results["positions"] = positions
    results["account_summary"] = account_summary
    results["market_data"] = market_data

    logger.info(f"Retrieved {len(positions)} positions")

    # Step 2: Calculate Greeks
    logger.info("\n" + "=" * 50)
    logger.info("Step 2: Calculating Portfolio Greeks")
    logger.info("=" * 50)

    greeks_config = config.get("greeks", {})
    greeks_calc = GreeksCalculator(
        risk_free_rate=greeks_config.get("risk_free_rate", 0.05),
        default_volatility=greeks_config.get("default_volatility", 0.25)
    )

    portfolio_greeks = greeks_calc.calculate_portfolio_greeks(positions, market_data)
    results["greeks"] = portfolio_greeks

    # Step 3: Run Monte Carlo Simulation
    logger.info("\n" + "=" * 50)
    logger.info("Step 3: Running Monte Carlo Simulation")
    logger.info("=" * 50)

    mc_config = config.get("monte_carlo", {})
    simulator = MonteCarloSimulator(
        num_paths=mc_config.get("num_paths", num_paths),
        num_days=mc_config.get("num_days", num_days),
        random_seed=mc_config.get("random_seed"),
        risk_free_rate=greeks_config.get("risk_free_rate", 0.05)
    )

    simulation = simulator.simulate_portfolio(positions, market_data)
    results["simulation"] = simulation

    # Run scenario analysis
    scenario_results = greeks_calc.scenario_analysis(positions, market_data)
    results["scenarios"] = scenario_results

    # Step 4: Generate Visualizations
    logger.info("\n" + "=" * 50)
    logger.info("Step 4: Generating Visualizations")
    logger.info("=" * 50)

    viz_config = config.get("visualization", {})
    visualizer = Visualizer(
        output_dir=charts_dir,
        dpi=viz_config.get("dpi", 150),
        figsize=tuple(viz_config.get("figure_size", [12, 8])),
        interactive=viz_config.get("interactive", True)
    )

    visualizer.plot_position_pie(positions)
    visualizer.plot_greeks_summary(portfolio_greeks)
    visualizer.plot_delta_exposure(portfolio_greeks)
    visualizer.plot_price_paths(simulation)
    visualizer.plot_return_distribution(simulation)
    visualizer.plot_var_analysis(simulation)
    visualizer.plot_scenario_heatmap(scenario_results)

    # Step 5: Generate Recommendations
    logger.info("\n" + "=" * 50)
    logger.info("Step 5: Generating Investment Recommendations")
    logger.info("=" * 50)

    risk_config = config.get("risk", {})
    advisor = PortfolioAdvisor(
        delta_neutral_threshold=risk_config.get("delta_neutral_threshold", 0.1),
        gamma_warning_threshold=risk_config.get("gamma_warning_threshold", 0.05),
        theta_warning_daily=risk_config.get("theta_decay_warning", -100),
        concentration_warning=risk_config.get("concentration_warning", 0.3)
    )

    advice = advisor.generate_report(positions, portfolio_greeks, simulation)
    results["advice"] = advice

    # Step 6: Generate HTML Report
    logger.info("\n" + "=" * 50)
    logger.info("Step 6: Generating HTML Report")
    logger.info("=" * 50)

    report_path = os.path.join(
        reports_dir,
        f"portfolio_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    visualizer.generate_html_report(
        positions, portfolio_greeks, simulation,
        advice.model_dump(),
        output_path=report_path
    )

    results["report_path"] = report_path

    # Final Summary
    logger.info("\n" + "=" * 70)
    logger.info("  Analysis Complete! / 分析完成!")
    logger.info("=" * 70)
    logger.info(f"  Portfolio Value: ${simulation.initial_portfolio_value:,.2f}")
    logger.info(f"  Expected Return ({num_days}D): {simulation.statistics.expected_return * 100:+.2f}%")
    logger.info(f"  95% VaR: ${simulation.statistics.var_95:,.2f}")
    logger.info(f"  Risk Level: {advice.risk_assessment.overall_level.value}")
    logger.info(f"  Recommendations: {len(advice.recommendations)}")
    logger.info("")
    logger.info(f"  Charts saved to: {charts_dir}")
    logger.info(f"  Report saved to: {report_path}")
    logger.info("=" * 70)

    # Print high priority recommendations
    high_priority = advice.get_high_priority_recommendations()
    if high_priority:
        logger.info("\n  HIGH PRIORITY ACTIONS:")
        for i, rec in enumerate(high_priority, 1):
            logger.warning(f"    {i}. {rec.title}")
            logger.warning(f"       {rec.suggested_action}")

    # Disconnect
    client.disconnect()

    return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="IB Portfolio Analysis System - 盈透账户仓位分析系统"
    )

    parser.add_argument(
        "--live", "-l",
        action="store_true",
        help="Connect to real IB TWS/Gateway (default: simulation mode)"
    )

    parser.add_argument(
        "--paths", "-p",
        type=int,
        default=10000,
        help="Number of Monte Carlo simulation paths (default: 10000)"
    )

    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="Number of days to simulate (default: 30)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output",
        help="Output directory for charts and reports (default: output)"
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to configuration file (default: config/config.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    try:
        results = run_analysis(
            simulation_mode=not args.live,
            num_paths=args.paths,
            num_days=args.days,
            output_dir=args.output,
            config_path=args.config
        )

        return 0

    except KeyboardInterrupt:
        logger.info("\nAnalysis cancelled by user")
        return 1

    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
