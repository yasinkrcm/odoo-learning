/* Odoo Sales Pulse — vanilla JS dashboard over the public KPI endpoint */
const $ = (id) => document.getElementById(id);

const state = {
  days: 30,
  cfg: {
    url: localStorage.getItem('odoo_url') || 'https://odoo.yasinkaracam.com',
    key: localStorage.getItem('odoo_key') || '',
  },
  timer: null,
};

const fmtMoney = (v, cur) =>
  new Intl.NumberFormat('tr-TR', { style: 'currency', currency: cur || 'TRY',
    maximumFractionDigits: 0 }).format(v);
const fmtNum = (v) => new Intl.NumberFormat('tr-TR').format(v);

async function fetchKpi() {
  const q = new URLSearchParams({
    days: state.days,
    api_key: state.cfg.key,
  });
  const url = `${state.cfg.url.replace(/\/$/, '')}/sales_insights/kpi?${q}`;
  const res = await fetch(url);
  if (res.status === 403) throw new Error('API key geçersiz veya boş.');
  if (!res.ok) throw new Error('Odoo cevabı: ' + res.status);
  return res.json();
}

function setDot(status, text) {
  $('dot').className = 'dot ' + status;
  $('status-text').textContent = text;
}

function render(data) {
  $('error').hidden = true;
  $('skeleton').hidden = true;
  $('content').hidden = false;
  setDot('ok', 'canlı');

  $('company').textContent = data.company;
  $('generated-at').textContent = data.generated_at;

  const k = data.kpi, cur = data.currency;
  const diff = k.prev_amount_total
    ? ((k.amount_total - k.prev_amount_total) / k.prev_amount_total) * 100
    : 0;
  const trend = k.prev_amount_total
    ? `<span class="${diff >= 0 ? 'up' : 'down'}">${diff >= 0 ? '▲' : '▼'} ${Math.abs(diff).toFixed(1)}%</span> önceki dönem`
    : '<span class="muted">önceki dönem verisi yok</span>';

  const cards = [
    ['Toplam Ciro', fmtMoney(k.amount_total, cur), trend],
    ['Sipariş', fmtNum(k.order_count),
      `ortalama ${fmtMoney(k.avg_order, cur)}`],
    ['Ürün Adedi', fmtNum(k.qty_total), `son ${data.days} gün içi`],
    ['Açık Talepler', fmtNum(data.helpdesk.open_tickets),
      data.helpdesk.sla_breached ? `SLA aşımı: ${data.helpdesk.sla_breached}` : 'SLA aşımı yok'],
    ['Stok Uyarısı', fmtNum(data.inventory.stock_alerts),
      `eşik: ${data.inventory.threshold}`],
    ['Vadesi Geçen Alacak', fmtMoney(data.ar_aging.overdue_total, cur),
      `${fmtNum(data.ar_aging.overdue_count)} kalem`],
  ];
  $('kpi-cards').innerHTML = cards.map(([l, v, s]) =>
    `<div class="card"><div class="label">${l}</div><div class="value">${v}</div><div class="sub">${s}</div></div>`
  ).join('');

  renderChart(data.daily, cur);
  renderBarList('top-customers', data.top_customers, cur,
    (x) => x.amount, (x) => fmtMoney(x.amount, cur), 'customers-empty');
  renderBarList('top-products', data.top_products, null,
    (x) => x.qty, (x) => `${fmtNum(x.qty)} adet`, 'products-empty');
  renderArAging(data.ar_aging, cur);
  renderCurrency(data.currency_ticker);
}

function renderArAging(ar, cur) {
  const buckets = [
    ['0-30 gün', ar['0_30']],
    ['31-60 gün', ar['31_60']],
    ['61-90 gün', ar['61_90']],
    ['90+ gün', ar['90_plus']],
  ];
  $('ar-aging').innerHTML = buckets.map(([label, v]) => `
    <li>
      <div class="row"><span class="name">${label}</span>
        <span class="val">${fmtMoney(v, cur)}</span></div>
      <div class="track"><div class="fill" style="width:${Math.min(100, (v / (Math.max(ar.overdue_total, 1))) * 100).toFixed(1)}%"></div></div>
    </li>`).join('');
}

function sparklinePoints(h, w = 120, height = 30) {
  const hist = h && h.length > 1 ? h : [h && h[0] || 0, h && h[0] || 0];
  const min = Math.min(...hist);
  const max = Math.max(...hist);
  const range = max - min || 1;
  return hist.map((v, i) => {
    const x = (i / (hist.length - 1)) * w;
    const y = height - ((v - min) / range) * (height - 3) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

function renderCurrency(items) {
  const el = $('currency');
  el.innerHTML = (items || []).map((it) => {
    const pct = Math.abs(it.change || 0).toFixed(2);
    return `<div class="cur">
      <div class="cur-top"><span>${escapeHtml(it.label)}</span><b>${fmtNum(it.value)} ${escapeHtml(it.currency)}</b></div>
      <svg class="cur-spark" viewBox="0 0 120 30" preserveAspectRatio="none">
        <polyline fill="none" stroke="currentColor" stroke-width="1.5"
          points="${sparklinePoints(it.history)}"></polyline>
      </svg>
      <div class="cur-pct ${it.change < 0 ? 'down' : 'up'}">${it.change < 0 ? '▼' : '▲'} %${pct}</div>
    </div>`;
  }).join('');
}

function renderChart(daily, cur) {
  const el = $('chart');
  $('chart-empty').hidden = daily.length > 0;
  const max = Math.max(...daily.map((d) => d.amount), 1);
  el.innerHTML = daily.map((d) => {
    const h = Math.max(3, Math.round((d.amount / max) * 100));
    return `<div class="bar" style="height:${h}%">
      <div class="tip">${d.date} · ${fmtMoney(d.amount, cur)}</div>
    </div>`;
  }).join('');
}

function renderBarList(id, items, _cur, valOf, fmtVal, emptyId) {
  const list = $(id);
  emptyId && ($(emptyId).hidden = items.length > 0);
  const max = Math.max(...items.map((x) => valOf(x)), 1);
  list.innerHTML = items.map((x) => `
    <li>
      <div class="row">
        <span class="name">${escapeHtml(x.name)}</span>
        <span class="val">${fmtVal(x)}</span>
      </div>
      <div class="track"><div class="fill" data-w="${((valOf(x) / max) * 100).toFixed(1)}"></div></div>
    </li>`).join('');
  requestAnimationFrame(() =>
    list.querySelectorAll('.fill').forEach((f) => (f.style.width = f.dataset.w + '%')));
}

const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function ask() {
  const q = $('ask-input').value.trim();
  const answer = $('ask-answer');
  if (!q) return;
  answer.hidden = false;
  answer.textContent = '…';
  try {
    const query = new URLSearchParams({ q, api_key: state.cfg.key });
    const url = `${state.cfg.url.replace(/\/$/, '')}/sales_insights/ask?${query}`;
    const res = await fetch(url);
    if (res.status === 403) throw new Error('API key geçersiz.');
    if (!res.ok) throw new Error('Odoo cevabı: ' + res.status);
    const data = await res.json();
    answer.textContent = data.answer || '—';
  } catch (err) {
    answer.textContent = err.message;
  }
}

async function load() {
  setDot('', 'bağlanıyor…');
  try {
    render(await fetchKpi());
  } catch (err) {
    $('skeleton').hidden = true;
    $('content').hidden = true;
    setDot('err', 'bağlantı yok');
    const e = $('error');
    e.hidden = false;
    e.textContent = err.message + ' — Ayarlar (⚙) → adres/anahtar kontrol et.';
  }
}

/* settings dialog */
const dlg = $('settings');
$('settings-btn').onclick = () => {
  $('cfg-url').value = state.cfg.url;
  $('cfg-key').value = state.cfg.key;
  dlg.showModal();
};
$('cfg-cancel').onclick = () => dlg.close();
$('cfg-save').onclick = () => {
  state.cfg.url = $('cfg-url').value.trim() || state.cfg.url;
  state.cfg.key = $('cfg-key').value.trim();
  localStorage.setItem('odoo_url', state.cfg.url);
  localStorage.setItem('odoo_key', state.cfg.key);
  dlg.close();
  load();
};

/* range buttons */
$('range').addEventListener('click', (ev) => {
  const btn = ev.target.closest('button[data-days]');
  if (!btn) return;
  document.querySelectorAll('#range button').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  state.days = Number(btn.dataset.days);
  load();
});

$('refresh').onclick = load;

$('ask-btn').onclick = ask;
$('ask-input').addEventListener('keyup', (ev) => {
  if (ev.key === 'Enter') ask();
});

state.timer = setInterval(load, 60000);
load();
