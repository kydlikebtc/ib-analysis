#!/usr/bin/env python3
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
        """返回模拟的投资组合数据（用于测试）"""
        return {
            "success": True,
            "data": {
                "account": {
                    "net_liquidation": 125000.00,
                    "unrealized_pnl": 3250.50,
                    "daily_pnl": 850.25,
                },
                "greeks": {
                    "delta": 0.65,
                    "delta_dollars": 8125.00,
                    "gamma": 0.02,
                    "gamma_dollars": 250.00,
                    "theta": -0.15,
                    "theta_dollars": -187.50,
                    "vega": 0.35,
                    "vega_dollars": 437.50,
                },
                "risk": {
                    "level": "MEDIUM",
                    "score": 45,
                    "var_95": 5250.00,
                    "max_loss": 12500.00,
                    "probability_loss": 0.35,
                },
                "recommendations": [
                    {
                        "priority": "HIGH",
                        "message": "AAPL 期权头寸 Delta 过高，建议对冲"
                    },
                    {
                        "priority": "MEDIUM",
                        "message": "投资组合整体 Theta 为负，每日时间价值衰减约 $187"
                    },
                    {
                        "priority": "LOW",
                        "message": "可考虑卖出看涨期权增加收益"
                    }
                ],
                "positions": [
                    {
                        "symbol": "AAPL",
                        "sec_type": "STK",
                        "position": 100,
                        "market_value": 17500.00,
                        "unrealized_pnl": 1250.00
                    },
                    {
                        "symbol": "AAPL",
                        "sec_type": "OPT",
                        "position": 5,
                        "market_value": 2500.00,
                        "unrealized_pnl": 350.00,
                        "details": "C 180 2025-02-21"
                    },
                    {
                        "symbol": "MSFT",
                        "sec_type": "STK",
                        "position": 50,
                        "market_value": 21000.00,
                        "unrealized_pnl": 800.00
                    },
                    {
                        "symbol": "SPY",
                        "sec_type": "STK",
                        "position": 100,
                        "market_value": 48000.00,
                        "unrealized_pnl": 500.00
                    },
                    {
                        "symbol": "SPY",
                        "sec_type": "OPT",
                        "position": -2,
                        "market_value": -1200.00,
                        "unrealized_pnl": 150.00,
                        "details": "P 460 2025-01-31"
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
        """生成完整的 HTML 报告"""
        try:
            from src.visualizer.charts import PortfolioVisualizer
            from datetime import datetime

            # 获取数据
            portfolio_data = self._handle_get_portfolio(params)

            if not portfolio_data.get('success'):
                return portfolio_data

            # 生成报告
            visualizer = PortfolioVisualizer()
            report_path = visualizer.generate_report(
                portfolio_data['data'],
                output_path=str(PROJECT_ROOT / "output" / "reports" /
                               f"popup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            )

            return {
                "success": True,
                "report_path": str(report_path)
            }

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

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


def main():
    """入口点"""
    host = NativeMessagingHost()
    host.run()


if __name__ == '__main__':
    main()
