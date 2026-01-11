# IB Portfolio Analysis System

盈透账户仓位分析系统 - 专业级期权投资组合风险分析工具

## 功能特性

### 1. 盈透API读取
- 连接IB TWS/Gateway获取实时账户数据
- 支持股票、期权、期货等多种资产类型
- 自动重连机制和模拟数据模式

### 2. 希腊值计算
- 基于Black-Scholes模型的精确计算
- 支持Delta、Gamma、Theta、Vega、Rho
- 按标的汇总和投资组合级别统计
- 美元化风险敞口计算

### 3. 蒙特卡洛模拟
- 几何布朗运动(GBM)价格路径模拟
- 支持多资产相关性
- VaR和CVaR风险度量
- 压力测试场景分析

### 4. 可视化输出
- 仓位分配饼图
- 希腊值汇总柱状图
- Delta暴露分析
- 价格路径扇形图
- 收益分布直方图
- VaR分析图表
- 情景热力图
- 交互式HTML报告

### 5. 投资建议
- 风险等级评估 (LOW/MEDIUM/HIGH/CRITICAL)
- Delta对冲建议
- 时间价值管理
- 集中度风险警告
- 到期期权滚动提醒
- 止盈止损建议

## 快速开始

### 安装依赖

```bash
# 克隆项目
cd ib-analysis

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行分析

#### 模拟模式 (无需IB连接)

```bash
python -m src.main
```

#### 连接真实IB账户

```bash
# 确保TWS或IB Gateway正在运行并允许API连接
python -m src.main --live
```

### 命令行参数

```bash
python -m src.main [选项]

选项:
  --live, -l          连接真实IB账户 (默认: 模拟模式)
  --paths, -p INT     蒙特卡洛模拟路径数 (默认: 10000)
  --days, -d INT      模拟天数 (默认: 30)
  --output, -o DIR    输出目录 (默认: output)
  --config, -c FILE   配置文件路径 (默认: config/config.yaml)
  --verbose, -v       详细日志输出
```

### 示例

```bash
# 完整30天模拟，10000路径
python -m src.main --paths 10000 --days 30

# 快速7天模拟
python -m src.main --paths 5000 --days 7

# 连接IB并分析
python -m src.main --live --output results
```

## 项目结构

```
ib-analysis/
├── src/
│   ├── ib_client/            # IB API客户端
│   │   ├── client.py         # 主客户端类
│   │   ├── contracts.py      # 合约构建
│   │   └── models.py         # 数据模型
│   ├── greeks/               # 希腊值计算
│   │   ├── black_scholes.py  # BS模型实现
│   │   ├── calculator.py     # 计算器
│   │   └── models.py         # 数据模型
│   ├── monte_carlo/          # 蒙特卡洛模拟
│   │   ├── simulator.py      # 模拟器
│   │   └── models.py         # 数据模型
│   ├── visualizer/           # 可视化
│   │   ├── charts.py         # 图表生成
│   │   └── styles.py         # 样式配置
│   ├── advisor/              # 投资建议
│   │   ├── analyzer.py       # 分析器
│   │   └── models.py         # 数据模型
│   └── main.py               # 主程序入口
├── tests/                    # 测试用例
├── config/
│   └── config.yaml           # 配置文件
├── output/                   # 输出目录
│   ├── charts/               # 图表
│   └── reports/              # HTML报告
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 配置说明

编辑 `config/config.yaml` 自定义设置:

```yaml
# IB连接设置
ib:
  host: "127.0.0.1"
  port: 7497        # TWS Paper: 7497, TWS Live: 7496
  client_id: 1
  timeout: 30

# 希腊值计算
greeks:
  risk_free_rate: 0.05
  default_volatility: 0.25

# 蒙特卡洛模拟
monte_carlo:
  num_paths: 10000
  num_days: 30

# 风险阈值
risk:
  delta_neutral_threshold: 0.1
  concentration_warning: 0.3
  theta_decay_warning: -100
```

## API使用

### 程序化使用

```python
from src.ib_client import IBClient
from src.greeks import GreeksCalculator
from src.monte_carlo import MonteCarloSimulator
from src.visualizer import Visualizer
from src.advisor import PortfolioAdvisor

# 1. 获取仓位
client = IBClient(simulation_mode=True)
client.connect()
positions = client.get_positions()

# 2. 计算希腊值
calc = GreeksCalculator()
greeks = calc.calculate_portfolio_greeks(positions)

# 3. 运行模拟
sim = MonteCarloSimulator(num_paths=10000, num_days=30)
result = sim.simulate_portfolio(positions)

# 4. 生成图表
viz = Visualizer(output_dir="output/charts")
viz.plot_return_distribution(result)

# 5. 获取建议
advisor = PortfolioAdvisor()
advice = advisor.generate_report(positions, greeks, result)
print(advice.summary)
```

## 输出示例

### 分析报告摘要

```
================================================================
  IB Portfolio Analysis System / 盈透账户仓位分析系统
================================================================
  Portfolio Value: $150,000.00
  Expected Return (30D): +3.25%
  95% VaR: $12,500.00
  Risk Level: MEDIUM
  Recommendations: 4
================================================================

  HIGH PRIORITY ACTIONS:
    1. Roll Expiring Options
       Roll 2 positions expiring within 7 days

    2. Reduce Time Decay
       Consider closing long options to save $150/day
================================================================
```

### 希腊值汇总

```
Portfolio Greeks Summary:
  Total Delta: 245.32 shares equivalent
  Delta Dollars: $36,798.00
  Total Gamma: 0.0523
  Gamma Dollars: $523.00 per 1% move
  Total Theta: -$125.00/day
  Total Vega: $890.00 per 1% IV
```

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_greeks.py

# 带覆盖率报告
pytest --cov=src --cov-report=html
```

## 风险提示

⚠️ **重要声明**

本工具仅供教育和研究目的。投资有风险，入市需谨慎。

- 模拟结果基于历史数据和统计模型，不代表未来表现
- Black-Scholes模型假设可能与实际市场条件不符
- 建议仅供参考，不构成投资建议
- 请在做出任何投资决策前咨询专业金融顾问

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 更新日志

### v0.1.0 (2026-01-11)
- 初始版本发布
- 实现IB API连接和仓位读取
- 实现Black-Scholes希腊值计算
- 实现蒙特卡洛模拟
- 实现可视化图表
- 实现投资建议生成
