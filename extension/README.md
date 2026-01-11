# IB Portfolio Analyzer Chrome 扩展

一个 Chrome 浏览器扩展，通过 Native Messaging 与本地 IB API 通信，实时获取和显示 Interactive Brokers 账户数据。

## 功能特点

- 📊 **账户概览**: 显示账户净值、未实现盈亏、日盈亏
- 📈 **希腊值分析**: Delta、Gamma、Theta、Vega 汇总及美元值
- ⚠️ **风险评估**: 风险等级、VaR (95%)、最大损失概率
- 💡 **投资建议**: 基于当前持仓的智能建议
- 📋 **持仓列表**: 快速查看所有持仓和盈亏
- ⚙️ **可配置连接**: 支持在扩展内配置 TWS/Gateway 连接参数

## 系统架构

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Chrome 扩展    │ ◄─────► │  Native Host    │ ◄─────► │  TWS/IB Gateway │
│  (popup.js)     │  stdio  │  (Python)       │   API   │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

## 完整安装指南

### 前置要求

1. **Python 3.7+** 已安装
2. **Google Chrome** 浏览器
3. **Interactive Brokers TWS** 或 **IB Gateway**
4. 项目依赖已安装：
   ```bash
   cd /path/to/ib-analysis
   pip install -r requirements.txt
   ```

### 步骤 1: 配置 TWS/IB Gateway

在开始之前，需要确保 TWS 或 IB Gateway 正确配置了 API 访问：

#### TWS (Trader Workstation) 配置

1. 启动 TWS 并登录
2. 进入菜单：**Edit → Global Configuration** (Windows) 或 **File → Global Configuration** (Mac)
3. 在左侧导航栏选择：**API → Settings**
4. 勾选以下选项：
   - ✅ **Enable ActiveX and Socket Clients** (启用 API)
   - ✅ **Allow connections from localhost only** (仅允许本地连接，更安全)
   - ❌ **Read-Only API** (取消勾选，如果需要交易功能)
5. 设置 **Socket port**：
   - 模拟账户：`7497`
   - 真实账户：`7496`
6. 点击 **OK** 保存设置

#### IB Gateway 配置

1. 启动 IB Gateway 并登录
2. 进入 **Configure → Settings**
3. 在 **API → Settings** 中：
   - ✅ **Enable ActiveX and Socket Clients**
   - 设置端口：`4001` (模拟) 或 `4002` (真实)
4. 保存设置

### 步骤 2: 安装 Chrome 扩展

1. 打开 Chrome 浏览器
2. 访问 `chrome://extensions/`
3. 开启右上角的 **"开发者模式"** 开关
4. 点击 **"加载已解压的扩展程序"**
5. 选择 `ib-analysis/extension` 目录
6. 扩展安装成功后，**记录显示的扩展 ID**（类似：`bpgjoagblakaodpafioondfbhecaenal`）

### 步骤 3: 注册 Native Messaging Host

#### macOS / Linux

```bash
cd /path/to/ib-analysis/extension
./install.sh
```

脚本会提示输入扩展 ID，粘贴上一步记录的 ID 后按回车。

#### 手动安装（如果脚本失败）

1. 编辑 Native Host 清单文件：
   ```bash
   # 替换 YOUR_EXTENSION_ID 为实际的扩展 ID
   cat > ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.ib.portfolio_analyzer.json << EOF
   {
     "name": "com.ib.portfolio_analyzer",
     "description": "IB Portfolio Analyzer Native Host",
     "path": "/path/to/ib-analysis/extension/native-host/ib_native_host.py",
     "type": "stdio",
     "allowed_origins": [
       "chrome-extension://YOUR_EXTENSION_ID/"
     ]
   }
   EOF
   ```

2. 确保 Python 脚本可执行：
   ```bash
   chmod +x /path/to/ib-analysis/extension/native-host/ib_native_host.py
   ```

### 步骤 4: 重启 Chrome 并测试

1. **完全关闭** Chrome 浏览器（确保所有进程都已退出）
2. 重新打开 Chrome
3. 确保 TWS/IB Gateway 正在运行
4. 点击工具栏中的扩展图标
5. 如果一切正常，将显示账户数据；如果 IB 未连接，将显示模拟数据

## 扩展设置

点击扩展弹窗中的 ⚙️ **设置** 按钮，可以配置以下选项：

### 连接设置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 主机地址 | `127.0.0.1` | TWS/Gateway 运行的 IP 地址 |
| 端口 | `7497` | API 端口（见下表） |
| 客户端 ID | `1` | 用于区分不同的 API 客户端 |

### 常用端口配置

| 软件 | 账户类型 | 默认端口 |
|------|----------|----------|
| TWS | 模拟 (Paper) | 7497 |
| TWS | 真实 (Live) | 7496 |
| IB Gateway | 模拟 (Paper) | 4001 |
| IB Gateway | 真实 (Live) | 4002 |

### 其他设置

- **自动刷新**: 开启后每隔指定秒数自动获取最新数据
- **刷新间隔**: 自动刷新的时间间隔（秒）
- **显示通知**: 当有重要风险提醒时显示浏览器通知

## 文件结构

```
extension/
├── manifest.json           # 扩展清单 (Manifest V3)
├── popup.html              # 弹窗主页面
├── settings.html           # 设置页面
├── src/
│   ├── popup.js            # 弹窗交互逻辑
│   ├── popup.css           # 弹窗样式
│   ├── settings.js         # 设置页面逻辑
│   ├── settings.css        # 设置页面样式
│   └── background.js       # Service Worker (Native Messaging)
├── icons/
│   ├── icon16.png          # 16x16 图标
│   ├── icon32.png          # 32x32 图标
│   ├── icon48.png          # 48x48 图标
│   └── icon128.png         # 128x128 图标
├── native-host/
│   ├── ib_native_host.py   # Native Host Python 脚本
│   ├── com.ib.portfolio_analyzer.json  # Host 清单模板
│   └── logs/               # 运行日志目录
├── install.sh              # macOS/Linux 安装脚本
├── uninstall.sh            # 卸载脚本
└── README.md               # 本文档
```

## 故障排除

### 问题：扩展显示 "连接断开" 或 "Native host 连接断开"

**可能原因及解决方案：**

1. **Native Host 未正确注册**
   ```bash
   # 检查配置文件是否存在
   cat ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.ib.portfolio_analyzer.json

   # 重新运行安装脚本
   ./extension/install.sh
   ```

2. **Python 脚本无法执行**
   ```bash
   # 确保脚本有执行权限
   chmod +x extension/native-host/ib_native_host.py

   # 测试脚本是否能运行
   python3 extension/native-host/ib_native_host.py <<< '{"action":"ping"}'
   ```

3. **Chrome 需要重启**
   - 完全关闭所有 Chrome 窗口和进程
   - 重新打开 Chrome

### 问题：连接 IB 失败

**检查清单：**

1. TWS/IB Gateway 是否正在运行？
2. API 是否已启用？（见上方配置说明）
3. 端口是否正确？（扩展设置中配置）
4. 是否有防火墙阻止连接？

**查看 Native Host 日志：**
```bash
tail -f extension/native-host/logs/native_host.log
```

### 问题：显示模拟数据而非真实数据

这是正常行为。当无法连接到 TWS/IB Gateway 时，扩展会自动显示模拟数据供预览。确保 IB 软件正在运行并正确配置后刷新即可。

## 开发调试

### 查看扩展日志

1. 访问 `chrome://extensions/`
2. 找到 IB Portfolio Analyzer
3. 点击 **"Service Worker"** 或 **"背景页面"**
4. 打开开发者工具查看 Console 日志

### 测试 Native Host

```bash
# 发送 ping 命令测试连接
echo '{"action":"ping"}' | python3 extension/native-host/ib_native_host.py

# 获取投资组合数据
echo '{"action":"get_portfolio"}' | python3 extension/native-host/ib_native_host.py
```

### 修改后重新加载

1. 修改代码后，访问 `chrome://extensions/`
2. 点击扩展卡片上的 🔄 **刷新** 按钮
3. 重新打开扩展弹窗测试

## 卸载

### 移除扩展

1. 访问 `chrome://extensions/`
2. 找到 IB Portfolio Analyzer
3. 点击 **"移除"**

### 移除 Native Host

```bash
./extension/uninstall.sh
```

或手动删除：
```bash
rm ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.ib.portfolio_analyzer.json
```

## 安全说明

- 扩展仅与本地 Native Host 通信，不会发送数据到外部服务器
- 所有 IB API 通信都在本地进行
- 建议在 TWS 中启用 "Allow connections from localhost only"
- 不要在公共电脑上使用此扩展

## 许可证

MIT License
