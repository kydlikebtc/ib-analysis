#!/Users/kyd/ib-analysis/.venv/bin/python3
"""
IB Portfolio Analyzer - Native Messaging Host
处理来自 Chrome 扩展的请求，连接 IB API 获取数据

Native Messaging 协议:
- 输入: 4字节长度（little-endian）+ JSON消息
- 输出: 4字节长度（little-endian）+ JSON响应
"""

import sys
import json
import struct
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置日志
LOG_DIR = PROJECT_ROOT / "extension" / "native-host" / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=str(LOG_DIR / "native_host.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NativeMessagingHost:
    """Native Messaging 主机"""

    def __init__(self):
        self.ib_client = None
        self.greeks_calculator = None
        self.monte_carlo = None
        self.advisor = None
        logger.info("Native Host 初始化")

    def run(self):
        """主循环：读取消息并处理"""
        logger.info("Native Host 开始运行")

        while True:
            try:
                message = self._read_message()
                if message is None:
                    logger.info("输入流关闭，退出")
                    break

                logger.debug(f"收到消息: {message}")
                response = self._handle_message(message)
                logger.debug(f"发送响应: {response}")
                self._send_message(response)

            except Exception as e:
                logger.error(f"处理消息时出错: {e}\n{traceback.format_exc()}")
                self._send_message({
                    "success": False,
                    "error": str(e)
                })

    def _read_message(self) -> Optional[Dict]:
        """读取 Native Messaging 格式的消息"""
        # 读取4字节长度
        raw_length = sys.stdin.buffer.read(4)
        if not raw_length:
            return None

        message_length = struct.unpack('<I', raw_length)[0]

        # 读取消息内容
        message_data = sys.stdin.buffer.read(message_length)
        return json.loads(message_data.decode('utf-8'))

    def _send_message(self, message: Dict):
        """发送 Native Messaging 格式的响应"""
        encoded = json.dumps(message, ensure_ascii=False).encode('utf-8')

        # 写入4字节长度 + 消息
        sys.stdout.buffer.write(struct.pack('<I', len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()

    def _handle_message(self, message: Dict) -> Dict:
        """处理消息并返回响应"""
        action = message.get('action', '')
        params = message.get('params', {})

        handlers = {
            'ping': self._handle_ping,
            'get_portfolio': self._handle_get_portfolio,
            'generate_report': self._handle_generate_report,
            'get_positions': self._handle_get_positions,
            'get_greeks': self._handle_get_greeks,
            'get_risk': self._handle_get_risk,
            'test_connection': self._handle_test_connection,
            'get_settings': self._handle_get_settings,
        }

        handler = handlers.get(action)
        if handler:
            return handler(params)
        else:
            return {
                "success": False,
                "error": f"未知的操作: {action}"
            }

    def _handle_ping(self, params: Dict) -> Dict:
        """健康检查"""
        return {
            "success": True,
            "message": "pong",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }

    def _handle_get_portfolio(self, params: Dict) -> Dict:
        """获取完整投资组合数据"""
        try:
            # 尝试连接真实的 IB API
            try:
                from src.ib_client.client import IBClient
                from src.greeks.calculator import GreeksCalculator
                from src.monte_carlo.simulator import MonteCarloSimulator
                from src.advisor.investment_advisor import InvestmentAdvisor

                # 连接 IB
                ib_client = IBClient()
                if not ib_client.connect():
                    raise ConnectionError("无法连接到 TWS/IB Gateway")

                # 获取真实数据
                positions = ib_client.get_positions()
                account = ib_client.get_account_summary()

                # 计算希腊值
                calculator = GreeksCalculator()
                greeks_summary = calculator.calculate_portfolio_greeks(positions)

                # 风险分析
                advisor = InvestmentAdvisor()
                analysis = advisor.analyze(positions, account)

                ib_client.disconnect()

                return {
                    "success": True,
                    "data": {
                        "account": {
                            "net_liquidation": account.get('NetLiquidation', 0),
                            "unrealized_pnl": account.get('UnrealizedPnL', 0),
                            "daily_pnl": account.get('RealizedPnL', 0),
                        },
                        "greeks": greeks_summary,
                        "risk": analysis.get('risk_assessment', {}),
                        "recommendations": analysis.get('recommendations', []),
                        "positions": [self._format_position(p) for p in positions]
                    }
                }

            except ImportError:
                logger.warning("IB 模块未安装，使用模拟数据")
                return self._get_simulated_portfolio()

            except ConnectionError as e:
                logger.warning(f"IB 连接失败: {e}，使用模拟数据")
                return self._get_simulated_portfolio()

        except Exception as e:
            logger.error(f"获取投资组合失败: {e}\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_simulated_portfolio(self) -> Dict:
        """
        返回模拟的投资组合数据（用于测试）

        包含多种资产类型:
        - STK (股票): AAPL, MSFT
        - OPT (期权): AAPL Call, SPY Put
        - FUT (期货): ES (E-mini S&P 500)
        - FUND (基金/ETF): SPY, QQQ
        - CASH (外汇): EUR.USD
        - CRYPTO (加密货币): BTC
        """
        return {
            "success": True,
            "data": {
                "account": {
                    "net_liquidation": 185000.00,
                    "unrealized_pnl": 5750.50,
                    "daily_pnl": 1250.25,
                },
                "greeks": {
                    "delta": 0.78,
                    "delta_dollars": 14425.00,
                    "gamma": 0.02,
                    "gamma_dollars": 250.00,
                    "theta": -0.15,
                    "theta_dollars": -187.50,
                    "vega": 0.35,
                    "vega_dollars": 437.50,
                },
                "risk": {
                    "level": "MEDIUM",
                    "score": 48,
                    "var_95": 7850.00,
                    "expected_return": 2500.00,
                    "max_loss": 18500.00,
                    "probability_loss": 0.32,
                },
                "recommendations": [
                    {
                        "priority": "HIGH",
                        "message": "ES 期货头寸敞口较大 (Delta=100)，市场波动时注意风险"
                    },
                    {
                        "priority": "MEDIUM",
                        "message": "投资组合整体 Theta 为负，每日时间价值衰减约 $187"
                    },
                    {
                        "priority": "MEDIUM",
                        "message": "EUR.USD 外汇敞口 10,000 欧元，注意汇率波动风险"
                    },
                    {
                        "priority": "LOW",
                        "message": "可考虑卖出看涨期权增加收益"
                    }
                ],
                "positions": [
                    # 股票 (STK)
                    {
                        "symbol": "AAPL",
                        "sec_type": "STK",
                        "sec_type_display": "股票",
                        "position": 100,
                        "market_price": 175.00,
                        "market_value": 17500.00,
                        "unrealized_pnl": 1250.00
                    },
                    {
                        "symbol": "MSFT",
                        "sec_type": "STK",
                        "sec_type_display": "股票",
                        "position": 50,
                        "market_price": 420.00,
                        "market_value": 21000.00,
                        "unrealized_pnl": 800.00
                    },
                    # 期权 (OPT)
                    {
                        "symbol": "AAPL",
                        "sec_type": "OPT",
                        "sec_type_display": "期权",
                        "position": 5,
                        "market_price": 5.00,
                        "market_value": 2500.00,
                        "unrealized_pnl": 350.00,
                        "details": "C 180 2025-02-21"
                    },
                    {
                        "symbol": "SPY",
                        "sec_type": "OPT",
                        "sec_type_display": "期权",
                        "position": -2,
                        "market_price": 6.00,
                        "market_value": -1200.00,
                        "unrealized_pnl": 150.00,
                        "details": "P 460 2025-01-31"
                    },
                    # 期货 (FUT)
                    {
                        "symbol": "ES",
                        "sec_type": "FUT",
                        "sec_type_display": "期货",
                        "position": 2,
                        "market_price": 5025.00,
                        "market_value": 502500.00,  # 名义价值
                        "unrealized_pnl": 2500.00,
                        "details": "Mar 2025, 乘数=50"
                    },
                    # 基金/ETF (FUND)
                    {
                        "symbol": "SPY",
                        "sec_type": "FUND",
                        "sec_type_display": "基金",
                        "position": 100,
                        "market_price": 480.00,
                        "market_value": 48000.00,
                        "unrealized_pnl": 500.00
                    },
                    {
                        "symbol": "QQQ",
                        "sec_type": "FUND",
                        "sec_type_display": "基金",
                        "position": 50,
                        "market_price": 420.00,
                        "market_value": 21000.00,
                        "unrealized_pnl": 350.00
                    },
                    # 外汇 (CASH)
                    {
                        "symbol": "EUR.USD",
                        "sec_type": "CASH",
                        "sec_type_display": "外汇",
                        "position": 10000,  # 10,000 欧元
                        "market_price": 1.0850,
                        "market_value": 10850.00,
                        "unrealized_pnl": 150.00,
                        "details": "EUR/USD"
                    },
                    # 加密货币 (CRYPTO) - 注意: IB 支持有限
                    {
                        "symbol": "BTC",
                        "sec_type": "CRYPTO",
                        "sec_type_display": "加密货币",
                        "position": 0.5,  # 0.5 BTC
                        "market_price": 42000.00,
                        "market_value": 21000.00,
                        "unrealized_pnl": 1500.00,
                        "details": "BTC/USD"
                    }
                ]
            },
            "simulated": True
        }

    def _format_position(self, position) -> Dict:
        """格式化持仓数据"""
        return {
            "symbol": position.symbol,
            "sec_type": position.sec_type,
            "position": position.position,
            "market_value": position.market_value,
            "unrealized_pnl": getattr(position, 'unrealized_pnl', 0),
        }

    def _handle_generate_report(self, params: Dict) -> Dict:
        """生成完整的 HTML 报告，保存到文件并返回路径"""
        try:
            # 获取数据
            portfolio_data = self._handle_get_portfolio(params)

            if not portfolio_data.get('success'):
                return portfolio_data

            # 生成 HTML 报告内容
            data = portfolio_data['data']
            html_content = self._generate_simple_report(data)

            # 保存到文件
            report_dir = PROJECT_ROOT / "output" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = report_dir / f"portfolio_report_{timestamp}.html"

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"报告已保存到: {report_path}")

            return {
                "success": True,
                "report_path": str(report_path),
                "report_url": f"file://{report_path}"
            }

        except Exception as e:
            logger.error(f"生成报告失败: {e}\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_simple_report(self, data: Dict) -> str:
        """生成带图表的 HTML 报告（使用 Chart.js）"""
        import json as json_lib

        account = data.get('account', {})
        greeks = data.get('greeks', {})
        risk = data.get('risk', {})
        recommendations = data.get('recommendations', [])
        positions = data.get('positions', [])

        # 资产类型颜色映射
        sec_type_colors = {
            'STK': '#2E86AB',    # 股票 - 蓝色
            'OPT': '#6610f2',    # 期权 - 紫色
            'FUT': '#fd7e14',    # 期货 - 橙色
            'FUND': '#28A745',   # 基金 - 绿色
            'CASH': '#17a2b8',   # 外汇 - 青色
            'CRYPTO': '#FFC107', # 加密货币 - 黄色
            'BOND': '#6c757d',   # 债券 - 灰色
            'CFD': '#DC3545',    # CFD - 红色
            'FOP': '#e83e8c',    # 期货期权 - 粉色
            'WAR': '#20c997',    # 权证 - 青绿色
        }

        # 生成持仓表格行
        position_rows = ""
        for pos in positions:
            pnl_color = "green" if pos.get('unrealized_pnl', 0) >= 0 else "red"
            sec_type = pos.get('sec_type', '')
            sec_type_display = pos.get('sec_type_display', sec_type)
            sec_type_color = sec_type_colors.get(sec_type, '#6c757d')

            # 格式化数量 (期货/加密货币可能有小数)
            position_val = pos.get('position', 0)
            if abs(position_val) >= 1:
                position_str = f"{position_val:+.0f}"
            else:
                position_str = f"{position_val:+.4f}"

            position_rows += f"""
            <tr>
                <td>{pos.get('symbol', '')}</td>
                <td><span style="background: {sec_type_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{sec_type_display}</span></td>
                <td>{position_str}</td>
                <td>${abs(pos.get('market_value', 0)):,.2f}</td>
                <td style="color: {pnl_color}">${pos.get('unrealized_pnl', 0):+,.2f}</td>
            </tr>
            """

        # 生成建议列表
        rec_items = ""
        priority_colors = {'HIGH': '#DC3545', 'MEDIUM': '#FFC107', 'LOW': '#28A745'}
        for rec in recommendations:
            priority = rec.get('priority', 'LOW')
            color = priority_colors.get(priority, '#6c757d')
            rec_items += f"""
            <div style="background: #f8f9fa; padding: 10px; margin: 5px 0; border-left: 4px solid {color}; border-radius: 4px;">
                <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">{priority}</span>
                <span style="margin-left: 10px;">{rec.get('message', '')}</span>
            </div>
            """

        # 准备图表数据
        # 按资产类型分组的饼图数据
        type_values = {}
        for pos in positions:
            sec_type = pos.get('sec_type_display', pos.get('sec_type', 'Unknown'))
            market_val = abs(pos.get('market_value', 0))
            type_values[sec_type] = type_values.get(sec_type, 0) + market_val

        pie_labels = list(type_values.keys())
        pie_values = list(type_values.values())

        # 希腊值柱状图数据
        greeks_labels = ['Delta ($)', 'Gamma ($)', 'Theta ($/日)', 'Vega ($)']
        greeks_values = [
            greeks.get('delta_dollars', 0),
            greeks.get('gamma_dollars', 0),
            greeks.get('theta_dollars', 0),
            greeks.get('vega_dollars', 0)
        ]
        greeks_colors = ['#2E86AB', '#28A745', '#DC3545', '#FFC107']

        # 按标的分组的 Delta 暴露
        delta_by_symbol = {}
        for pos in positions:
            symbol = pos.get('symbol', 'Unknown')
            # 简化计算：股票 delta=1，期权需要实际 delta
            if pos.get('sec_type') == 'STK':
                delta = pos.get('position', 0)
            else:
                delta = pos.get('position', 0) * 50  # 期权按 50 delta 估算
            delta_by_symbol[symbol] = delta_by_symbol.get(symbol, 0) + delta

        delta_labels = list(delta_by_symbol.keys())
        delta_values = list(delta_by_symbol.values())

        # 生成模拟的蒙特卡洛数据（30天）
        import random
        random.seed(42)
        initial_value = account.get('net_liquidation', 100000)
        num_paths = 50
        num_days = 30

        mc_paths = []
        for _ in range(num_paths):
            path = [initial_value]
            for day in range(num_days):
                daily_return = random.gauss(0.0003, 0.015)  # 日均收益 0.03%，波动率 1.5%
                path.append(path[-1] * (1 + daily_return))
            mc_paths.append(path)

        # 计算百分位数
        percentiles = {}
        for day in range(num_days + 1):
            day_values = [path[day] for path in mc_paths]
            day_values.sort()
            percentiles[day] = {
                'p5': day_values[int(len(day_values) * 0.05)],
                'p25': day_values[int(len(day_values) * 0.25)],
                'p50': day_values[int(len(day_values) * 0.50)],
                'p75': day_values[int(len(day_values) * 0.75)],
                'p95': day_values[int(len(day_values) * 0.95)],
            }

        mc_labels = list(range(num_days + 1))
        mc_p5 = [percentiles[d]['p5'] for d in mc_labels]
        mc_p25 = [percentiles[d]['p25'] for d in mc_labels]
        mc_p50 = [percentiles[d]['p50'] for d in mc_labels]
        mc_p75 = [percentiles[d]['p75'] for d in mc_labels]
        mc_p95 = [percentiles[d]['p95'] for d in mc_labels]

        # 收益分布直方图数据
        final_returns = [(path[-1] / path[0] - 1) * 100 for path in mc_paths]
        return_bins = {}
        bin_size = 2
        for ret in final_returns:
            bin_key = int(ret // bin_size) * bin_size
            return_bins[bin_key] = return_bins.get(bin_key, 0) + 1

        return_labels = sorted(return_bins.keys())
        return_values = [return_bins[k] for k in return_labels]
        return_labels_str = [f"{k}% ~ {k+bin_size}%" for k in return_labels]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>IB Portfolio Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-radius: 8px; }}
        h1 {{ color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px; }}
        h2 {{ color: #343A40; margin-top: 30px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }}
        .summary-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB; }}
        .summary-card.success {{ border-left-color: #28A745; }}
        .summary-card.danger {{ border-left-color: #DC3545; }}
        .summary-card.warning {{ border-left-color: #FFC107; }}
        .summary-card h3 {{ margin: 0 0 5px 0; font-size: 14px; color: #6c757d; }}
        .summary-card .value {{ font-size: 20px; font-weight: bold; color: #343A40; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background-color: #2E86AB; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .risk-badge {{ display: inline-block; padding: 5px 15px; border-radius: 4px; color: white; font-weight: bold; }}
        .risk-LOW {{ background-color: #28A745; }}
        .risk-MEDIUM {{ background-color: #FFC107; color: #343A40; }}
        .risk-HIGH {{ background-color: #DC3545; }}
        .risk-CRITICAL {{ background-color: #721c24; }}
        .timestamp {{ color: #6c757d; font-size: 12px; }}
        .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
        .chart-container {{ background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; }}
        .chart-full {{ grid-column: 1 / -1; }}
        canvas {{ max-height: 300px; }}
        .chart-title {{ font-size: 14px; font-weight: bold; color: #343A40; margin-bottom: 10px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 投资组合分析报告</h1>
        <p class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>账户概览</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <h3>净资产</h3>
                <div class="value">${account.get('net_liquidation', 0):,.2f}</div>
            </div>
            <div class="summary-card {'success' if account.get('unrealized_pnl', 0) >= 0 else 'danger'}">
                <h3>未实现盈亏</h3>
                <div class="value">${account.get('unrealized_pnl', 0):+,.2f}</div>
            </div>
            <div class="summary-card">
                <h3>风险等级</h3>
                <div class="value"><span class="risk-badge risk-{risk.get('level', 'LOW')}">{risk.get('level', 'N/A')}</span></div>
            </div>
            <div class="summary-card danger">
                <h3>95% VaR</h3>
                <div class="value">${risk.get('var_95', 0):,.2f}</div>
            </div>
        </div>

        <h2>可视化分析</h2>
        <div class="chart-row">
            <div class="chart-container">
                <div class="chart-title">持仓分配</div>
                <canvas id="pieChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">希腊值汇总</div>
                <canvas id="greeksChart"></canvas>
            </div>
        </div>

        <div class="chart-row">
            <div class="chart-container">
                <div class="chart-title">Delta 暴露 (按标的)</div>
                <canvas id="deltaChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">收益分布 (30天模拟)</div>
                <canvas id="returnChart"></canvas>
            </div>
        </div>

        <div class="chart-row">
            <div class="chart-container chart-full">
                <div class="chart-title">蒙特卡洛模拟 - 投资组合价值路径 (30天, 50条路径)</div>
                <canvas id="mcChart"></canvas>
            </div>
        </div>

        <h2>希腊值汇总</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <h3>Delta ($)</h3>
                <div class="value">${greeks.get('delta_dollars', 0):,.2f}</div>
            </div>
            <div class="summary-card">
                <h3>Gamma ($)</h3>
                <div class="value">${greeks.get('gamma_dollars', 0):,.2f}</div>
            </div>
            <div class="summary-card {'danger' if greeks.get('theta_dollars', 0) < -50 else ''}">
                <h3>Theta ($/日)</h3>
                <div class="value">${greeks.get('theta_dollars', 0):,.2f}</div>
            </div>
            <div class="summary-card">
                <h3>Vega ($)</h3>
                <div class="value">${greeks.get('vega_dollars', 0):,.2f}</div>
            </div>
        </div>

        <h2>投资建议</h2>
        {rec_items if rec_items else '<p style="color: #666;">暂无建议</p>'}

        <h2>持仓明细</h2>
        <table>
            <tr>
                <th>标的</th>
                <th>类型</th>
                <th>数量</th>
                <th>市值</th>
                <th>盈亏</th>
            </tr>
            {position_rows}
        </table>

        <p class="timestamp" style="margin-top: 30px; text-align: center;">
            IB Portfolio Analyzer v1.0.0 | 数据仅供参考，不构成投资建议
        </p>
    </div>

    <script>
        // 持仓分配饼图
        new Chart(document.getElementById('pieChart'), {{
            type: 'doughnut',
            data: {{
                labels: {json_lib.dumps(pie_labels)},
                datasets: [{{
                    data: {json_lib.dumps(pie_values)},
                    backgroundColor: ['#2E86AB', '#28A745', '#FFC107', '#DC3545', '#6c757d', '#17a2b8', '#6610f2', '#fd7e14']
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ position: 'right' }}
                }}
            }}
        }});

        // 希腊值柱状图
        new Chart(document.getElementById('greeksChart'), {{
            type: 'bar',
            data: {{
                labels: {json_lib.dumps(greeks_labels)},
                datasets: [{{
                    data: {json_lib.dumps(greeks_values)},
                    backgroundColor: {json_lib.dumps(greeks_colors)}
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Delta 暴露柱状图
        new Chart(document.getElementById('deltaChart'), {{
            type: 'bar',
            data: {{
                labels: {json_lib.dumps(delta_labels)},
                datasets: [{{
                    label: 'Delta',
                    data: {json_lib.dumps(delta_values)},
                    backgroundColor: {json_lib.dumps(delta_values)}.map(v => v >= 0 ? '#28A745' : '#DC3545')
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});

        // 收益分布直方图
        new Chart(document.getElementById('returnChart'), {{
            type: 'bar',
            data: {{
                labels: {json_lib.dumps(return_labels_str)},
                datasets: [{{
                    label: '频次',
                    data: {json_lib.dumps(return_values)},
                    backgroundColor: '#2E86AB'
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: '频次' }} }},
                    x: {{ title: {{ display: true, text: '收益率' }} }}
                }}
            }}
        }});

        // 蒙特卡洛模拟图
        new Chart(document.getElementById('mcChart'), {{
            type: 'line',
            data: {{
                labels: {json_lib.dumps(mc_labels)},
                datasets: [
                    {{
                        label: '95th 百分位',
                        data: {json_lib.dumps(mc_p95)},
                        borderColor: 'rgba(46, 134, 171, 0.3)',
                        backgroundColor: 'rgba(46, 134, 171, 0.1)',
                        fill: '+1',
                        pointRadius: 0
                    }},
                    {{
                        label: '75th 百分位',
                        data: {json_lib.dumps(mc_p75)},
                        borderColor: 'rgba(46, 134, 171, 0.5)',
                        backgroundColor: 'rgba(46, 134, 171, 0.2)',
                        fill: '+1',
                        pointRadius: 0
                    }},
                    {{
                        label: '中位数',
                        data: {json_lib.dumps(mc_p50)},
                        borderColor: '#2E86AB',
                        borderWidth: 2,
                        fill: false,
                        pointRadius: 0
                    }},
                    {{
                        label: '25th 百分位',
                        data: {json_lib.dumps(mc_p25)},
                        borderColor: 'rgba(46, 134, 171, 0.5)',
                        backgroundColor: 'transparent',
                        fill: false,
                        pointRadius: 0
                    }},
                    {{
                        label: '5th 百分位',
                        data: {json_lib.dumps(mc_p5)},
                        borderColor: 'rgba(220, 53, 69, 0.5)',
                        backgroundColor: 'transparent',
                        fill: false,
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                interaction: {{ intersect: false, mode: 'index' }},
                plugins: {{
                    legend: {{ position: 'top' }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return context.dataset.label + ': $' + context.parsed.y.toLocaleString(undefined, {{maximumFractionDigits: 0}});
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ title: {{ display: true, text: '天数' }} }},
                    y: {{
                        title: {{ display: true, text: '投资组合价值 ($)' }},
                        ticks: {{
                            callback: function(value) {{ return '$' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
        """
        return html

    def _handle_get_positions(self, params: Dict) -> Dict:
        """仅获取持仓列表"""
        portfolio = self._handle_get_portfolio({})
        if portfolio.get('success'):
            return {
                "success": True,
                "positions": portfolio['data']['positions']
            }
        return portfolio

    def _handle_get_greeks(self, params: Dict) -> Dict:
        """仅获取希腊值"""
        portfolio = self._handle_get_portfolio({})
        if portfolio.get('success'):
            return {
                "success": True,
                "greeks": portfolio['data']['greeks']
            }
        return portfolio

    def _handle_get_risk(self, params: Dict) -> Dict:
        """仅获取风险评估"""
        portfolio = self._handle_get_portfolio({})
        if portfolio.get('success'):
            return {
                "success": True,
                "risk": portfolio['data']['risk']
            }
        return portfolio

    def _handle_test_connection(self, params: Dict) -> Dict:
        """测试 IB TWS/Gateway 连接"""
        host = params.get('host', '127.0.0.1')
        port = params.get('port', 7497)
        client_id = params.get('clientId', 1)

        logger.info(f"测试连接: {host}:{port}, clientId={client_id}")

        try:
            import socket

            # 首先测试端口是否可达
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result != 0:
                logger.warning(f"端口 {port} 不可达")
                return {
                    "success": False,
                    "error": f"无法连接到 {host}:{port}，请确保 TWS/IB Gateway 正在运行且 API 已启用"
                }

            # 尝试使用 IB API 连接
            try:
                from src.ib_client.client import IBClient

                ib_client = IBClient(host=host, port=port, client_id=client_id)
                if ib_client.connect():
                    ib_client.disconnect()
                    logger.info("IB API 连接测试成功")
                    return {
                        "success": True,
                        "message": "连接成功",
                        "details": {
                            "host": host,
                            "port": port,
                            "clientId": client_id
                        }
                    }
                else:
                    logger.warning("IB API 连接失败")
                    return {
                        "success": False,
                        "error": "IB API 连接失败，请检查 TWS/Gateway 的 API 设置"
                    }

            except ImportError:
                # IB 模块未安装，但端口可达
                logger.info("IB 模块未安装，但端口可达")
                return {
                    "success": True,
                    "message": "端口可达（IB 模块未安装，无法验证 API 连接）",
                    "details": {
                        "host": host,
                        "port": port,
                        "clientId": client_id
                    }
                }

        except Exception as e:
            logger.error(f"连接测试失败: {e}\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e)
            }

    def _handle_get_settings(self, params: Dict) -> Dict:
        """获取当前设置（供扩展查询）"""
        # 返回默认设置信息和系统状态
        return {
            "success": True,
            "settings": {
                "defaultHost": "127.0.0.1",
                "defaultPort": 7497,
                "defaultClientId": 1,
                "portPresets": {
                    "tws_paper": 7497,
                    "tws_live": 7496,
                    "gateway_paper": 4001,
                    "gateway_live": 4002
                }
            },
            "system": {
                "version": "1.0.0",
                "pythonVersion": sys.version,
                "projectRoot": str(PROJECT_ROOT)
            }
        }


def main():
    """入口点"""
    host = NativeMessagingHost()
    host.run()


if __name__ == '__main__':
    main()
