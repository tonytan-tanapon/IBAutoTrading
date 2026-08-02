const $ = (id) => document.getElementById(id);
let latestHistoricalBars = [];

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderTable(targetId, columns, rows, emptyText) {
  const target = $(targetId);
  target.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    target.append(empty);
    return;
  }
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  columns.forEach(({ label }) => {
    const th = document.createElement("th");
    th.textContent = label;
    head.append(th);
  });
  const body = table.createTBody();
  rows.forEach((row) => {
    const tr = body.insertRow();
    columns.forEach(({ key }) => {
      const td = tr.insertCell();
      td.textContent = displayValue(row[key]);
    });
  });
  target.append(table);
}

function flatten(value, prefix = "", result = []) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    Object.entries(value).forEach(([key, item]) => flatten(item, prefix ? `${prefix}.${key}` : key, result));
  } else {
    result.push({ field: prefix || "value", value: displayValue(value) });
  }
  return result;
}

function objectRows(data) {
  return Object.entries(data || {}).map(([id, value]) => ({ id, ...(value || {}) }));
}

function accountRows(data) {
  const rows = [];
  Object.entries(data || {}).forEach(([account, metrics]) => {
    Object.entries(metrics || {}).forEach(([metric, item]) => rows.push({ account, metric, value: item?.value, currency: item?.currency }));
  });
  return rows;
}

function dynamicColumns(rows, leading = "id") {
  const keys = new Set([leading]);
  rows.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
  return [...keys].slice(0, 10).map((key) => ({ key, label: key.replaceAll("_", " ") }));
}

function drawCandlestickChart(bars) {
  latestHistoricalBars = Array.isArray(bars) ? bars.filter((bar) =>
    [bar.open, bar.high, bar.low, bar.close].every((value) => Number.isFinite(Number(value)))
  ) : [];

  const canvas = $("candlestick-chart");
  const empty = $("chart-empty");
  const range = $("chart-range");
  if (!latestHistoricalBars.length) {
    empty.classList.remove("hidden");
    range.textContent = "Waiting for bars";
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  empty.classList.add("hidden");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const width = rect.width;
  const height = rect.height;
  const padding = { top: 16, right: 70, bottom: 34, left: 12 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const lows = latestHistoricalBars.map((bar) => Number(bar.low));
  const highs = latestHistoricalBars.map((bar) => Number(bar.high));
  let minPrice = Math.min(...lows);
  let maxPrice = Math.max(...highs);
  const pricePadding = Math.max((maxPrice - minPrice) * 0.08, maxPrice * 0.002);
  minPrice -= pricePadding;
  maxPrice += pricePadding;
  const priceRange = maxPrice - minPrice || 1;
  const priceY = (price) => padding.top + ((maxPrice - price) / priceRange) * plotHeight;

  ctx.clearRect(0, 0, width, height);
  ctx.font = "11px Inter, system-ui, sans-serif";
  ctx.lineWidth = 1;
  ctx.textBaseline = "middle";

  for (let line = 0; line <= 5; line += 1) {
    const y = padding.top + (plotHeight / 5) * line;
    const price = maxPrice - (priceRange / 5) * line;
    ctx.strokeStyle = "rgba(134, 147, 167, .16)";
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = "#8693a7";
    ctx.fillText(price.toFixed(2), width - padding.right + 10, y);
  }

  const slot = plotWidth / latestHistoricalBars.length;
  const candleWidth = Math.max(3, Math.min(16, slot * 0.62));
  latestHistoricalBars.forEach((bar, index) => {
    const open = Number(bar.open);
    const high = Number(bar.high);
    const low = Number(bar.low);
    const close = Number(bar.close);
    const x = padding.left + slot * index + slot / 2;
    const rising = close >= open;
    const color = rising ? "#46d597" : "#ff667d";
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, priceY(high));
    ctx.lineTo(x, priceY(low));
    ctx.stroke();
    const bodyTop = Math.min(priceY(open), priceY(close));
    const bodyHeight = Math.max(1.5, Math.abs(priceY(open) - priceY(close)));
    ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
  });

  const labelIndexes = [...new Set([0, Math.floor((latestHistoricalBars.length - 1) / 2), latestHistoricalBars.length - 1])];
  ctx.textBaseline = "alphabetic";
  labelIndexes.forEach((index) => {
    const bar = latestHistoricalBars[index];
    const x = padding.left + slot * index + slot / 2;
    const label = String(bar.time || "").replace("  ", " ");
    ctx.fillStyle = "#8693a7";
    ctx.textAlign = index === 0 ? "left" : index === latestHistoricalBars.length - 1 ? "right" : "center";
    ctx.fillText(label, x, height - 8);
  });
  ctx.textAlign = "left";
  range.textContent = `${latestHistoricalBars.length} bars · ${displayValue(latestHistoricalBars[0].time)} → ${displayValue(latestHistoricalBars.at(-1).time)}`;
}

function updateStatus(status) {
  const online = status.tws_connected;
  const running = status.engine_running;
  const badge = $("connection-badge");
  badge.className = `badge ${online ? "badge-online" : running ? "badge-starting" : "badge-offline"}`;
  badge.innerHTML = `<span></span>${online ? "TWS Connected" : running ? "Starting" : "Offline"}`;
  $("start-button").disabled = running;
  $("stop-button").disabled = !running;
  $("symbol-value").textContent = status.symbol || "—";
  $("strategy-name").textContent = status.strategy_name || "—";
  $("trading-mode").textContent = status.dry_run_orders ? "DRY RUN" : "LIVE ORDERS";
  $("trading-mode").className = `metric-value ${status.dry_run_orders ? "safe-text" : "signal-sell"}`;
  const alert = $("alert");
  if (status.error) {
    alert.textContent = status.error;
    alert.classList.remove("hidden");
  } else {
    alert.classList.add("hidden");
  }
  const errors = status.recent_ib_errors || [];
  renderTable("errors-table", [
    { key: "code", label: "Code" }, { key: "req_id", label: "Request" }, { key: "message", label: "Message" }
  ], errors.slice().reverse(), "No IB events reported");
}

function updateDashboard(data) {
  const quote = data.market_data?.[data.symbol] || Object.values(data.market_data || {})[0] || {};
  $("last-price").textContent = displayValue(quote.last ?? quote.close ?? quote.market_price);
  $("bid-ask").textContent = `Bid ${displayValue(quote.bid)} · Ask ${displayValue(quote.ask)}`;
  $("market-updated").textContent = quote.updated_at ? `Updated ${quote.updated_at}` : "Waiting for market data";
  $("bar-count").textContent = displayValue(data.historical_bar_count || 0);
  drawCandlestickChart(data.historical_data || []);

  const signal = data.strategy?.signal || {};
  const action = String(signal.action || "WAIT").toUpperCase();
  $("signal-value").textContent = action;
  $("signal-value").className = `metric-value ${action === "BUY" ? "signal-buy" : action === "SELL" ? "signal-sell" : "signal-neutral"}`;

  renderTable("account-table", [
    { key: "account", label: "Account" }, { key: "metric", label: "Metric" }, { key: "value", label: "Value" }, { key: "currency", label: "Currency" }
  ], accountRows(data.account_summary), "Account data will appear after the engine starts");

  const positions = objectRows(data.positions);
  const orders = objectRows(data.orders);
  $("position-count").textContent = positions.length;
  $("order-count").textContent = orders.length;
  renderTable("positions-table", dynamicColumns(positions), positions, "No open positions");
  renderTable("orders-table", dynamicColumns(orders), orders, "No open orders");
  renderTable("strategy-table", [
    { key: "field", label: "Field" }, { key: "value", label: "Value" }
  ], flatten(data.strategy || {}), data.strategy_error || "Strategy snapshot will appear after startup");
  $("last-refresh").textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

async function refresh() {
  try {
    const [status, dashboard] = await Promise.all([fetchJson("/api/status"), fetchJson("/api/dashboard")]);
    updateStatus(status);
    updateDashboard(dashboard);
  } catch (error) {
    const alert = $("alert");
    alert.textContent = `Dashboard error: ${error.message}`;
    alert.classList.remove("hidden");
  }
}

async function controlEngine(action) {
  try {
    await fetchJson(`/api/engine/${action}`, { method: "POST" });
    await refresh();
  } catch (error) {
    const alert = $("alert");
    alert.textContent = error.message;
    alert.classList.remove("hidden");
  }
}

$("start-button").addEventListener("click", () => controlEngine("start"));
$("stop-button").addEventListener("click", () => controlEngine("stop"));
window.addEventListener("resize", () => drawCandlestickChart(latestHistoricalBars));
refresh();
setInterval(refresh, 2000);
