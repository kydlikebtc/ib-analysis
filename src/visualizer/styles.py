"""
Chart styling configuration
"""

from typing import Dict, List
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from loguru import logger


class ChartStyles:
    """Chart styling utilities"""

    # Color palettes
    COLORS = {
        "primary": "#2E86AB",
        "secondary": "#A23B72",
        "success": "#28A745",
        "danger": "#DC3545",
        "warning": "#FFC107",
        "info": "#17A2B8",
        "dark": "#343A40",
        "light": "#F8F9FA",
    }

    # Palette for multiple series
    PALETTE = [
        "#2E86AB",  # Blue
        "#A23B72",  # Magenta
        "#F18F01",  # Orange
        "#28A745",  # Green
        "#6C757D",  # Gray
        "#17A2B8",  # Cyan
        "#DC3545",  # Red
        "#6610F2",  # Purple
        "#20C997",  # Teal
        "#FFC107",  # Yellow
    ]

    # Greeks colors
    GREEKS_COLORS = {
        "delta": "#2E86AB",
        "gamma": "#A23B72",
        "theta": "#DC3545",
        "vega": "#28A745",
        "rho": "#6C757D",
    }

    # Position colors
    POSITION_COLORS = {
        "long": "#28A745",
        "short": "#DC3545",
        "stock": "#2E86AB",
        "call": "#28A745",
        "put": "#DC3545",
    }

    @classmethod
    def setup_matplotlib(cls, chinese_font: str = None) -> None:
        """
        Setup matplotlib with custom styling

        Args:
            chinese_font: Font name for Chinese characters
        """
        # Set style
        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except Exception:
            try:
                plt.style.use("seaborn-whitegrid")
            except Exception:
                plt.style.use("ggplot")

        # Configure font
        if chinese_font:
            try:
                # Try to find Chinese font
                font_paths = fm.findSystemFonts()
                chinese_fonts = [
                    "SimHei", "Microsoft YaHei", "STHeiti", "PingFang SC",
                    "Heiti SC", "WenQuanYi Micro Hei", "Source Han Sans"
                ]

                font_found = None
                for font_name in chinese_fonts:
                    for path in font_paths:
                        if font_name.lower() in path.lower():
                            font_found = font_name
                            break
                    if font_found:
                        break

                if font_found:
                    plt.rcParams["font.sans-serif"] = [font_found, "DejaVu Sans"]
                    plt.rcParams["axes.unicode_minus"] = False
                    logger.info(f"Using Chinese font: {font_found}")
                else:
                    logger.warning("No Chinese font found, using default")

            except Exception as e:
                logger.warning(f"Error setting Chinese font: {e}")

        # General settings
        plt.rcParams.update({
            "figure.figsize": (12, 8),
            "figure.dpi": 150,
            "axes.labelsize": 12,
            "axes.titlesize": 14,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.titlesize": 16,
        })

    @classmethod
    def get_color_gradient(cls, n: int, cmap: str = "viridis") -> List[str]:
        """
        Get a gradient of n colors

        Args:
            n: Number of colors needed
            cmap: Matplotlib colormap name

        Returns:
            List of hex color codes
        """
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors

        colormap = cm.get_cmap(cmap)
        colors = [colormap(i / (n - 1) if n > 1 else 0) for i in range(n)]
        return [mcolors.rgb2hex(c) for c in colors]

    @classmethod
    def format_currency(cls, value: float) -> str:
        """Format value as currency"""
        if abs(value) >= 1e6:
            return f"${value / 1e6:.1f}M"
        elif abs(value) >= 1e3:
            return f"${value / 1e3:.1f}K"
        else:
            return f"${value:.0f}"

    @classmethod
    def format_percentage(cls, value: float) -> str:
        """Format value as percentage"""
        return f"{value * 100:.1f}%"

    @classmethod
    def plotly_theme(cls, exclude: list = None) -> Dict:
        """
        Get Plotly theme configuration

        Args:
            exclude: List of keys to exclude from the layout

        Returns:
            Dict with layout configuration
        """
        layout = {
            "font": {"family": "Arial, sans-serif", "size": 12},
            "paper_bgcolor": "white",
            "plot_bgcolor": "rgba(248, 249, 250, 1)",
            "colorway": cls.PALETTE,
        }

        if exclude:
            for key in exclude:
                layout.pop(key, None)

        return {"layout": layout}

    @classmethod
    def default_legend(cls) -> Dict:
        """Get default legend configuration"""
        return {
            "bgcolor": "rgba(255, 255, 255, 0.8)",
            "bordercolor": "#E0E0E0",
            "borderwidth": 1,
        }
