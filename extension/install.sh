#!/bin/bash
# IB Portfolio Analyzer Chrome Extension - 安装脚本
# 用于注册 Native Messaging Host

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_NAME="com.ib.portfolio_analyzer"
HOST_PATH="$SCRIPT_DIR/native-host/ib_native_host.py"
MANIFEST_PATH="$SCRIPT_DIR/native-host/$HOST_NAME.json"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     IB Portfolio Analyzer - Native Host 安装程序           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 检查操作系统
OS="$(uname -s)"
case "$OS" in
    Darwin)
        # macOS
        CHROME_MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        CHROMIUM_MANIFEST_DIR="$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
        ;;
    Linux)
        # Linux
        CHROME_MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
        CHROMIUM_MANIFEST_DIR="$HOME/.config/chromium/NativeMessagingHosts"
        ;;
    *)
        echo "❌ 不支持的操作系统: $OS"
        echo "   请手动配置 Native Messaging Host"
        exit 1
        ;;
esac

# 确保 Python 脚本可执行
chmod +x "$HOST_PATH"

# 获取 Chrome 扩展 ID
echo "📋 请输入 Chrome 扩展 ID（在 chrome://extensions 中查看）:"
echo "   如果还没有安装扩展，请先加载扩展后再运行此脚本"
read -r EXTENSION_ID

if [ -z "$EXTENSION_ID" ]; then
    echo "❌ 扩展 ID 不能为空"
    exit 1
fi

# 更新 manifest 文件中的扩展 ID
TEMP_MANIFEST=$(mktemp)
cat > "$TEMP_MANIFEST" << EOF
{
  "name": "$HOST_NAME",
  "description": "IB Portfolio Analyzer Native Host - 连接 Interactive Brokers API 获取投资组合数据",
  "path": "$HOST_PATH",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXTENSION_ID/"
  ]
}
EOF

# 安装到 Chrome
install_manifest() {
    local target_dir="$1"
    local browser_name="$2"

    if [ -d "$(dirname "$target_dir")" ] || [ "$browser_name" = "Chrome" ]; then
        mkdir -p "$target_dir"
        cp "$TEMP_MANIFEST" "$target_dir/$HOST_NAME.json"
        echo "✅ 已安装到 $browser_name: $target_dir/$HOST_NAME.json"
        return 0
    else
        echo "⏭️  跳过 $browser_name（未检测到安装）"
        return 1
    fi
}

echo ""
echo "🔧 正在安装 Native Messaging Host..."
echo ""

# 安装到各个浏览器
install_manifest "$CHROME_MANIFEST_DIR" "Chrome"
install_manifest "$CHROMIUM_MANIFEST_DIR" "Chromium" 2>/dev/null || true

# 清理临时文件
rm -f "$TEMP_MANIFEST"

# 验证安装
echo ""
echo "🔍 验证安装..."
if [ -f "$CHROME_MANIFEST_DIR/$HOST_NAME.json" ]; then
    echo "✅ Chrome Native Host 配置:"
    cat "$CHROME_MANIFEST_DIR/$HOST_NAME.json"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                     安装完成！                              ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  下一步:                                                    ║"
echo "║  1. 重启 Chrome 浏览器                                      ║"
echo "║  2. 打开 IB Portfolio Analyzer 扩展                         ║"
echo "║  3. 确保 TWS 或 IB Gateway 正在运行                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
