"""
Chart generation for portfolio visualization
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import numpy as np
from loguru import logger

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not installed")

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("plotly not installed")

from ..ib_client.models import Position
from ..greeks.models import PortfolioGreeks
from ..monte_carlo.models import SimulationResult
from .styles import ChartStyles


class Visualizer:
    """
    Portfolio visualization generator

    Creates charts for positions, Greeks, Monte Carlo simulations,
    and comprehensive analysis reports.
    """

    def __init__(
        self,
        output_dir: str = "output/charts",
        dpi: int = 150,
        figsize: tuple = (12, 8),
        interactive: bool = True
    ):
        """
        Initialize Visualizer

        Args:
            output_dir: Directory for saving charts
            dpi: DPI for saved images
            figsize: Default figure size
            interactive: Generate interactive Plotly charts
        """
        self.output_dir = output_dir
        self.dpi = dpi
        self.figsize = figsize
        self.interactive = interactive and PLOTLY_AVAILABLE

        os.makedirs(output_dir, exist_ok=True)
        ChartStyles.setup_matplotlib()

        logger.info(f"Visualizer initialized. Output dir: {output_dir}")

    def plot_position_pie(
        self,
        positions: List[Position],
        save: bool = True
    ) -> Optional[Any]:
        """
        Create pie chart of position allocation by market value

        Args:
            positions: List of positions
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info("Generating position allocation pie chart...")

        # Group by symbol and aggregate
        position_values = {}
        for pos in positions:
            value = abs(pos.market_value)
            label = f"{pos.symbol}"
            if pos.is_option and pos.option_details:
                label += f" {pos.option_details.strike}{pos.option_details.right}"

            if label in position_values:
                position_values[label] += value
            else:
                position_values[label] = value

        labels = list(position_values.keys())
        values = list(position_values.values())

        if self.interactive:
            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                textinfo='label+percent',
                textposition='outside',
                marker=dict(colors=ChartStyles.PALETTE[:len(labels)])
            )])

            fig.update_layout(
                title="Portfolio Allocation by Market Value",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                **ChartStyles.plotly_theme()["layout"]
            )

            if save:
                fig.write_html(f"{self.output_dir}/position_pie.html")
                fig.write_image(f"{self.output_dir}/position_pie.png", scale=2)

            return fig

        else:
            fig, ax = plt.subplots(figsize=self.figsize)

            colors = ChartStyles.get_color_gradient(len(labels))
            wedges, texts, autotexts = ax.pie(
                values, labels=labels, autopct='%1.1f%%',
                colors=colors, pctdistance=0.85
            )

            centre_circle = plt.Circle((0, 0), 0.50, fc='white')
            ax.add_patch(centre_circle)

            ax.set_title("Portfolio Allocation by Market Value", fontsize=14, fontweight='bold')

            if save:
                plt.savefig(f"{self.output_dir}/position_pie.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def plot_greeks_summary(
        self,
        greeks: PortfolioGreeks,
        save: bool = True
    ) -> Optional[Any]:
        """
        Create bar chart summarizing portfolio Greeks

        Args:
            greeks: Portfolio Greeks object
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info("Generating Greeks summary chart...")

        greek_names = ['Delta ($)', 'Gamma ($)', 'Theta ($/day)', 'Vega ($/1%IV)']
        greek_values = [
            greeks.total_delta_dollars,
            greeks.total_gamma_dollars,
            greeks.total_theta_dollars,
            greeks.total_vega_dollars
        ]

        colors = [
            ChartStyles.GREEKS_COLORS['delta'],
            ChartStyles.GREEKS_COLORS['gamma'],
            ChartStyles.GREEKS_COLORS['theta'],
            ChartStyles.GREEKS_COLORS['vega']
        ]

        if self.interactive:
            fig = go.Figure(data=[go.Bar(
                x=greek_names,
                y=greek_values,
                marker_color=colors,
                text=[f"${v:,.0f}" for v in greek_values],
                textposition='outside'
            )])

            fig.update_layout(
                title="Portfolio Greeks Summary (Dollar Values)",
                xaxis_title="Greek",
                yaxis_title="Dollar Value",
                showlegend=False,
                **ChartStyles.plotly_theme()["layout"]
            )

            # Add zero line
            fig.add_hline(y=0, line_dash="dash", line_color="gray")

            if save:
                fig.write_html(f"{self.output_dir}/greeks_summary.html")
                fig.write_image(f"{self.output_dir}/greeks_summary.png", scale=2)

            return fig

        else:
            fig, ax = plt.subplots(figsize=self.figsize)

            bars = ax.bar(greek_names, greek_values, color=colors, edgecolor='black')
            ax.axhline(y=0, color='gray', linestyle='--', alpha=0.7)

            # Add value labels
            for bar, val in zip(bars, greek_values):
                height = bar.get_height()
                ax.annotate(f'${val:,.0f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=10)

            ax.set_ylabel('Dollar Value')
            ax.set_title('Portfolio Greeks Summary', fontsize=14, fontweight='bold')

            if save:
                plt.savefig(f"{self.output_dir}/greeks_summary.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def plot_delta_exposure(
        self,
        greeks: PortfolioGreeks,
        save: bool = True
    ) -> Optional[Any]:
        """
        Create chart showing delta exposure by underlying

        Args:
            greeks: Portfolio Greeks object
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info("Generating delta exposure chart...")

        symbols = list(greeks.by_underlying.keys())
        deltas = [greeks.by_underlying[s].greeks.delta for s in symbols]
        delta_dollars = [greeks.by_underlying[s].greeks.delta_dollars for s in symbols]

        colors = [ChartStyles.COLORS['success'] if d > 0 else ChartStyles.COLORS['danger']
                  for d in deltas]

        if self.interactive:
            fig = make_subplots(rows=1, cols=2,
                               subplot_titles=("Delta (Shares Equivalent)", "Delta (Dollar Exposure)"))

            fig.add_trace(
                go.Bar(x=symbols, y=deltas, marker_color=colors, name="Delta",
                      text=[f"{d:+.0f}" for d in deltas], textposition='outside'),
                row=1, col=1
            )

            fig.add_trace(
                go.Bar(x=symbols, y=delta_dollars, marker_color=colors, name="Delta $",
                      text=[f"${d:+,.0f}" for d in delta_dollars], textposition='outside'),
                row=1, col=2
            )

            fig.update_layout(
                title="Delta Exposure by Underlying",
                showlegend=False,
                height=500,
                **ChartStyles.plotly_theme()["layout"]
            )

            # Add zero lines
            fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
            fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=2)

            if save:
                fig.write_html(f"{self.output_dir}/delta_exposure.html")
                fig.write_image(f"{self.output_dir}/delta_exposure.png", scale=2)

            return fig

        else:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            ax1.bar(symbols, deltas, color=colors, edgecolor='black')
            ax1.axhline(y=0, color='gray', linestyle='--')
            ax1.set_ylabel('Delta (Shares)')
            ax1.set_title('Delta by Underlying')

            ax2.bar(symbols, delta_dollars, color=colors, edgecolor='black')
            ax2.axhline(y=0, color='gray', linestyle='--')
            ax2.set_ylabel('Delta ($)')
            ax2.set_title('Dollar Delta by Underlying')

            plt.suptitle('Delta Exposure Analysis', fontsize=14, fontweight='bold')
            plt.tight_layout()

            if save:
                plt.savefig(f"{self.output_dir}/delta_exposure.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def plot_price_paths(
        self,
        simulation: SimulationResult,
        symbol: str = None,
        num_paths: int = 100,
        save: bool = True
    ) -> Optional[Any]:
        """
        Create fan chart of simulated price paths

        Args:
            simulation: Simulation result object
            symbol: Symbol to plot (if None, plots portfolio value)
            num_paths: Number of paths to display
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info(f"Generating price paths chart ({num_paths} paths)...")

        if symbol and symbol in simulation.price_paths_by_symbol:
            paths = np.array(simulation.price_paths_by_symbol[symbol])[:num_paths]
            title = f"{symbol} Price Simulation ({simulation.config.num_days} Days)"
            ylabel = "Price ($)"
        else:
            paths = np.array(simulation.portfolio_value_paths)[:num_paths]
            title = f"Portfolio Value Simulation ({simulation.config.num_days} Days)"
            ylabel = "Portfolio Value ($)"

        days = np.arange(paths.shape[1])

        # Calculate percentile bands
        all_paths = np.array(simulation.portfolio_value_paths) if symbol is None else \
                    np.array(simulation.price_paths_by_symbol.get(symbol, paths))

        p5 = np.percentile(all_paths, 5, axis=0)
        p25 = np.percentile(all_paths, 25, axis=0)
        p50 = np.percentile(all_paths, 50, axis=0)
        p75 = np.percentile(all_paths, 75, axis=0)
        p95 = np.percentile(all_paths, 95, axis=0)

        if self.interactive:
            fig = go.Figure()

            # Add sample paths (faint)
            for i in range(min(num_paths, 50)):
                fig.add_trace(go.Scatter(
                    x=days, y=paths[i],
                    mode='lines',
                    line=dict(width=0.5, color='rgba(100, 100, 100, 0.1)'),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            # Add percentile bands
            fig.add_trace(go.Scatter(
                x=np.concatenate([days, days[::-1]]),
                y=np.concatenate([p95, p5[::-1]]),
                fill='toself',
                fillcolor='rgba(46, 134, 171, 0.2)',
                line=dict(width=0),
                name='5%-95% Band',
                hoverinfo='skip'
            ))

            fig.add_trace(go.Scatter(
                x=np.concatenate([days, days[::-1]]),
                y=np.concatenate([p75, p25[::-1]]),
                fill='toself',
                fillcolor='rgba(46, 134, 171, 0.4)',
                line=dict(width=0),
                name='25%-75% Band',
                hoverinfo='skip'
            ))

            # Add median
            fig.add_trace(go.Scatter(
                x=days, y=p50,
                mode='lines',
                line=dict(width=2, color=ChartStyles.COLORS['primary']),
                name='Median'
            ))

            # Add initial value line
            fig.add_hline(y=paths[0, 0], line_dash="dash",
                         line_color=ChartStyles.COLORS['dark'],
                         annotation_text=f"Initial: ${paths[0, 0]:,.0f}")

            fig.update_layout(
                title=title,
                xaxis_title="Days",
                yaxis_title=ylabel,
                hovermode="x unified",
                **ChartStyles.plotly_theme()["layout"]
            )

            if save:
                fig.write_html(f"{self.output_dir}/price_paths.html")
                fig.write_image(f"{self.output_dir}/price_paths.png", scale=2)

            return fig

        else:
            fig, ax = plt.subplots(figsize=self.figsize)

            # Plot sample paths
            for i in range(min(num_paths, 50)):
                ax.plot(days, paths[i], alpha=0.1, color='gray', linewidth=0.5)

            # Plot percentile bands
            ax.fill_between(days, p5, p95, alpha=0.2, color=ChartStyles.COLORS['primary'], label='5%-95%')
            ax.fill_between(days, p25, p75, alpha=0.4, color=ChartStyles.COLORS['primary'], label='25%-75%')
            ax.plot(days, p50, color=ChartStyles.COLORS['primary'], linewidth=2, label='Median')

            # Initial value line
            ax.axhline(y=paths[0, 0], color='black', linestyle='--', alpha=0.5)

            ax.set_xlabel('Days')
            ax.set_ylabel(ylabel)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.legend(loc='upper left')

            if save:
                plt.savefig(f"{self.output_dir}/price_paths.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def plot_return_distribution(
        self,
        simulation: SimulationResult,
        save: bool = True
    ) -> Optional[Any]:
        """
        Create histogram of return distribution

        Args:
            simulation: Simulation result object
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info("Generating return distribution chart...")

        returns = np.array(simulation.return_distribution) * 100  # Convert to percentage
        stats = simulation.statistics

        if self.interactive:
            fig = go.Figure()

            # Histogram
            fig.add_trace(go.Histogram(
                x=returns,
                nbinsx=50,
                name='Return Distribution',
                marker_color=ChartStyles.COLORS['primary'],
                opacity=0.7
            ))

            # Add VaR lines
            var_95_return = (stats.var_95 / simulation.initial_portfolio_value) * 100
            var_99_return = (stats.var_99 / simulation.initial_portfolio_value) * 100

            fig.add_vline(x=-var_95_return, line_dash="dash",
                         line_color=ChartStyles.COLORS['warning'],
                         annotation_text=f"95% VaR: {-var_95_return:.1f}%")

            fig.add_vline(x=-var_99_return, line_dash="dash",
                         line_color=ChartStyles.COLORS['danger'],
                         annotation_text=f"99% VaR: {-var_99_return:.1f}%")

            # Add mean line
            fig.add_vline(x=stats.expected_return * 100, line_dash="solid",
                         line_color=ChartStyles.COLORS['success'],
                         annotation_text=f"Expected: {stats.expected_return * 100:.1f}%")

            # Add zero line
            fig.add_vline(x=0, line_dash="dot", line_color="gray")

            fig.update_layout(
                title=f"Return Distribution ({simulation.config.num_days}-Day Simulation)",
                xaxis_title="Return (%)",
                yaxis_title="Frequency",
                showlegend=False,
                **ChartStyles.plotly_theme()["layout"]
            )

            # Add statistics annotation
            fig.add_annotation(
                x=0.95, y=0.95, xref="paper", yref="paper",
                text=f"Mean: {stats.expected_return * 100:.2f}%<br>"
                     f"Std Dev: {stats.std / simulation.initial_portfolio_value * 100:.2f}%<br>"
                     f"Prob Loss: {stats.probability_loss * 100:.1f}%<br>"
                     f"Sharpe: {stats.sharpe_ratio:.2f}",
                showarrow=False,
                font=dict(size=10),
                align="right",
                bgcolor="white",
                bordercolor="gray",
                borderwidth=1
            )

            if save:
                fig.write_html(f"{self.output_dir}/return_distribution.html")
                fig.write_image(f"{self.output_dir}/return_distribution.png", scale=2)

            return fig

        else:
            fig, ax = plt.subplots(figsize=self.figsize)

            ax.hist(returns, bins=50, color=ChartStyles.COLORS['primary'],
                   alpha=0.7, edgecolor='white')

            # Add VaR lines
            var_95_return = (stats.var_95 / simulation.initial_portfolio_value) * 100
            var_99_return = (stats.var_99 / simulation.initial_portfolio_value) * 100

            ax.axvline(x=-var_95_return, color=ChartStyles.COLORS['warning'],
                      linestyle='--', label=f'95% VaR: {-var_95_return:.1f}%')
            ax.axvline(x=-var_99_return, color=ChartStyles.COLORS['danger'],
                      linestyle='--', label=f'99% VaR: {-var_99_return:.1f}%')
            ax.axvline(x=0, color='gray', linestyle=':', alpha=0.5)

            ax.set_xlabel('Return (%)')
            ax.set_ylabel('Frequency')
            ax.set_title(f'Return Distribution ({simulation.config.num_days}-Day Simulation)',
                        fontsize=14, fontweight='bold')
            ax.legend()

            if save:
                plt.savefig(f"{self.output_dir}/return_distribution.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def plot_var_analysis(
        self,
        simulation: SimulationResult,
        save: bool = True
    ) -> Optional[Any]:
        """
        Create VaR visualization with expected shortfall

        Args:
            simulation: Simulation result object
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info("Generating VaR analysis chart...")

        pnl = np.array(simulation.pnl_distribution)
        stats = simulation.statistics

        if self.interactive:
            fig = make_subplots(rows=1, cols=2,
                               subplot_titles=("P&L Distribution with VaR", "Daily VaR Evolution"))

            # P&L histogram with VaR
            fig.add_trace(
                go.Histogram(x=pnl, nbinsx=50, name='P&L',
                            marker_color=ChartStyles.COLORS['primary'], opacity=0.7),
                row=1, col=1
            )

            # VaR lines
            fig.add_vline(x=-stats.var_95, line_dash="dash",
                         line_color=ChartStyles.COLORS['warning'], row=1, col=1,
                         annotation_text=f"95% VaR: ${stats.var_95:,.0f}")
            fig.add_vline(x=-stats.var_99, line_dash="dash",
                         line_color=ChartStyles.COLORS['danger'], row=1, col=1,
                         annotation_text=f"99% VaR: ${stats.var_99:,.0f}")

            # CVaR shading (Expected Shortfall)
            pnl_sorted = np.sort(pnl)
            var_95_idx = int(len(pnl) * 0.05)
            tail_pnl = pnl_sorted[:var_95_idx]

            fig.add_trace(
                go.Histogram(x=tail_pnl, nbinsx=20, name='CVaR Region',
                            marker_color=ChartStyles.COLORS['danger'], opacity=0.5),
                row=1, col=1
            )

            # Daily VaR evolution
            days = list(range(len(simulation.daily_var_95)))
            fig.add_trace(
                go.Scatter(x=days, y=simulation.daily_var_95,
                          mode='lines', name='5% Percentile',
                          line=dict(color=ChartStyles.COLORS['danger'])),
                row=1, col=2
            )

            fig.add_trace(
                go.Scatter(x=days, y=simulation.daily_mean,
                          mode='lines', name='Expected Value',
                          line=dict(color=ChartStyles.COLORS['primary'])),
                row=1, col=2
            )

            fig.update_layout(
                title="Value at Risk Analysis",
                height=500,
                showlegend=True,
                **ChartStyles.plotly_theme()["layout"]
            )

            if save:
                fig.write_html(f"{self.output_dir}/var_analysis.html")
                fig.write_image(f"{self.output_dir}/var_analysis.png", scale=2)

            return fig

        else:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            # P&L histogram
            ax1.hist(pnl, bins=50, color=ChartStyles.COLORS['primary'], alpha=0.7)
            ax1.axvline(x=-stats.var_95, color=ChartStyles.COLORS['warning'],
                       linestyle='--', label=f'95% VaR: ${stats.var_95:,.0f}')
            ax1.axvline(x=-stats.var_99, color=ChartStyles.COLORS['danger'],
                       linestyle='--', label=f'99% VaR: ${stats.var_99:,.0f}')
            ax1.set_xlabel('P&L ($)')
            ax1.set_ylabel('Frequency')
            ax1.set_title('P&L Distribution')
            ax1.legend()

            # Daily VaR evolution
            days = list(range(len(simulation.daily_var_95)))
            ax2.plot(days, simulation.daily_var_95, color=ChartStyles.COLORS['danger'],
                    label='5% Percentile')
            ax2.plot(days, simulation.daily_mean, color=ChartStyles.COLORS['primary'],
                    label='Expected')
            ax2.fill_between(days, simulation.daily_var_95, simulation.daily_mean,
                            alpha=0.2, color=ChartStyles.COLORS['danger'])
            ax2.set_xlabel('Days')
            ax2.set_ylabel('Portfolio Value ($)')
            ax2.set_title('Daily VaR Evolution')
            ax2.legend()

            plt.suptitle('Value at Risk Analysis', fontsize=14, fontweight='bold')
            plt.tight_layout()

            if save:
                plt.savefig(f"{self.output_dir}/var_analysis.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def plot_scenario_heatmap(
        self,
        scenario_results: Dict[str, Dict[str, float]],
        save: bool = True
    ) -> Optional[Any]:
        """
        Create heatmap for scenario analysis

        Args:
            scenario_results: Nested dict of spot_change -> iv_change -> P&L
            save: Whether to save the chart

        Returns:
            Figure object
        """
        logger.info("Generating scenario heatmap...")

        # Convert to matrix
        spot_labels = list(scenario_results.keys())
        iv_labels = list(list(scenario_results.values())[0].keys())

        z = [[scenario_results[spot][iv] for iv in iv_labels] for spot in spot_labels]

        if self.interactive:
            fig = go.Figure(data=go.Heatmap(
                z=z,
                x=iv_labels,
                y=spot_labels,
                colorscale='RdYlGn',
                zmid=0,
                text=[[f"${v:,.0f}" for v in row] for row in z],
                texttemplate="%{text}",
                textfont={"size": 10},
                hovertemplate="Spot: %{y}<br>IV: %{x}<br>P&L: $%{z:,.0f}<extra></extra>"
            ))

            fig.update_layout(
                title="Scenario Analysis: P&L by Spot and IV Changes",
                xaxis_title="IV Change",
                yaxis_title="Spot Change",
                **ChartStyles.plotly_theme()["layout"]
            )

            if save:
                fig.write_html(f"{self.output_dir}/scenario_heatmap.html")
                fig.write_image(f"{self.output_dir}/scenario_heatmap.png", scale=2)

            return fig

        else:
            fig, ax = plt.subplots(figsize=self.figsize)

            im = ax.imshow(z, cmap='RdYlGn', aspect='auto')

            ax.set_xticks(range(len(iv_labels)))
            ax.set_yticks(range(len(spot_labels)))
            ax.set_xticklabels(iv_labels)
            ax.set_yticklabels(spot_labels)

            plt.colorbar(im, label='P&L ($)')

            # Add text annotations
            for i in range(len(spot_labels)):
                for j in range(len(iv_labels)):
                    ax.text(j, i, f"${z[i][j]:,.0f}",
                           ha='center', va='center', fontsize=8)

            ax.set_xlabel('IV Change')
            ax.set_ylabel('Spot Change')
            ax.set_title('Scenario Analysis Heatmap', fontsize=14, fontweight='bold')

            if save:
                plt.savefig(f"{self.output_dir}/scenario_heatmap.png", dpi=self.dpi, bbox_inches='tight')
                plt.close()

            return fig

    def generate_html_report(
        self,
        positions: List[Position],
        greeks: PortfolioGreeks,
        simulation: SimulationResult,
        advice: Dict = None,
        output_path: str = None
    ) -> str:
        """
        Generate comprehensive HTML report

        Args:
            positions: List of positions
            greeks: Portfolio Greeks
            simulation: Simulation result
            advice: Portfolio advice dictionary
            output_path: Output file path

        Returns:
            Path to generated report
        """
        logger.info("Generating comprehensive HTML report...")

        if output_path is None:
            output_path = f"{self.output_dir}/../reports/portfolio_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Create symlink to charts directory for HTML report to find charts
        report_dir = os.path.dirname(output_path)
        charts_link = os.path.join(report_dir, "charts")
        if not os.path.exists(charts_link):
            try:
                os.symlink(self.output_dir, charts_link)
            except OSError:
                pass  # Symlink may already exist or not supported

        # Generate all charts first
        self.plot_position_pie(positions)
        self.plot_greeks_summary(greeks)
        self.plot_delta_exposure(greeks)
        self.plot_price_paths(simulation)
        self.plot_return_distribution(simulation)
        self.plot_var_analysis(simulation)

        # Get summary data
        stats = simulation.statistics
        greek_summary = greeks.summary_dict()
        sim_summary = simulation.summary()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Portfolio Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px; }}
        h2 {{ color: #343A40; margin-top: 30px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .summary-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB; }}
        .summary-card.danger {{ border-left-color: #DC3545; }}
        .summary-card.success {{ border-left-color: #28A745; }}
        .summary-card.warning {{ border-left-color: #FFC107; }}
        .summary-card h3 {{ margin: 0 0 5px 0; font-size: 14px; color: #6c757d; }}
        .summary-card .value {{ font-size: 24px; font-weight: bold; color: #343A40; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background-color: #2E86AB; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .chart-container {{ margin: 20px 0; text-align: center; }}
        .chart-container img {{ max-width: 100%; border: 1px solid #dee2e6; border-radius: 4px; }}
        .risk-badge {{ display: inline-block; padding: 5px 10px; border-radius: 4px; color: white; font-weight: bold; }}
        .risk-low {{ background-color: #28A745; }}
        .risk-medium {{ background-color: #FFC107; color: #343A40; }}
        .risk-high {{ background-color: #DC3545; }}
        .recommendation {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #FFC107; }}
        .timestamp {{ color: #6c757d; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Portfolio Analysis Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>Executive Summary</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <h3>Portfolio Value</h3>
                <div class="value">${simulation.initial_portfolio_value:,.0f}</div>
            </div>
            <div class="summary-card {'success' if stats.expected_return > 0 else 'danger'}">
                <h3>Expected Return ({simulation.config.num_days}D)</h3>
                <div class="value">{stats.expected_return * 100:+.2f}%</div>
            </div>
            <div class="summary-card danger">
                <h3>95% VaR</h3>
                <div class="value">${stats.var_95:,.0f}</div>
            </div>
            <div class="summary-card {'danger' if stats.probability_loss > 0.5 else 'success'}">
                <h3>Probability of Loss</h3>
                <div class="value">{stats.probability_loss * 100:.1f}%</div>
            </div>
        </div>

        <h2>Greeks Summary</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <h3>Total Delta ($)</h3>
                <div class="value">${greek_summary['delta_dollars']:,.0f}</div>
            </div>
            <div class="summary-card {'danger' if greek_summary['theta_dollars'] < -50 else ''}">
                <h3>Daily Theta</h3>
                <div class="value">${greek_summary['theta_dollars']:,.0f}/day</div>
            </div>
            <div class="summary-card">
                <h3>Vega Exposure</h3>
                <div class="value">${greek_summary['vega_dollars']:,.0f}</div>
            </div>
            <div class="summary-card">
                <h3>Weighted Avg IV</h3>
                <div class="value">{greek_summary['weighted_avg_iv']:.1f}%</div>
            </div>
        </div>

        <h2>Position Allocation</h2>
        <div class="chart-container">
            <iframe src="charts/position_pie.html" width="100%" height="500" frameborder="0"></iframe>
        </div>

        <h2>Greeks Analysis</h2>
        <div class="chart-container">
            <iframe src="charts/greeks_summary.html" width="100%" height="500" frameborder="0"></iframe>
        </div>

        <h2>Delta Exposure</h2>
        <div class="chart-container">
            <iframe src="charts/delta_exposure.html" width="100%" height="500" frameborder="0"></iframe>
        </div>

        <h2>Monte Carlo Simulation ({simulation.config.num_paths:,} paths, {simulation.config.num_days} days)</h2>
        <div class="chart-container">
            <iframe src="charts/price_paths.html" width="100%" height="600" frameborder="0"></iframe>
        </div>

        <h2>Return Distribution</h2>
        <div class="chart-container">
            <iframe src="charts/return_distribution.html" width="100%" height="500" frameborder="0"></iframe>
        </div>

        <h2>Risk Analysis (VaR)</h2>
        <div class="chart-container">
            <iframe src="charts/var_analysis.html" width="100%" height="500" frameborder="0"></iframe>
        </div>

        <h2>Simulation Statistics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Expected Final Value</td><td>${stats.mean:,.2f}</td></tr>
            <tr><td>Standard Deviation</td><td>${stats.std:,.2f}</td></tr>
            <tr><td>95% VaR</td><td>${stats.var_95:,.2f}</td></tr>
            <tr><td>99% VaR</td><td>${stats.var_99:,.2f}</td></tr>
            <tr><td>95% CVaR (Expected Shortfall)</td><td>${stats.cvar_95:,.2f}</td></tr>
            <tr><td>Maximum Drawdown</td><td>{stats.max_drawdown * 100:.2f}%</td></tr>
            <tr><td>Sharpe Ratio (Annualized)</td><td>{stats.sharpe_ratio:.2f}</td></tr>
            <tr><td>Sortino Ratio</td><td>{stats.sortino_ratio:.2f}</td></tr>
            <tr><td>Skewness</td><td>{stats.skewness:.2f}</td></tr>
            <tr><td>Kurtosis</td><td>{stats.kurtosis:.2f}</td></tr>
        </table>

        <h2>Positions Detail</h2>
        <table>
            <tr>
                <th>Symbol</th>
                <th>Type</th>
                <th>Quantity</th>
                <th>Avg Cost</th>
                <th>Market Value</th>
                <th>P&L</th>
            </tr>
            {''.join(f'''
            <tr>
                <td>{pos.symbol}{f" {pos.option_details.strike}{pos.option_details.right}" if pos.option_details else ""}</td>
                <td>{pos.sec_type}</td>
                <td>{pos.position:+.0f}</td>
                <td>${pos.avg_cost:.2f}</td>
                <td>${pos.market_value:,.2f}</td>
                <td style="color: {'green' if pos.unrealized_pnl >= 0 else 'red'}">${pos.unrealized_pnl:+,.2f}</td>
            </tr>
            ''' for pos in positions)}
        </table>

    </div>
</body>
</html>
        """

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML report generated: {output_path}")
        return output_path

    def save_all_charts(self) -> List[str]:
        """
        Save all generated charts

        Returns:
            List of saved file paths
        """
        saved_files = []
        for filename in os.listdir(self.output_dir):
            if filename.endswith(('.png', '.html')):
                saved_files.append(os.path.join(self.output_dir, filename))

        logger.info(f"Saved {len(saved_files)} chart files")
        return saved_files
