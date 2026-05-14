/* ====================================================
   DCF/VAL — app.js
   Handles all UI interaction, API calls, and charting
   ==================================================== */

'use strict';

/* ── State ─────────────────────────────────────────── */
let currentMarket = 'US';
let fcfChart = null;
let valueChart = null;
let lastResult = null;

/* ── DOM refs ───────────────────────────────────────── */
const sidebar        = document.getElementById('sidebar');
const hamburger      = document.getElementById('hamburger');
const sidebarClose   = document.getElementById('sidebarClose');
const dcfForm        = document.getElementById('dcfForm');
const tickerInput    = document.getElementById('tickerInput');
const tickerSearchBtn= document.getElementById('tickerSearchBtn');
const marketToggle   = document.getElementById('marketToggle');
const popularChips   = document.getElementById('popularChips');
const yearsInput     = document.getElementById('yearsInput');
const yearsDisplay   = document.getElementById('yearsDisplay');
const taxInput       = document.getElementById('taxInput');
const taxDisplay     = document.getElementById('taxDisplay');
const growthRatesContainer = document.getElementById('growthRatesContainer');
const analyzeBtn     = document.getElementById('analyzeBtn');
const analyzeBtnText = document.getElementById('analyzeBtnText');
const btnSpinner     = document.getElementById('btnSpinner');
const stockPreview   = document.getElementById('stockPreview');
const previewName    = document.getElementById('previewName');
const previewPrice   = document.getElementById('previewPrice');
const topbarTitle    = document.getElementById('topbarTitle');

const emptyState   = document.getElementById('emptyState');
const errorState   = document.getElementById('errorState');
const loadingState = document.getElementById('loadingState');
const loadingText  = document.getElementById('loadingText');
const resultsEl    = document.getElementById('results');

/* ── Overlay ────────────────────────────────────────── */
let overlay = document.createElement('div');
overlay.className = 'sidebar-overlay';
document.body.appendChild(overlay);
overlay.addEventListener('click', closeSidebar);

function openSidebar() {
    sidebar.classList.add('open');
    overlay.classList.add('active');
}
function closeSidebar() {
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
}
hamburger.addEventListener('click', openSidebar);
sidebarClose.addEventListener('click', closeSidebar);

/* ── Market toggle ──────────────────────────────────── */
marketToggle.addEventListener('click', (e) => {
    const btn = e.target.closest('.toggle-btn');
    if (!btn) return;
    marketToggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentMarket = btn.dataset.market;
    loadPopularStocks(currentMarket);
    tickerInput.placeholder = currentMarket === 'IN' ? 'e.g. TCS.NS or RELIANCE.NS' : 'e.g. AAPL or MSFT';
});

/* ── Load popular stocks ────────────────────────────── */
async function loadPopularStocks(market) {
    try {
        const res = await fetch(`/popular_stocks?market=${market}`);
        const stocks = await res.json();
        popularChips.innerHTML = '';
        stocks.slice(0, 8).forEach(s => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'chip';
            btn.dataset.ticker = s.ticker;
            btn.textContent = s.ticker.replace('.NS', '').replace('.BO', '');
            btn.title = s.name;
            btn.addEventListener('click', () => selectTicker(s.ticker, s.name));
            popularChips.appendChild(btn);
        });
    } catch (err) {
        console.warn('Could not load popular stocks:', err);
    }
}
loadPopularStocks('US');

function selectTicker(ticker, name) {
    tickerInput.value = ticker;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    const chip = popularChips.querySelector(`[data-ticker="${ticker}"]`);
    if (chip) chip.classList.add('active');
    fetchStockPreview(ticker);
}

/* ── Ticker preview ─────────────────────────────────── */
let previewTimeout = null;
tickerInput.addEventListener('input', () => {
    clearTimeout(previewTimeout);
    const val = tickerInput.value.trim().toUpperCase();
    if (val.length >= 1) {
        previewTimeout = setTimeout(() => fetchStockPreview(val), 600);
    } else {
        stockPreview.style.display = 'none';
    }
});

tickerSearchBtn.addEventListener('click', () => {
    const val = tickerInput.value.trim().toUpperCase();
    if (val) fetchStockPreview(val);
});

async function fetchStockPreview(ticker) {
    if (!ticker) return;
    try {
        const res = await fetch(`/stock_info/${ticker}`);
        const data = await res.json();
        if (data.stock_info && data.stock_info.name) {
            const info = data.stock_info;
            previewName.textContent = info.name;
            const price = info.current_price;
            previewPrice.textContent = price ? formatPrice(price, ticker) : '—';
            stockPreview.style.display = 'flex';
        } else {
            stockPreview.style.display = 'none';
        }
    } catch {
        stockPreview.style.display = 'none';
    }
}

/* ── Projection years ───────────────────────────────── */
yearsInput.addEventListener('input', () => {
    yearsDisplay.textContent = yearsInput.value;
    buildGrowthRateInputs(parseInt(yearsInput.value));
});

function buildGrowthRateInputs(years) {
    // Preserve existing values
    const existing = [];
    growthRatesContainer.querySelectorAll('.growth-input').forEach(i => {
        existing.push(parseFloat(i.value) || 10);
    });
    growthRatesContainer.innerHTML = '';
    for (let i = 0; i < years; i++) {
        const defaultVal = existing[i] !== undefined ? existing[i] : (i < 3 ? 15 : i < 6 ? 10 : 5);
        const row = document.createElement('div');
        row.className = 'growth-rate-row';
        row.innerHTML = `
            <span class="growth-year-label">Yr ${i + 1}</span>
            <input type="number" class="growth-input" value="${defaultVal}" min="-50" max="100" step="0.5">
            <span class="growth-unit">%</span>
        `;
        growthRatesContainer.appendChild(row);
    }
}
buildGrowthRateInputs(5);

/* ── Tax rate slider ────────────────────────────────── */
taxInput.addEventListener('input', () => {
    taxDisplay.textContent = taxInput.value + '%';
});

/* ── Quick analyze (called from empty state) ─────────── */
function quickAnalyze(ticker) {
    tickerInput.value = ticker;
    fetchStockPreview(ticker);
    dcfForm.requestSubmit();
}

/* ── Form submit ────────────────────────────────────── */
dcfForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const ticker = tickerInput.value.trim().toUpperCase();
    if (!ticker) {
        alert('Please enter a ticker symbol.');
        return;
    }

    const growthInputs = growthRatesContainer.querySelectorAll('.growth-input');
    const growthRates = Array.from(growthInputs).map(i => parseFloat(i.value) / 100 || 0.10);

    const payload = {
        ticker,
        growth_rates: growthRates,
        tax_rate: parseFloat(taxInput.value) / 100,
        years: parseInt(yearsInput.value)
    };

    setLoading(true, 'Fetching financial data...');
    showState('loading');
    closeSidebar();

    try {
        setTimeout(() => setLoadingText('Calculating WACC & projections...'), 1200);
        setTimeout(() => setLoadingText('Discounting cash flows...'), 2400);

        const res = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (data.error) {
            showError('Analysis Failed', data.error);
        } else {
            lastResult = data;
            renderResults(data);
        }
    } catch (err) {
        showError('Network Error', 'Could not connect to the server. Please ensure the application is running.');
    } finally {
        setLoading(false);
    }
});

/* ── Loading helpers ────────────────────────────────── */
function setLoading(on, text) {
    if (on) {
        analyzeBtn.disabled = true;
        analyzeBtnText.style.display = 'none';
        btnSpinner.style.display = 'block';
    } else {
        analyzeBtn.disabled = false;
        analyzeBtnText.style.display = 'block';
        btnSpinner.style.display = 'none';
    }
}

function setLoadingText(text) {
    loadingText.textContent = text;
}

function showState(state) {
    emptyState.style.display    = 'none';
    errorState.style.display    = 'none';
    loadingState.style.display  = 'none';
    resultsEl.style.display     = 'none';

    if (state === 'empty')   emptyState.style.display   = 'flex';
    if (state === 'error')   errorState.style.display   = 'flex';
    if (state === 'loading') loadingState.style.display = 'flex';
    if (state === 'results') resultsEl.style.display    = 'flex';
}

function showError(title, message) {
    document.getElementById('errorTitle').textContent = title;
    document.getElementById('errorMessage').textContent = message;
    showState('error');
}

/* ── Render results ─────────────────────────────────── */
function renderResults(data) {
    const info = data.stock_info || {};
    const ticker = data.ticker || '';
    const isIndian = ticker.endsWith('.NS') || ticker.endsWith('.BO');
    const currency = isIndian ? '₹' : '$';

    // Topbar
    topbarTitle.textContent = ticker;

    // Header
    document.getElementById('resTicker').textContent = ticker;
    document.getElementById('resName').textContent   = data.stock_name || info.name || ticker;
    document.getElementById('resSector').textContent = info.sector || 'Equity';
    document.getElementById('resCurrentPrice').textContent = formatPrice(data.current_price || info.current_price, ticker);
    document.getElementById('resFairValue').textContent    = formatPrice(data.fair_value_per_share, ticker);

    // Recommendation
    const upside = data.upside_percentage;
    const rec    = data.recommendation || '—';
    const recColor = data.recommendation_color || 'warning';
    const banner = document.getElementById('recommendationBanner');
    const recVal = document.getElementById('recValue');
    const recUp  = document.getElementById('recUpside');

    recVal.textContent = rec;
    recVal.className   = `rec-value rec-${recColor}`;
    recUp.textContent  = upside !== undefined ? (upside >= 0 ? '+' : '') + upside.toFixed(1) + '%' : '—';
    recUp.className    = `rec-upside-value rec-${recColor}`;
    banner.className   = `recommendation-banner banner-${recColor}`;

    // Key metrics
    document.getElementById('mWacc').textContent      = pct(data.wacc);
    document.getElementById('mEV').textContent        = formatLarge(data.enterprise_value, currency);
    document.getElementById('mEquity').textContent    = formatLarge(data.equity_value, currency);
    document.getElementById('mTV').textContent        = formatLarge(data.pv_terminal_value, currency);
    document.getElementById('mPVFCF').textContent     = formatLarge(data.pv_projected_fcf, currency);
    document.getElementById('mMarketCap').textContent = formatLarge(data.market_cap || info.market_cap, currency);

    // Charts
    renderFCFChart(data.projected_fcf || [], currency);
    renderValueChart(data.pv_projected_fcf, data.pv_terminal_value, currency);

    // Projection table
    renderProjectionTable(data.projected_fcf || [], currency);

    // Fundamentals
    document.getElementById('iBeta').textContent   = num(info.beta, 2);
    document.getElementById('iPE').textContent     = num(info.pe_ratio, 1) + 'x';
    document.getElementById('iPB').textContent     = num(info.pb_ratio, 2) + 'x';
    document.getElementById('iDiv').textContent    = info.dividend_yield ? pct(info.dividend_yield) : '—';
    document.getElementById('iROE').textContent    = info.return_on_equity ? pct(info.return_on_equity) : '—';
    document.getElementById('iMargin').textContent = info.profit_margin ? pct(info.profit_margin) : '—';
    document.getElementById('iDE').textContent     = num(info.debt_to_equity, 2);
    document.getElementById('iShares').textContent = formatLarge(info.shares_outstanding || data.shares_outstanding, '');

    // Assumptions
    document.getElementById('aTax').textContent    = pct(parseFloat(taxInput.value) / 100);
    document.getElementById('aNetDebt').textContent= formatLarge(data.net_debt, currency);
    document.getElementById('aFCF').textContent    = formatLarge(
        data.projected_fcf && data.projected_fcf[0]
            ? data.projected_fcf[0].Free_Cash_Flow / (1 + (data.projected_fcf[0].Growth_Rate || 0.1))
            : 0,
        currency
    );

    showState('results');
}

/* ── Charts ─────────────────────────────────────────── */
const chartDefaults = {
    plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: '#161820',
            borderColor: '#1e2128',
            borderWidth: 1,
            titleColor: '#c8f55a',
            bodyColor: '#9ca3af',
            padding: 12,
        }
    },
    scales: {
        x: {
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: { color: '#6b7280', font: { family: 'DM Mono', size: 11 } },
            border: { color: '#1e2128' }
        },
        y: {
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: { color: '#6b7280', font: { family: 'DM Mono', size: 11 } },
            border: { color: '#1e2128' }
        }
    }
};

function renderFCFChart(projectedFCF, currency) {
    const ctx = document.getElementById('fcfChart').getContext('2d');
    if (fcfChart) fcfChart.destroy();

    const labels = projectedFCF.map(r => `Yr ${r.Year}`);
    const values = projectedFCF.map(r => r.Free_Cash_Flow / 1e9);

    fcfChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: 'rgba(200,245,90,0.2)',
                borderColor: '#c8f55a',
                borderWidth: 2,
                borderRadius: 4,
                hoverBackgroundColor: 'rgba(200,245,90,0.35)',
            }]
        },
        options: {
            ...chartDefaults,
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                ...chartDefaults.plugins,
                tooltip: {
                    ...chartDefaults.plugins.tooltip,
                    callbacks: {
                        label: (ctx) => ` ${currency}${ctx.parsed.y.toFixed(2)}B`
                    }
                }
            },
            scales: {
                ...chartDefaults.scales,
                y: {
                    ...chartDefaults.scales.y,
                    ticks: {
                        ...chartDefaults.scales.y.ticks,
                        callback: v => `${currency}${v.toFixed(1)}B`
                    }
                }
            }
        }
    });
}

function renderValueChart(pvFCF, pvTV, currency) {
    const ctx = document.getElementById('valueChart').getContext('2d');
    if (valueChart) valueChart.destroy();

    valueChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['PV of FCFs', 'Terminal Value (PV)'],
            datasets: [{
                data: [pvFCF / 1e9, pvTV / 1e9],
                backgroundColor: ['rgba(200,245,90,0.75)', 'rgba(200,245,90,0.2)'],
                borderColor: ['#c8f55a', 'rgba(200,245,90,0.4)'],
                borderWidth: 2,
                hoverOffset: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '68%',
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: '#6b7280',
                        font: { family: 'DM Mono', size: 11 },
                        padding: 16,
                        boxWidth: 12,
                        boxHeight: 12,
                    }
                },
                tooltip: {
                    ...chartDefaults.plugins.tooltip,
                    callbacks: {
                        label: (ctx) => ` ${currency}${ctx.parsed.toFixed(2)}B`
                    }
                }
            }
        }
    });
}

/* ── Projection table ───────────────────────────────── */
function renderProjectionTable(projected, currency) {
    const tbody = document.getElementById('projectionBody');
    tbody.innerHTML = '';

    if (!projected.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px;">No projection data</td></tr>';
        return;
    }

    projected.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><span class="year-badge">${row.Year}</span></td>
            <td>${pct(row.Growth_Rate)}</td>
            <td>${formatLarge(row.Free_Cash_Flow, currency)}</td>
            <td>${row.Discount_Factor !== undefined ? row.Discount_Factor.toFixed(4) : '—'}</td>
            <td>${row.Present_Value !== undefined ? formatLarge(row.Present_Value, currency) : '—'}</td>
        `;
        tbody.appendChild(tr);
    });
}

/* ── Formatters ─────────────────────────────────────── */
function formatPrice(val, ticker) {
    if (val === undefined || val === null || isNaN(val)) return '—';
    const isIndian = ticker && (ticker.endsWith('.NS') || ticker.endsWith('.BO'));
    const sym = isIndian ? '₹' : '$';
    if (val >= 1000) return sym + val.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    return sym + val.toFixed(2);
}

function formatLarge(val, currency) {
    if (val === undefined || val === null || isNaN(val)) return '—';
    const abs = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    if (abs >= 1e12) return sign + currency + (abs / 1e12).toFixed(2) + 'T';
    if (abs >= 1e9)  return sign + currency + (abs / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6)  return sign + currency + (abs / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3)  return sign + currency + (abs / 1e3).toFixed(1) + 'K';
    return sign + currency + abs.toFixed(0);
}

function pct(val) {
    if (val === undefined || val === null || isNaN(val)) return '—';
    return (val * 100).toFixed(1) + '%';
}

function num(val, decimals = 2) {
    if (val === undefined || val === null || isNaN(val)) return '—';
    return parseFloat(val).toFixed(decimals);
}
