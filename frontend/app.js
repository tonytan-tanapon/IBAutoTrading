const elements = {
  serverStatus: document.querySelector("#server-status"),
  twsStatus: document.querySelector("#tws-status"),
  twsStatusDot: document.querySelector("#tws-status-dot"),
  connectButton: document.querySelector("#connect-button"),
  disconnectButton: document.querySelector("#disconnect-button"),
  disconnectAllButton: document.querySelector("#disconnect-all-button"),
  refreshButton: document.querySelector("#refresh-button"),
  buyingPower: document.querySelector("#buying-power"),
  accountNumber: document.querySelector("#account-number"),
  accountEnvironment: document.querySelector("#account-environment"),
  positionsBody: document.querySelector("#positions-body"),
  positionCount: document.querySelector("#position-count"),
  marketForm: document.querySelector("#market-form"),
  marketSymbol: document.querySelector("#market-symbol"),
  marketQuotes: document.querySelector("#market-quotes"),
  strategyStatus: document.querySelector("#strategy-status"),
  strategyName: document.querySelector("#strategy-name"),
  strategySignal: document.querySelector("#strategy-signal"),
  strategyChecked: document.querySelector("#strategy-checked"),
  strategyClose: document.querySelector("#strategy-close"),
  strategyShortSma: document.querySelector("#strategy-short-sma"),
  strategyLongSma: document.querySelector("#strategy-long-sma"),
  strategyHigh: document.querySelector("#strategy-high"),
  strategyLow: document.querySelector("#strategy-low"),
  rangeLevels: document.querySelector("#range-levels"),
  callEntry: document.querySelector("#call-entry"),
  callTarget: document.querySelector("#call-target"),
  callStop: document.querySelector("#call-stop"),
  putEntry: document.querySelector("#put-entry"),
  putTarget: document.querySelector("#put-target"),
  putStop: document.querySelector("#put-stop"),
  strategyMessage: document.querySelector("#strategy-message"),
  strategyForm: document.querySelector("#strategy-form"),
  strategyType: document.querySelector("#strategy-type"),
  strategySymbol: document.querySelector("#strategy-symbol"),
  strategyInterval: document.querySelector("#strategy-interval"),
  strategyShortWindow: document.querySelector("#strategy-short-window"),
  strategyLongWindow: document.querySelector("#strategy-long-window"),
  strategySaveButton: document.querySelector("#strategy-save-button"),
  strategyCheckButton: document.querySelector("#strategy-check-button"),
  strategyStartButton: document.querySelector("#strategy-start-button"),
  strategyStopButton: document.querySelector("#strategy-stop-button"),
  orderForm: document.querySelector("#order-form"),
  orderSymbol: document.querySelector("#order-symbol"),
  orderAction: document.querySelector("#order-action"),
  orderQuantity: document.querySelector("#order-quantity"),
  orderType: document.querySelector("#order-type"),
  orderLimitPrice: document.querySelector("#order-limit-price"),
  limitPriceField: document.querySelector("#limit-price-field"),
  orderPreview: document.querySelector("#order-preview"),
  previewOrderButton: document.querySelector("#preview-order-button"),
  submitOrderButton: document.querySelector("#submit-order-button"),
  ordersBody: document.querySelector("#orders-body"),
  orderCount: document.querySelector("#order-count"),
  riskForm: document.querySelector("#risk-form"),
  maxQuantity: document.querySelector("#max-quantity"),
  maxOrderValue: document.querySelector("#max-order-value"),
  killSwitch: document.querySelector("#kill-switch"),
  log: document.querySelector("#log"),
};

let currentPreviewId = null;
let strategyFormDirty = false;

function updateStatus(element, connected, text) {
  element.textContent = text;
  element.classList.toggle("connected", connected);
  element.classList.toggle("disconnected", !connected);
}

function updateTwsStatus(connected, text) {
  updateStatus(elements.twsStatus, connected, text);
  elements.twsStatusDot.classList.toggle("connected", connected);
  elements.twsStatusDot.classList.toggle("disconnected", !connected);
}

function addLog(message) {
  const time = new Date().toLocaleTimeString();
  elements.log.textContent += `\n[${time}] ${message}`;
  elements.log.scrollTop = elements.log.scrollHeight;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

async function loadStatus() {
  try {
    const data = await request("/api/status");
    updateStatus(elements.serverStatus, true, "API Running");
    updateTwsStatus(
      data.connected,
      data.connected ? "Connected" : "Disconnected",
    );

    await Promise.all([
      loadAccountSummary(data.connected),
      loadPositions(data.connected),
      loadMarketData(),
      loadOrders(),
      loadRiskSettings(),
      loadStrategy(),
    ]);
  } catch (error) {
    updateStatus(elements.serverStatus, false, "API Offline");
    updateTwsStatus(false, "Unknown");
    addLog(`Refresh failed: ${error.message}`);
  }
}

async function loadAccountSummary(connected) {
  if (!connected) {
    elements.buyingPower.textContent = "-";
    elements.accountNumber.textContent = "-";
    elements.accountEnvironment.textContent = "-";
    return;
  }
  const data = await request("/api/account/summary");
  elements.buyingPower.textContent =
    data.buying_power === null
      ? "Loading..."
      : `${formatNumber(data.buying_power)} ${data.currency || ""}`;
  elements.accountNumber.textContent = data.accounts[0] || "-";
  elements.accountEnvironment.textContent = data.paper_account
    ? "Paper"
    : "Live / Unknown";
}

async function loadPositions(connected) {
  if (!connected) {
    renderPositions([]);
    return;
  }
  const data = await request("/api/positions");
  renderPositions(data.positions);
}

function renderPositions(positions) {
  elements.positionCount.textContent = `${positions.length} positions`;
  if (!positions.length) {
    elements.positionsBody.innerHTML =
      '<tr class="empty-row"><td colspan="6">No open positions.</td></tr>';
    return;
  }
  elements.positionsBody.innerHTML = positions
    .map((position) => {
      const pnlClass =
        position.unrealized_pnl > 0
          ? "positive"
          : position.unrealized_pnl < 0
            ? "negative"
            : "";
      return `<tr>
        <td><strong>${position.symbol}</strong></td>
        <td>${formatNumber(position.quantity, 0)}</td>
        <td>${formatNumber(position.average_cost)}</td>
        <td>${formatNumber(position.market_price)}</td>
        <td>${formatNumber(position.market_value)}</td>
        <td class="${pnlClass}">${formatNumber(position.unrealized_pnl)}</td>
      </tr>`;
    })
    .join("");
}

async function loadMarketData() {
  const data = await request("/api/market-data");
  if (!data.items.length) {
    elements.marketQuotes.innerHTML =
      '<p class="empty-message">No market data subscriptions.</p>';
    return;
  }
  elements.marketQuotes.innerHTML = data.items
    .map(
      (quote) => `<article class="quote">
        <div><strong>${quote.symbol}</strong><small>Streaming</small></div>
        <dl>
          <div><dt>Bid</dt><dd>${formatNumber(quote.bid)}</dd></div>
          <div><dt>Ask</dt><dd>${formatNumber(quote.ask)}</dd></div>
          <div><dt>Last</dt><dd>${formatNumber(quote.last || quote.close)}</dd></div>
        </dl>
        <button class="ghost small" data-unsubscribe="${quote.symbol}">Remove</button>
      </article>`,
    )
    .join("");
}

async function loadOrders() {
  const data = await request("/api/orders");
  elements.orderCount.textContent = `${data.orders.length} orders`;
  if (!data.orders.length) {
    elements.ordersBody.innerHTML =
      '<tr class="empty-row"><td colspan="9">No orders received.</td></tr>';
    return;
  }
  elements.ordersBody.innerHTML = data.orders
    .sort((a, b) => b.order_id - a.order_id)
    .map((order) => {
      const canCancel = !["Filled", "Cancelled", "ApiCancelled"].includes(
        order.status,
      );
      return `<tr>
        <td>${order.order_id}</td>
        <td><strong>${order.symbol || "-"}</strong></td>
        <td>${order.action || "-"}</td>
        <td>${order.order_type || "-"}</td>
        <td>${formatNumber(order.quantity, 0)}</td>
        <td>${order.status || "-"}</td>
        <td>${formatNumber(order.filled, 0)}</td>
        <td>${formatNumber(order.average_fill_price)}</td>
        <td>${
          canCancel
            ? `<button class="danger small" data-cancel-order="${order.order_id}">Cancel</button>`
            : "-"
        }</td>
      </tr>`;
    })
    .join("");
}

async function loadRiskSettings() {
  const data = await request("/api/risk");
  elements.maxQuantity.value = data.max_quantity;
  elements.maxOrderValue.value = data.max_order_value;
  elements.killSwitch.checked = data.kill_switch;
}

async function loadStrategy() {
  const data = await request("/api/strategy/status");
  elements.strategyStatus.textContent = data.enabled ? "Enabled" : "Disabled";
  elements.strategyStatus.classList.toggle("connected", data.enabled);
  elements.strategyStatus.classList.toggle("neutral", !data.enabled);
  elements.strategyName.textContent = data.name;
  elements.strategySignal.textContent = data.last_signal || "-";
  elements.strategyChecked.textContent = data.last_checked_at || "-";
  elements.strategyClose.textContent = formatNumber(data.last_close);
  elements.strategyShortSma.textContent = formatNumber(data.short_sma);
  elements.strategyLongSma.textContent = formatNumber(data.long_sma);
  elements.strategyHigh.textContent = formatNumber(data.previous_high);
  elements.strategyLow.textContent = formatNumber(data.previous_low);
  elements.callEntry.textContent = formatNumber(data.call_entry);
  elements.callTarget.textContent = formatNumber(data.call_target);
  elements.callStop.textContent = formatNumber(data.call_stop);
  elements.putEntry.textContent = formatNumber(data.put_entry);
  elements.putTarget.textContent = formatNumber(data.put_target);
  elements.putStop.textContent = formatNumber(data.put_stop);
  if (!strategyFormDirty) {
    elements.strategyType.value = data.strategy_type;
    elements.strategySymbol.value = data.symbol;
    elements.strategyInterval.value = data.interval_seconds;
    elements.strategyShortWindow.value = data.short_window;
    elements.strategyLongWindow.value = data.long_window;
  }
  elements.strategyMessage.textContent = data.error
    ? `Error: ${data.error}`
    : data.message;
  elements.strategyCheckButton.disabled = data.running_check;
  updateStrategyFields();
}

function strategyPayload() {
  return {
    strategy_type: elements.strategyType.value,
    symbol: elements.strategySymbol.value.trim().toUpperCase(),
    short_window: Number(elements.strategyShortWindow.value),
    long_window: Number(elements.strategyLongWindow.value),
    interval_seconds: Number(elements.strategyInterval.value),
  };
}

function updateStrategyFields() {
  const isRange = elements.strategyType.value === "PREVIOUS_4H_RANGE";
  document.querySelectorAll(".sma-setting, .sma-result").forEach((element) => {
    element.classList.toggle("hidden", isRange);
  });
  document.querySelectorAll(".range-result").forEach((element) => {
    element.classList.toggle("hidden", !isRange);
  });
  elements.rangeLevels.classList.toggle("hidden", !isRange);
}

async function saveStrategy() {
  try {
    await request("/api/strategy/config", {
      method: "PUT",
      body: JSON.stringify(strategyPayload()),
    });
    strategyFormDirty = false;
    addLog("Strategy configuration saved.");
    await loadStrategy();
    return true;
  } catch (error) {
    addLog(`Strategy configuration failed: ${error.message}`);
    return false;
  }
}

async function checkStrategy() {
  try {
    if (!(await saveStrategy())) return;
    const data = await request("/api/strategy/check", { method: "POST" });
    addLog(data.message);
    setTimeout(loadStrategy, 1500);
  } catch (error) {
    addLog(`Strategy check failed: ${error.message}`);
  }
}

async function startStrategy() {
  try {
    if (!(await saveStrategy())) return;
    await request("/api/strategy/start", { method: "POST" });
    addLog("Signal-only strategy enabled.");
    await loadStrategy();
  } catch (error) {
    addLog(`Enable strategy failed: ${error.message}`);
  }
}

async function stopStrategy() {
  try {
    await request("/api/strategy/stop", { method: "POST" });
    addLog("Strategy disabled.");
    await loadStrategy();
  } catch (error) {
    addLog(`Disable strategy failed: ${error.message}`);
  }
}

async function connectTws() {
  addLog("Connecting to TWS...");
  try {
    const data = await request("/api/connect", { method: "POST" });
    addLog(data.error ? `${data.message}: ${data.error}` : data.message);
    await loadStatus();
  } catch (error) {
    addLog(`Connect failed: ${error.message}`);
  }
}

async function disconnectTws() {
  try {
    const data = await request("/api/disconnect", { method: "POST" });
    addLog(data.message);
    await loadStatus();
  } catch (error) {
    addLog(`Disconnect failed: ${error.message}`);
  }
}

async function disconnectAll() {
  const confirmed = window.confirm(
    "Stop the strategy, cancel market data subscriptions, and disconnect this app from TWS?\n\nExisting orders will NOT be cancelled.",
  );
  if (!confirmed) return;

  try {
    const data = await request("/api/disconnect-all", { method: "POST" });
    addLog(data.message);
    resetPreview();
    await loadStatus();
  } catch (error) {
    addLog(`Disconnect All failed: ${error.message}`);
  }
}

async function subscribeMarketData(event) {
  event.preventDefault();
  try {
    const symbol = elements.marketSymbol.value.trim().toUpperCase();
    const data = await request("/api/market-data/subscribe", {
      method: "POST",
      body: JSON.stringify({ symbol }),
    });
    addLog(data.message);
    elements.orderSymbol.value = symbol;
    await loadMarketData();
  } catch (error) {
    addLog(`Market data failed: ${error.message}`);
  }
}

function resetPreview() {
  currentPreviewId = null;
  elements.submitOrderButton.disabled = true;
  elements.orderPreview.textContent =
    "Preview an order to review its estimated value.";
}

function orderPayload() {
  const orderType = elements.orderType.value;
  return {
    symbol: elements.orderSymbol.value.trim().toUpperCase(),
    action: elements.orderAction.value,
    quantity: Number(elements.orderQuantity.value),
    order_type: orderType,
    limit_price:
      orderType === "LMT" ? Number(elements.orderLimitPrice.value) : null,
  };
}

async function previewOrder() {
  try {
    const data = await request("/api/orders/preview", {
      method: "POST",
      body: JSON.stringify(orderPayload()),
    });
    currentPreviewId = data.preview_id;
    const preview = data.preview;
    elements.orderPreview.innerHTML = `<strong>${preview.action} ${preview.quantity} ${preview.symbol}</strong>
      <span>${preview.order_type} at ${formatNumber(preview.estimated_price)}</span>
      <span>Estimated value: ${formatNumber(preview.estimated_value)}</span>`;
    elements.submitOrderButton.disabled = false;
    addLog("Order preview created. Review it before submitting.");
  } catch (error) {
    resetPreview();
    addLog(`Preview failed: ${error.message}`);
  }
}

async function submitOrder() {
  if (!currentPreviewId) return;
  try {
    const data = await request("/api/orders/submit", {
      method: "POST",
      body: JSON.stringify({ preview_id: currentPreviewId }),
    });
    addLog(`${data.message}. Order ID: ${data.order_id}`);
    resetPreview();
    await loadOrders();
  } catch (error) {
    addLog(`Submit failed: ${error.message}`);
    resetPreview();
  }
}

async function saveRiskSettings(event) {
  event.preventDefault();
  try {
    await request("/api/risk", {
      method: "PUT",
      body: JSON.stringify({
        max_quantity: Number(elements.maxQuantity.value),
        max_order_value: Number(elements.maxOrderValue.value),
        kill_switch: elements.killSwitch.checked,
      }),
    });
    addLog("Risk settings saved.");
    resetPreview();
  } catch (error) {
    addLog(`Risk update failed: ${error.message}`);
  }
}

elements.connectButton.addEventListener("click", connectTws);
elements.disconnectButton.addEventListener("click", disconnectTws);
elements.disconnectAllButton.addEventListener("click", disconnectAll);
elements.refreshButton.addEventListener("click", loadStatus);
elements.marketForm.addEventListener("submit", subscribeMarketData);
elements.previewOrderButton.addEventListener("click", previewOrder);
elements.submitOrderButton.addEventListener("click", submitOrder);
elements.riskForm.addEventListener("submit", saveRiskSettings);
elements.strategySaveButton.addEventListener("click", saveStrategy);
elements.strategyCheckButton.addEventListener("click", checkStrategy);
elements.strategyStartButton.addEventListener("click", startStrategy);
elements.strategyStopButton.addEventListener("click", stopStrategy);
elements.strategyForm.addEventListener("input", () => {
  strategyFormDirty = true;
});
elements.strategyType.addEventListener("change", () => {
  strategyFormDirty = true;
  updateStrategyFields();
});
elements.orderForm.addEventListener("input", resetPreview);
elements.orderType.addEventListener("change", () => {
  elements.limitPriceField.classList.toggle(
    "hidden",
    elements.orderType.value !== "LMT",
  );
  resetPreview();
});

elements.marketQuotes.addEventListener("click", async (event) => {
  const symbol = event.target.dataset.unsubscribe;
  if (!symbol) return;
  try {
    const data = await request("/api/market-data/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ symbol }),
    });
    addLog(data.message);
    await loadMarketData();
  } catch (error) {
    addLog(`Unsubscribe failed: ${error.message}`);
  }
});

elements.ordersBody.addEventListener("click", async (event) => {
  const orderId = event.target.dataset.cancelOrder;
  if (!orderId) return;
  try {
    const data = await request(`/api/orders/${orderId}/cancel`, {
      method: "POST",
    });
    addLog(data.message);
  } catch (error) {
    addLog(`Cancel failed: ${error.message}`);
  }
});

loadStatus();
setInterval(loadStatus, 5000);
