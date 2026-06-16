const form = document.querySelector("#history-form");
const strategy = document.querySelector("#history-strategy");
const symbol = document.querySelector("#history-symbol");
const shortWindow = document.querySelector("#history-short-window");
const longWindow = document.querySelector("#history-long-window");
const limit = document.querySelector("#history-limit");
const statusBadge = document.querySelector("#history-status");
const title = document.querySelector("#history-title");
const count = document.querySelector("#history-count");
const head = document.querySelector("#history-head");
const body = document.querySelector("#history-body");
const loadButton = document.querySelector("#load-history-button");
const chart = document.querySelector("#history-chart");
const chartWrapper = document.querySelector("#history-chart-wrapper");
const chartEmpty = document.querySelector("#history-chart-empty");
let chartRows = [];

function formatNumber(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function updateFields() {
  const isSma = strategy.value === "SMA";
  document.querySelectorAll(".history-sma-field").forEach((element) => {
    element.classList.toggle("hidden", !isSma);
  });
}

function signalBadge(signal) {
  const signalClass = ["BUY", "CALL"].includes(signal)
    ? "positive"
    : ["SELL", "PUT"].includes(signal)
      ? "negative"
      : "neutral-text";
  return `<strong class="${signalClass}">${signal}</strong>`;
}

function renderSma(rows) {
  head.innerHTML = `<tr>
    <th>Time</th><th>Close</th><th>Signal</th>
    <th>Short SMA</th><th>Long SMA</th>
  </tr>`;
  body.innerHTML = rows
    .map(
      (row) => `<tr>
        <td>${row.time}</td>
        <td>${formatNumber(row.price)}</td>
        <td>${signalBadge(row.signal)}</td>
        <td>${formatNumber(row.short_sma)}</td>
        <td>${formatNumber(row.long_sma)}</td>
      </tr>`,
    )
    .join("");
}

function renderRange(rows) {
  head.innerHTML = `<tr>
    <th>Time</th><th>Close</th><th>Signal</th><th>Prev H</th><th>Prev L</th>
    <th>Call Entry</th><th>Call Target</th><th>Call Stop</th>
    <th>Put Entry</th><th>Put Target</th><th>Put Stop</th>
  </tr>`;
  body.innerHTML = rows
    .map(
      (row) => `<tr>
        <td>${row.time}</td>
        <td>${formatNumber(row.price)}</td>
        <td>${signalBadge(row.signal)}</td>
        <td>${formatNumber(row.previous_high)}</td>
        <td>${formatNumber(row.previous_low)}</td>
        <td>${formatNumber(row.call_entry)}</td>
        <td>${formatNumber(row.call_target)}</td>
        <td>${formatNumber(row.call_stop)}</td>
        <td>${formatNumber(row.put_entry)}</td>
        <td>${formatNumber(row.put_target)}</td>
        <td>${formatNumber(row.put_stop)}</td>
      </tr>`,
    )
    .join("");
}

function drawCandlestickChart(rows) {
  chartRows = rows;
  if (!rows.length) {
    chartWrapper.classList.add("hidden");
    chartEmpty.classList.remove("hidden");
    return;
  }

  chartWrapper.classList.remove("hidden");
  chartEmpty.classList.add("hidden");

  const pixelRatio = window.devicePixelRatio || 1;
  const width = Math.max(chartWrapper.clientWidth, 320);
  const height = 460;
  chart.width = width * pixelRatio;
  chart.height = height * pixelRatio;
  chart.style.width = `${width}px`;
  chart.style.height = `${height}px`;

  const context = chart.getContext("2d");
  context.scale(pixelRatio, pixelRatio);
  context.clearRect(0, 0, width, height);

  const padding = { top: 30, right: 70, bottom: 45, left: 16 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const minPrice = Math.min(...rows.map((row) => row.low));
  const maxPrice = Math.max(...rows.map((row) => row.high));
  const priceRange = Math.max(maxPrice - minPrice, 0.0001);
  const pricePadding = priceRange * 0.08;
  const chartMin = minPrice - pricePadding;
  const chartMax = maxPrice + pricePadding;
  const candleStep = plotWidth / rows.length;
  const candleWidth = Math.max(2, Math.min(10, candleStep * 0.62));

  const yForPrice = (price) =>
    padding.top +
    ((chartMax - price) / (chartMax - chartMin)) * plotHeight;

  context.strokeStyle = "#202a3a";
  context.fillStyle = "#94a3b8";
  context.font = "11px system-ui";
  context.textAlign = "left";
  for (let index = 0; index <= 5; index += 1) {
    const y = padding.top + (plotHeight / 5) * index;
    const price = chartMax - ((chartMax - chartMin) / 5) * index;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillText(
      formatNumber(price),
      width - padding.right + 8,
      y + 4,
    );
  }

  rows.forEach((row, index) => {
    const x = padding.left + candleStep * index + candleStep / 2;
    const bullish = row.close >= row.open;
    const color = bullish ? "#34d399" : "#fb7185";
    const openY = yForPrice(row.open);
    const closeY = yForPrice(row.close);
    const highY = yForPrice(row.high);
    const lowY = yForPrice(row.low);

    context.strokeStyle = color;
    context.fillStyle = color;
    context.beginPath();
    context.moveTo(x, highY);
    context.lineTo(x, lowY);
    context.stroke();
    context.fillRect(
      x - candleWidth / 2,
      Math.min(openY, closeY),
      candleWidth,
      Math.max(Math.abs(closeY - openY), 1),
    );

    if (!["HOLD", "WAIT"].includes(row.signal)) {
      const positiveSignal = ["BUY", "CALL"].includes(row.signal);
      const markerY = positiveSignal ? lowY + 13 : highY - 13;
      context.fillStyle = positiveSignal ? "#22c55e" : "#f43f5e";
      context.beginPath();
      if (positiveSignal) {
        context.moveTo(x, markerY - 5);
        context.lineTo(x - 5, markerY + 4);
        context.lineTo(x + 5, markerY + 4);
      } else {
        context.moveTo(x, markerY + 5);
        context.lineTo(x - 5, markerY - 4);
        context.lineTo(x + 5, markerY - 4);
      }
      context.closePath();
      context.fill();

      context.font = "bold 10px system-ui";
      context.textAlign = "center";
      context.fillText(
        row.signal,
        x,
        positiveSignal ? markerY + 17 : markerY - 10,
      );
    }
  });

  context.fillStyle = "#64748b";
  context.font = "10px system-ui";
  context.textAlign = "center";
  const labelEvery = Math.max(1, Math.ceil(rows.length / 6));
  rows.forEach((row, index) => {
    if (index % labelEvery !== 0 && index !== rows.length - 1) return;
    const x = padding.left + candleStep * index + candleStep / 2;
    context.fillText(shortTime(row.time), x, height - 16);
  });
}

function shortTime(value) {
  const text = String(value);
  if (text.length >= 17) return `${text.slice(4, 8)} ${text.slice(9, 14)}`;
  return text;
}

async function loadHistory(event) {
  event.preventDefault();
  loadButton.disabled = true;
  statusBadge.textContent = "Loading...";

  try {
    const data = await request("/api/strategy/history", {
      method: "POST",
      body: JSON.stringify({
        strategy_type: strategy.value,
        symbol: symbol.value.trim().toUpperCase(),
        short_window: Number(shortWindow.value),
        long_window: Number(longWindow.value),
        limit: Number(limit.value),
      }),
    });

    title.textContent = `${data.symbol} - ${
      data.strategy_type === "SMA" ? "SMA Crossover" : "Previous 4H Range"
    }`;
    count.textContent = `${data.rows.length} rows`;
    statusBadge.textContent = `${data.bar_count} bars loaded`;

    if (!data.rows.length) {
      head.innerHTML = "";
      body.innerHTML =
        '<tr class="empty-row"><td>No signals were calculated.</td></tr>';
      drawCandlestickChart([]);
    } else if (data.strategy_type === "SMA") {
      renderSma(data.rows);
      drawCandlestickChart(data.rows);
    } else {
      renderRange(data.rows);
      drawCandlestickChart(data.rows);
    }
  } catch (error) {
    statusBadge.textContent = "Error";
    head.innerHTML = "";
    body.innerHTML = `<tr class="empty-row"><td>${error.message}</td></tr>`;
    drawCandlestickChart([]);
  } finally {
    loadButton.disabled = false;
  }
}

strategy.addEventListener("change", updateFields);
form.addEventListener("submit", loadHistory);
window.addEventListener("resize", () => {
  if (chartRows.length) drawCandlestickChart(chartRows);
});
updateFields();
