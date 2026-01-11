/**
 * IB Portfolio Analyzer - 设置页面
 */

// 默认设置
const DEFAULT_SETTINGS = {
  ib: {
    host: '127.0.0.1',
    port: 7497,
    clientId: 1
  },
  refresh: {
    auto: false,
    interval: 60
  },
  notifications: {
    show: true
  },
  data: {
    includeGreeks: true,
    includeMonteCarlo: true,
    includeRecommendations: true
  }
};

// DOM 元素
const elements = {};

/**
 * 初始化页面
 */
document.addEventListener('DOMContentLoaded', () => {
  initElements();
  bindEvents();
  loadSettings();
});

/**
 * 初始化 DOM 元素引用
 */
function initElements() {
  // IB 连接设置
  elements.ibHost = document.getElementById('ib-host');
  elements.ibPort = document.getElementById('ib-port');
  elements.clientId = document.getElementById('client-id');

  // 刷新设置
  elements.autoRefresh = document.getElementById('auto-refresh');
  elements.refreshInterval = document.getElementById('refresh-interval');
  elements.refreshIntervalGroup = document.getElementById('refresh-interval-group');

  // 通知设置
  elements.showNotifications = document.getElementById('show-notifications');

  // 数据设置
  elements.includeGreeks = document.getElementById('include-greeks');
  elements.includeMonteCarlo = document.getElementById('include-monte-carlo');
  elements.includeRecommendations = document.getElementById('include-recommendations');

  // 按钮
  elements.backBtn = document.getElementById('back-btn');
  elements.saveBtn = document.getElementById('save-btn');
  elements.testConnection = document.getElementById('test-connection');
  elements.clearCache = document.getElementById('clear-cache');
  elements.resetSettings = document.getElementById('reset-settings');

  // Toast
  elements.toast = document.getElementById('toast');
  elements.toastMessage = document.getElementById('toast-message');
}

/**
 * 绑定事件
 */
function bindEvents() {
  // 返回按钮
  elements.backBtn?.addEventListener('click', () => {
    window.location.href = 'popup.html';
  });

  // 保存按钮
  elements.saveBtn?.addEventListener('click', saveSettings);

  // 自动刷新开关
  elements.autoRefresh?.addEventListener('change', () => {
    updateRefreshIntervalVisibility();
  });

  // 预设按钮
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const port = parseInt(btn.dataset.port);
      if (elements.ibPort) {
        elements.ibPort.value = port;
      }
      // 更新预设按钮状态
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // 测试连接
  elements.testConnection?.addEventListener('click', testConnection);

  // 清除缓存
  elements.clearCache?.addEventListener('click', clearCache);

  // 重置设置
  elements.resetSettings?.addEventListener('click', resetSettings);
}

/**
 * 加载设置
 */
function loadSettings() {
  chrome.storage.local.get(['settings'], (result) => {
    const settings = { ...DEFAULT_SETTINGS, ...result.settings };

    // IB 连接设置
    if (elements.ibHost) elements.ibHost.value = settings.ib?.host || DEFAULT_SETTINGS.ib.host;
    if (elements.ibPort) elements.ibPort.value = settings.ib?.port || DEFAULT_SETTINGS.ib.port;
    if (elements.clientId) elements.clientId.value = settings.ib?.clientId || DEFAULT_SETTINGS.ib.clientId;

    // 刷新设置
    if (elements.autoRefresh) elements.autoRefresh.checked = settings.refresh?.auto || false;
    if (elements.refreshInterval) elements.refreshInterval.value = settings.refresh?.interval || DEFAULT_SETTINGS.refresh.interval;

    // 通知设置
    if (elements.showNotifications) elements.showNotifications.checked = settings.notifications?.show !== false;

    // 数据设置
    if (elements.includeGreeks) elements.includeGreeks.checked = settings.data?.includeGreeks !== false;
    if (elements.includeMonteCarlo) elements.includeMonteCarlo.checked = settings.data?.includeMonteCarlo !== false;
    if (elements.includeRecommendations) elements.includeRecommendations.checked = settings.data?.includeRecommendations !== false;

    updateRefreshIntervalVisibility();
    updatePresetButtonState();
  });
}

/**
 * 保存设置
 */
function saveSettings() {
  const settings = {
    ib: {
      host: elements.ibHost?.value || DEFAULT_SETTINGS.ib.host,
      port: parseInt(elements.ibPort?.value) || DEFAULT_SETTINGS.ib.port,
      clientId: parseInt(elements.clientId?.value) || DEFAULT_SETTINGS.ib.clientId
    },
    refresh: {
      auto: elements.autoRefresh?.checked || false,
      interval: parseInt(elements.refreshInterval?.value) || DEFAULT_SETTINGS.refresh.interval
    },
    notifications: {
      show: elements.showNotifications?.checked !== false
    },
    data: {
      includeGreeks: elements.includeGreeks?.checked !== false,
      includeMonteCarlo: elements.includeMonteCarlo?.checked !== false,
      includeRecommendations: elements.includeRecommendations?.checked !== false
    }
  };

  // 验证
  if (settings.ib.port < 1 || settings.ib.port > 65535) {
    showToast('端口号必须在 1-65535 之间', 'error');
    return;
  }

  if (settings.refresh.interval < 10 || settings.refresh.interval > 3600) {
    showToast('刷新间隔必须在 10-3600 秒之间', 'error');
    return;
  }

  chrome.storage.local.set({ settings }, () => {
    showToast('设置已保存', 'success');
    console.log('[Settings] 设置已保存:', settings);
  });
}

/**
 * 更新刷新间隔输入框可见性
 */
function updateRefreshIntervalVisibility() {
  if (elements.refreshIntervalGroup) {
    elements.refreshIntervalGroup.style.display = elements.autoRefresh?.checked ? 'block' : 'none';
  }
}

/**
 * 更新预设按钮状态
 */
function updatePresetButtonState() {
  const currentPort = elements.ibPort?.value;
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.port === currentPort);
  });
}

/**
 * 测试连接
 */
async function testConnection() {
  const btn = elements.testConnection;
  if (!btn) return;

  const originalText = btn.innerHTML;
  btn.innerHTML = '<span class="btn-icon">⏳</span> 测试中...';
  btn.disabled = true;

  try {
    const response = await sendNativeMessage({
      action: 'test_connection',
      params: {
        host: elements.ibHost?.value || DEFAULT_SETTINGS.ib.host,
        port: parseInt(elements.ibPort?.value) || DEFAULT_SETTINGS.ib.port,
        clientId: parseInt(elements.clientId?.value) || DEFAULT_SETTINGS.ib.clientId
      }
    });

    if (response.success) {
      showToast('连接成功！', 'success');
    } else {
      showToast(`连接失败: ${response.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`连接失败: ${error.message}`, 'error');
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

/**
 * 清除缓存
 */
function clearCache() {
  chrome.storage.local.remove(['portfolioData', 'lastUpdate'], () => {
    showToast('缓存已清除', 'success');
  });
}

/**
 * 重置设置
 */
function resetSettings() {
  if (confirm('确定要重置所有设置为默认值吗？')) {
    chrome.storage.local.set({ settings: DEFAULT_SETTINGS }, () => {
      loadSettings();
      showToast('设置已重置', 'success');
    });
  }
}

/**
 * 发送 Native Message
 */
function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { type: 'NATIVE_MESSAGE', payload: message },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else if (response && response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }
      }
    );
  });
}

/**
 * 显示 Toast 提示
 */
function showToast(message, type = 'info') {
  if (!elements.toast || !elements.toastMessage) return;

  elements.toastMessage.textContent = message;
  elements.toast.className = `toast ${type}`;
  elements.toast.classList.remove('hidden');

  setTimeout(() => {
    elements.toast.classList.add('hidden');
  }, 3000);
}
