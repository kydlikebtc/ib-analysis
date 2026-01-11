/**
 * IB Portfolio Analyzer - Background Service Worker
 * 处理 Native Messaging 通信
 */

const NATIVE_HOST_NAME = 'com.ib.portfolio_analyzer';

// 连接状态
let nativePort = null;
let pendingRequests = new Map();
let requestId = 0;

/**
 * 监听来自 popup 的消息
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'NATIVE_MESSAGE') {
    handleNativeMessage(message.payload)
      .then(sendResponse)
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // 保持消息通道开放
  }
});

/**
 * 处理 Native Messaging 请求
 */
async function handleNativeMessage(payload) {
  console.log('[Background] 发送 Native 消息:', payload);

  return new Promise((resolve, reject) => {
    try {
      // 每次请求创建新连接（短连接模式）
      const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
      let responseReceived = false;

      // 设置超时
      const timeout = setTimeout(() => {
        if (!responseReceived) {
          port.disconnect();
          reject(new Error('Native host 响应超时'));
        }
      }, 30000); // 30秒超时

      // 监听响应
      port.onMessage.addListener((response) => {
        responseReceived = true;
        clearTimeout(timeout);
        console.log('[Background] 收到 Native 响应:', response);

        if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }

        port.disconnect();
      });

      // 监听断开连接
      port.onDisconnect.addListener(() => {
        clearTimeout(timeout);
        if (!responseReceived) {
          const error = chrome.runtime.lastError;
          console.error('[Background] Native host 断开连接:', error);
          reject(new Error(error?.message || 'Native host 连接断开'));
        }
      });

      // 发送消息
      port.postMessage(payload);

    } catch (error) {
      console.error('[Background] Native messaging 错误:', error);
      reject(error);
    }
  });
}

/**
 * 扩展安装时的初始化
 */
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[IB Analyzer] 扩展已安装/更新:', details.reason);

  // 设置默认配置
  chrome.storage.local.set({
    settings: {
      autoRefresh: false,
      refreshInterval: 60, // 秒
      showNotifications: true
    }
  });
});

/**
 * 扩展启动时检查 Native Host 可用性
 */
chrome.runtime.onStartup.addListener(() => {
  console.log('[IB Analyzer] 扩展启动');
  checkNativeHostAvailability();
});

/**
 * 检查 Native Host 是否可用
 */
async function checkNativeHostAvailability() {
  try {
    const response = await handleNativeMessage({ action: 'ping' });
    console.log('[IB Analyzer] Native Host 可用:', response);
    return true;
  } catch (error) {
    console.warn('[IB Analyzer] Native Host 不可用:', error.message);
    return false;
  }
}

/**
 * 定期健康检查（可选）
 */
// chrome.alarms.create('healthCheck', { periodInMinutes: 5 });
// chrome.alarms.onAlarm.addListener((alarm) => {
//   if (alarm.name === 'healthCheck') {
//     checkNativeHostAvailability();
//   }
// });
