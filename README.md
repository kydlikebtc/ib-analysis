# IB Portfolio Analyzer

**Interactive Brokers 投资组合分析器** - 一款专为期权交易者设计的 Chrome 浏览器扩展

<p align="center">
  <img src="extension/icons/icon128.png" alt="IB Portfolio Analyzer" width="128">
</p>

## 核心产品：Chrome 浏览器扩展

一键获取你的 IB 账户数据，实时查看希腊值、风险评估和投资建议。

### 主要功能

| 功能 | 描述 |
|------|------|
| **账户概览** | 净资产、未实现盈亏、持仓数量 |
| **希腊值分析** | Delta/Gamma/Theta/Vega 实时计算与美元化敞口 |
| **风险评估** | 95% VaR、风险等级评定 (LOW/MEDIUM/HIGH/CRITICAL) |
| **智能建议** | Delta 对冲、时间价值管理、集中度警告 |
| **完整报告** | 交互式 HTML 报告，含 5 种可视化图表 |

### 报告图表

- **持仓分配饼图** - 各标的市值占比
- **希腊值汇总柱状图** - Delta/Gamma/Theta/Vega 可视化
- **Delta 暴露柱状图** - 按标的显示 Delta 敞口
- **收益分布直方图** - 30 天蒙特卡洛模拟收益分布
- **蒙特卡洛模拟图** - 50 条路径的投资组合价值演变

---

## 快速开始

### 1. 安装依赖

```bash
cd ib-analysis

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 安装 Chrome 扩展

1. 打开 Chrome，访问 `chrome://extensions/`
2. 开启右上角「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择 `extension` 目录

### 3. 注册 Native Host

```bash
cd extension
chmod +x install.sh
./install.sh
```

### 4. 配置 IB 连接

1. 确保 TWS 或 IB Gateway 正在运行
2. 启用 API 连接（TWS: 编辑 → 全局配置 → API → 设置）
3. 点击扩展图标，进入「设置」页面配置连接参数

| 模式 | 端口 |
|------|------|
| TWS Paper Trading | 7497 |
| TWS Live Trading | 7496 |
| IB Gateway Paper | 4001 |
| IB Gateway Live | 4002 |

### 5. 开始使用

点击浏览器工具栏中的扩展图标，即可查看你的投资组合数据！

---

## 系统要求

- **操作系统**: macOS / Linux / Windows
- **浏览器**: Chrome 88+ / Edge 88+ (Chromium 内核)
- **Python**: 3.9+
- **IB 软件**: TWS 或 IB Gateway

---

## 项目结构

```
ib-analysis/
├── extension/                    # Chrome 扩展 (核心产品)
│   ├── manifest.json             # 扩展清单
│   ├── popup.html                # 主界面
│   ├── settings.html             # 设置页面
│   ├── src/
│   │   ├── popup.js              # 主界面逻辑
│   │   ├── popup.css             # 主界面样式
│   │   ├── settings.js           # 设置页面逻辑
│   │   ├── settings.css          # 设置页面样式
│   │   └── background.js         # Service Worker
│   ├── native-host/
│   │   └── ib_native_host.py     # Native Messaging 主机
│   ├── icons/                    # 扩展图标
│   ├── install.sh                # 安装脚本
│   └── uninstall.sh              # 卸载脚本
│
├── src/                          # Python 底层库
│   ├── ib_client/                # IB API 客户端
│   ├── greeks/                   # 希腊值计算 (Black-Scholes)
│   ├── monte_carlo/              # 蒙特卡洛模拟
│   ├── visualizer/               # 可视化图表
│   ├── advisor/                  # 投资建议引擎
│   └── main.py                   # CLI 入口
│
├── config/
│   └── config.yaml               # 配置文件
├── output/                       # 输出目录
│   ├── charts/                   # 图表文件
│   └── reports/                  # HTML 报告
├── tests/                        # 测试用例
└── requirements.txt              # Python 依赖
```

---

## Python 底层库

Chrome 扩展基于以下 Python 模块构建，也可独立使用：

### 模块说明

| 模块 | 功能 |
|------|------|
| `src.ib_client` | IB API 客户端，支持连接 TWS/Gateway |
| `src.greeks` | Black-Scholes 模型希腊值计算 |
| `src.monte_carlo` | 几何布朗运动蒙特卡洛模拟 |
| `src.visualizer` | Plotly/Matplotlib 可视化图表 |
| `src.advisor` | 风险评估与投资建议生成 |

### CLI 使用

```bash
# 模拟模式（无需 IB 连接）
python -m src.main

# 连接真实 IB 账户
python -m src.main --live

# 自定义参数
python -m src.main --paths 10000 --days 30 --output results
```

### API 使用

```python
from src.ib_client import IBClient
from src.greeks import GreeksCalculator
from src.monte_carlo import MonteCarloSimulator

# 获取仓位
client = IBClient(simulation_mode=True)
client.connect()
positions = client.get_positions()

# 计算希腊值
calc = GreeksCalculator()
greeks = calc.calculate_portfolio_greeks(positions)

# 运行蒙特卡洛模拟
sim = MonteCarloSimulator(num_paths=10000, num_days=30)
result = sim.simulate_portfolio(positions)
```

---

## 配置文件

编辑 `config/config.yaml`：

```yaml
# IB 连接
ib:
  host: "127.0.0.1"
  port: 7497
  client_id: 1

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

---

## 测试

```bash
# 运行所有测试
pytest

# 带覆盖率报告
pytest --cov=src --cov-report=html
```

---

## 风险提示

> **重要声明**
>
> 本工具仅供教育和研究目的，不构成投资建议。
>
> - 模拟结果基于统计模型，不代表未来表现
> - Black-Scholes 假设可能与实际市场不符
> - 请在投资决策前咨询专业金融顾问

---

## 更新日志

### v1.0.0 (2026-01-11)

**Chrome 扩展功能完善**
- 重构报告生成，添加 5 种交互式 Chart.js 图表
- 修复 Blob URL 无法加载外部资源的问题
- 报告直接在新标签页中打开

**设置页面**
- 支持配置 IB 连接参数
- 快速端口预设 (TWS/Gateway Paper/Live)
- 连接测试功能

**Native Host**
- 移除外部依赖，使用内置报告生成
- 改进错误处理和日志

### v0.1.0 (2026-01-11)

- 初始版本
- IB API 连接和仓位读取
- Black-Scholes 希腊值计算
- 蒙特卡洛模拟
- 可视化图表
- 投资建议生成

---

## 许可证

MIT License

---

## 贡献

欢迎提交 Issue 和 Pull Request！
