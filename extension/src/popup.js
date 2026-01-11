/**
 * IB Portfolio Analyzer - Popup Script
 * 处理 UI 交互和 Native Messaging 通信
 */

// 应用状态
const state = {
  isLoading: false,
  lastUpdate: null,
  portfolioData: null,
  error: null
};

// DOM 元素引用
const elements = {
  loadingView: null,
  errorView: null,
  mainView: null,
  statusBadge: null,
  updateTime: null,
  refreshBtn: null,
  fullReportBtn: null
};

/**
 * 初始化应用
 */
document.addEventListener('DOMContentLoaded', () => {
  initElements();
  bindEvents();
  loadCachedData();
  fetchPortfolioData();
});

/**
 * 初始化 DOM 元素引用
 */
function initElements() {
  elements.loadingView = document.getElementById('loading');
  elements.errorView = document.getElementById('error');
  elements.mainView = document.getElementById('content');
  elements.statusBadge = document.getElementById('status');
  elements.updateTime = document.getElementById('last-update');
  elements.refreshBtn = document.getElementById('refresh-btn');
  elements.fullReportBtn = document.getElementById('report-btn');
}

/**
 * 绑定事件监听器
 */
function bindEvents() {
  elements.refreshBtn?.addEventListener('click', () => fetchPortfolioData());
  elements.fullReportBtn?.addEventListener('click', () => generateFullReport());
  document.getElementById('retry-btn')?.addEventListener('click', () => fetchPortfolioData());

  // 设置按钮
  document.getElementById('settings-btn')?.addEventListener('click', () => {
    window.location.href = 'settings.html';
  });
}

/**
 * 从缓存加载数据
 */
function loadCachedData() {
  chrome.storage.local.get(['portfolioData', 'lastUpdate'], (result) => {
    if (result.portfolioData) {
      state.portfolioData = result.portfolioData;
      state.lastUpdate = result.lastUpdate;
      renderPortfolioData(result.portfolioData);
      updateLastUpdateTime(result.lastUpdate);
    }
  });
}

/**
 * 通过 Native Messaging 获取投资组合数据
 */
async function fetchPortfolioData() {
  if (state.isLoading) return;

  setLoadingState(true);
  console.log('[IB Analyzer] 开始获取投资组合数据...');

  try {
    const response = await sendNativeMessage({
      action: 'get_portfolio',
      params: {
        include_greeks: true,
        include_monte_carlo: true,
        include_recommendations: true
      }
    });

    if (response.success) {
      state.portfolioData = response.data;
      state.lastUpdate = new Date().toISOString();
      state.error = null;

      // 缓存数据
      chrome.storage.local.set({
        portfolioData: response.data,
        lastUpdate: state.lastUpdate
      });

      renderPortfolioData(response.data);
      updateConnectionStatus('connected');
      updateLastUpdateTime(state.lastUpdate);
      console.log('[IB Analyzer] 数据获取成功');
    } else {
      throw new Error(response.error || '获取数据失败');
    }
  } catch (error) {
    console.error('[IB Analyzer] 获取数据失败:', error);
    state.error = error.message;
    showError(error.message);
    updateConnectionStatus('error');
  } finally {
    setLoadingState(false);
  }
}

/**
 * 发送 Native Message
 */
function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    const hostName = 'com.ib.portfolio_analyzer';

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
 * 设置加载状态
 */
function setLoadingState(isLoading) {
  state.isLoading = isLoading;

  if (isLoading) {
    elements.loadingView?.classList.remove('hidden');
    elements.errorView?.classList.add('hidden');
    elements.mainView?.classList.add('hidden');
  } else {
    elements.loadingView?.classList.add('hidden');
  }

  if (elements.refreshBtn) {
    elements.refreshBtn.disabled = isLoading;
  }
}

/**
 * 显示错误视图
 */
function showError(message) {
  elements.loadingView?.classList.add('hidden');
  elements.mainView?.classList.add('hidden');
  elements.errorView?.classList.remove('hidden');

  const errorMsg = document.getElementById('error-message');
  if (errorMsg) {
    errorMsg.textContent = message || '连接 IB API 失败，请确保 TWS/IB Gateway 正在运行';
  }
}

/**
 * 渲染投资组合数据
 */
function renderPortfolioData(data) {
  elements.loadingView?.classList.add('hidden');
  elements.errorView?.classList.add('hidden');
  elements.mainView?.classList.remove('hidden');

  renderAccountOverview(data.account);
  renderGreeks(data.greeks);
  renderRiskAssessment(data.risk);
  renderRecommendations(data.recommendations);
  renderPositions(data.positions);
}

/**
 * 渲染账户概览
 */
function renderAccountOverview(account) {
  if (!account) return;

  setElementText('portfolio-value', formatCurrency(account.net_liquidation));
  setElementText('unrealized-pnl', formatCurrency(account.unrealized_pnl),
    account.unrealized_pnl >= 0 ? 'positive' : 'negative');
  // position-count 将在 renderPositions 中设置
}

/**
 * 渲染希腊值汇总
 */
function renderGreeks(greeks) {
  if (!greeks) return;

  // 使用已有的 DOM 元素设置值
  setElementText('delta', formatNumber(greeks.delta, 2));
  setElementText('delta-dollars', formatCurrency(greeks.delta_dollars));
  setElementText('gamma', formatNumber(greeks.gamma, 4));
  setElementText('theta', formatCurrency(greeks.theta_dollars));
  setElementText('vega', formatNumber(greeks.vega, 2));
}

/**
 * 渲染风险评估
 */
function renderRiskAssessment(risk) {
  if (!risk) return;

  // 风险等级徽章
  const riskLevel = document.getElementById('risk-level');
  if (riskLevel) {
    const badge = riskLevel.querySelector('.risk-badge');
    if (badge) {
      badge.textContent = risk.level;
      badge.className = `risk-badge ${risk.level}`;
    }
  }

  // 风险评分
  setElementText('risk-score', `${risk.score}/100`);

  // 风险指标
  setElementText('expected-return', formatCurrency(risk.expected_return || 0));
  setElementText('var-95', formatCurrency(risk.var_95));
  setElementText('prob-loss', `${(risk.probability_loss * 100).toFixed(1)}%`);
}

/**
 * 渲染建议列表
 */
function renderRecommendations(recommendations) {
  const container = document.getElementById('recommendations');
  if (!container || !recommendations) return;

  if (recommendations.length === 0) {
    container.innerHTML = '<p style="color: #666; text-align: center;">暂无建议</p>';
    return;
  }

  container.innerHTML = recommendations.slice(0, 5).map(rec => `
    <div class="recommendation ${rec.priority}">
      <span class="priority">${rec.priority}</span>
      <span class="text">${rec.message}</span>
    </div>
  `).join('');
}

/**
 * 渲染持仓列表
 */
function renderPositions(positions) {
  const container = document.getElementById('positions');
  if (!container || !positions) return;

  // 更新持仓数量
  setElementText('position-count', positions.length.toString());

  const header = `
    <div class="position-row header">
      <span>标的</span>
      <span>数量</span>
      <span>市值</span>
      <span>盈亏</span>
    </div>
  `;

  const rows = positions.slice(0, 10).map(pos => `
    <div class="position-row">
      <div>
        <span class="position-symbol">${pos.symbol}</span>
        <span class="position-type">${pos.sec_type}</span>
      </div>
      <span>${pos.position}</span>
      <span>${formatCurrency(pos.market_value)}</span>
      <span class="position-pnl ${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
        ${formatCurrency(pos.unrealized_pnl)}
      </span>
    </div>
  `).join('');

  container.innerHTML = header + rows;
}

/**
 * 更新连接状态
 */
function updateConnectionStatus(status) {
  if (!elements.statusBadge) return;

  elements.statusBadge.className = `status ${status}`;
  elements.statusBadge.textContent = status === 'connected' ? '已连接' :
                                      status === 'error' ? '断开' : '连接中';
}

/**
 * 更新最后更新时间
 */
function updateLastUpdateTime(isoString) {
  if (!elements.updateTime || !isoString) return;

  const date = new Date(isoString);
  elements.updateTime.textContent = `最后更新: ${date.toLocaleTimeString('zh-CN')}`;
}

/**
 * 生成完整报告
 */
async function generateFullReport() {
  try {
    const response = await sendNativeMessage({
      action: 'generate_report',
      params: { format: 'html' }
    });

    if (response.success && response.report_path) {
      // 通知用户报告已生成
      alert(`报告已生成: ${response.report_path}`);
    }
  } catch (error) {
    console.error('[IB Analyzer] 生成报告失败:', error);
    alert('生成报告失败: ' + error.message);
  }
}

// ========== 工具函数 ==========

/**
 * 格式化货币
 */
function formatCurrency(value) {
  if (value === null || value === undefined) return '--';

  const absValue = Math.abs(value);
  const sign = value < 0 ? '-' : (value > 0 ? '+' : '');

  if (absValue >= 1000000) {
    return `${sign}$${(absValue / 1000000).toFixed(2)}M`;
  } else if (absValue >= 1000) {
    return `${sign}$${(absValue / 1000).toFixed(1)}K`;
  } else {
    return `${sign}$${absValue.toFixed(2)}`;
  }
}

/**
 * 格式化数字
 */
function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined) return '--';
  return value.toFixed(decimals);
}

/**
 * 设置元素文本和可选的类
 */
function setElementText(id, text, className = null) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = text;
    if (className) {
      el.className = `value ${className}`;
    }
  }
}
