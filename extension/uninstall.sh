#!/bin/bash
# IB Portfolio Analyzer Chrome Extension - 卸载脚本
# 用于移除 Native Messaging Host 注册

set -e

HOST_NAME="com.ib.portfolio_analyzer"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     IB Portfolio Analyzer - Native Host 卸载程序           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 检查操作系统
OS="$(uname -s)"
case "$OS" in
    Darwin)
        CHROME_MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        CHROMIUM_MANIFEST_DIR="$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
        ;;
    Linux)
        CHROME_MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
        CHROMIUM_MANIFEST_DIR="$HOME/.config/chromium/NativeMessagingHosts"
        ;;
    *)
        echo "❌ 不支持的操作系统: $OS"
        exit 1
        ;;
esac

# 移除 manifest 文件
remove_manifest() {
    local target_file="$1/$HOST_NAME.json"
    local browser_name="$2"

    if [ -f "$target_file" ]; then
        rm -f "$target_file"
        echo "✅ 已从 $browser_name 移除: $target_file"
    else
        echo "⏭️  $browser_name 中未找到配置文件"
    fi
}

echo "🗑️  正在移除 Native Messaging Host..."
echo ""

remove_manifest "$CHROME_MANIFEST_DIR" "Chrome"
remove_manifest "$CHROMIUM_MANIFEST_DIR" "Chromium"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                     卸载完成！                              ║"
echo "║  请手动从 Chrome 扩展管理页面移除扩展                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
