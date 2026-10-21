const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

function fmt(value) {
  return value === null || value === undefined ? '—' : nf.format(value);
}

function valueCell(value, suffix = '') {
  if (value === null || value === undefined) return '<td class="na">—</td>';
  const cls = value < 0 ? 'neg' : '';
  return `<td class="${cls}">${fmt(value)}${suffix}</td>`;
}

function sparkline(values) {
  const points = values.map((v, i) => [i, v]).filter(([, v]) => v !== null && v !== undefined);
  if (points.length < 2) return '';
  const w = 76;
  const h = 20;
  const pad = 2;
  const ys = points.map(([, v]) => v);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const span = max - min || 1;
  const x = (i) => pad + (w - 2 * pad) * (i / (values.length - 1));
  const y = (v) => h - pad - (h - 2 * pad) * ((v - min) / span);
  const d = points.map(([i, v], k) => `${k ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const [li, lv] = points[points.length - 1];
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Trend">` +
    `<path d="${d}"/><circle cx="${x(li).toFixed(1)}" cy="${y(lv).toFixed(1)}" r="1.7"/></svg>`;
}

function renderTable(target, columns, rows, options = {}) {
  const { spark = false, suffix = '', totals = false, emptyRows = false } = options;
  const head = `<tr><th scope="col">Line item</th>${spark ? '<th scope="col" class="spark-head">Trend</th>' : ''}` +
    columns.map((c) => `<th scope="col">${esc(c)}</th>`).join('') + '</tr>';
  const body = rows.map((row, idx) => {
    const isTotal = totals && isTotalItem(row.item);
    const startsSection = isTotal && idx > 0;
    const cls = [isTotal ? 'total' : '', startsSection ? 'section-start' : '', emptyRows && row.values.every((v) => v === null) ? 'empty' : '']
      .filter(Boolean).join(' ');
    const cells = row.values.map((v) => valueCell(v, suffix)).join('');
    return `<tr class="${cls}"><th scope="row" title="${esc(row.item)}">${esc(row.item)}</th>` +
      `${spark ? `<td class="spark">${sparkline(row.values.slice(0, -1))}</td>` : ''}${cells}</tr>`;
  }).join('');
  target.innerHTML = `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

const TOTAL_ITEMS = new Set([
  'Gross Profit', 'Operating Income (Loss)', 'EBIT', 'EBITDA', 'EBITA',
  'Pretax Income', 'Income (Loss) from Cont Ops', 'Income (Loss) Incl. MI',
  'Net Income, GAAP', 'Net Income Avail to Common, GAAP',
  'Equity Before Minority Interest', 'Free Cash Flow', 'Free Cash Flow to Firm',
  'Free Cash Flow to Equity', 'Cash from Operating Activities',
  'Cash from Investing Activities', 'Cash from Financing Activities',
]);

function isTotalItem(item) {
  return item.startsWith('Total ') || TOTAL_ITEMS.has(item);
}

function renderStats() {
  const { overview, capital_structure, company } = DATA;
  const col = overview.columns.length - 1;
  const row = (name) => overview.rows.find((r) => r.item === name)?.values[col] ?? null;
  const shares = capital_structure.rows.find((r) => r.item === 'Shares Outstanding')?.values.at(-1) ?? null;
  const cards = [
    { label: 'Revenue (TTM)', value: row('Sales/Revenue/Turnover'), sub: '$ millions' },
    { label: 'Net income (TTM)', value: row('Net Income, GAAP'), sub: '$ millions' },
    { label: 'Free cash flow / share', value: row('Free Cash Flow per Basic Share'), sub: 'TTM' },
    { label: 'Total equity (TTM)', value: row('Total Equity'), sub: '$ millions' },
    { label: 'Shares outstanding', value: shares, sub: 'millions, Jun 2026' },
    { label: 'Employees', value: company.employees, sub: 'full time' },
  ];
  $('#stats').innerHTML = cards.map((c) => {
    const neg = c.value !== null && c.value < 0;
    return `<div class="stat"><div class="value ${neg ? 'neg' : ''}">${fmt(c.value)}</div>` +
      `<div class="label">${esc(c.label)}</div><div class="subvalue">${esc(c.sub)}</div></div>`;
  }).join('');
}

function renderHeader() {
  const c = DATA.company;
  $('#company-name').textContent = c.name;
  $('#company-sector').textContent = c.sector;
  $('#company-industry').textContent = c.industry;
  $('#price').textContent = c.price === null ? '—' : `$${c.price.toFixed(2)}`;
  const change = c.price_change ?? 0;
  const changeEl = $('#change');
  changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}`;
  changeEl.className = `chg ${change >= 0 ? 'up' : 'down'}`;
  $('#mcap').textContent = c.market_cap_millions === null
    ? 'Market cap —'
    : `Market cap $${(c.market_cap_millions / 1000).toFixed(2)}B`;
  $('#captured').textContent = DATA.meta.captured_at;
  $('#footer-captured').textContent = `Snapshot captured ${DATA.meta.captured_at}`;
  $('#description').textContent = c.description;
  $('#business').textContent = c.business;
  $('#company-facts').innerHTML = [
    ['CEO', c.ceo], ['Employees', fmt(c.employees)], ['IPO date', c.ipo_date],
    ['CIK', c.cik], ['ISIN', c.isin], ['CUSIP', c.cusip], ['Address', c.address],
  ].map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('') +
    `<dt>Website</dt><dd><a href="${esc(c.website)}" target="_blank" rel="noopener">${esc(c.website.replace(/^https?:\/\//, ''))}</a></dd>`;
}

function renderOverview() {
  renderTable($('#overview-table'), DATA.overview.columns, DATA.overview.rows, { spark: true });
  renderTable($('#capital-table'), DATA.capital_structure.columns, DATA.capital_structure.rows, {});
  renderTable($('#working-table'), DATA.working_capital.columns, DATA.working_capital.rows, {});
  renderTable($('#growth-table'), DATA.growth.columns, DATA.growth.rows, { suffix: '%' });
}

function renderStatements() {
  for (const key of ['income', 'balance', 'cashflow']) {
    const stmt = DATA.statements[key];
    renderTable($(`#${key}-table`), stmt.columns, stmt.rows, { totals: true, emptyRows: true });
  }
  $$('.hide-empty').forEach((cb) => {
    const apply = () => {
      $$('tbody tr.empty', cb.closest('.panel')).forEach((tr) => { tr.hidden = cb.checked; });
    };
    cb.addEventListener('change', apply);
    apply();
  });
}

function renderQuarterly() {
  const config = [
    ['q-revenue', DATA.quarterly.revenue, 'Revenue'],
    ['q-eps', DATA.quarterly.eps, 'EPS'],
    ['q-dps', DATA.quarterly.dps, 'Dividend per share'],
  ];
  for (const [id, blob, label] of config) {
    const years = [...new Set(blob.rows.map((r) => r.year))].sort();
    const quarters = ['Q1', 'Q2', 'Q3', 'Q4', 'FY'];
    const rows = years.map((year) => {
      const values = quarters.map((q) => blob.rows.find((r) => r.year === year && r.quarter === q)?.value ?? null);
      return { item: String(year), values };
    });
    renderTable($(`#${id}`), quarters, rows, {});
  }
}

function renderNews() {
  $('#news-list').innerHTML = DATA.news.map((n) =>
    `<li><span class="date">${esc(n.published)}</span><span class="src">${esc(n.source)}</span>` +
    `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></li>`
  ).join('');
}

function renderDatabase() {
  const stats = [
    ['Facts', DB_STATS.facts],
    ['Companies', DB_STATS.companies],
    ['News items', DB_STATS.news],
    ['Datasets', DB_STATS.datasets],
  ];
  $('#db-stats').innerHTML = stats.map(([label, value]) =>
    `<div class="db-stat"><div class="value">${fmt(value)}</div><div class="label">${esc(label)}</div></div>`
  ).join('');

  const sqlUrl = URL.createObjectURL(new Blob([SQL_DUMP], { type: 'application/sql' }));
  $('#download-sql').href = sqlUrl;
  const jsonUrl = URL.createObjectURL(new Blob([JSON.stringify(DATA, null, 2)], { type: 'application/json' }));
  $('#download-json').href = jsonUrl;
}

function setupTabs() {
  const tabs = $$('.tab');
  const activate = (name, push = true) => {
    if (!DATA || !$(`#panel-${name}`)) name = 'overview';
    tabs.forEach((tab) => {
      const on = tab.dataset.panel === name;
      tab.classList.toggle('active', on);
      tab.setAttribute('aria-selected', String(on));
    });
    $$('.panel').forEach((panel) => { panel.hidden = panel.id !== `panel-${name}`; });
    if (push) { try { history.replaceState(null, '', `#${name}`); } catch (_) { /* file:// */ } }
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => activate(tab.dataset.panel)));
  activate(location.hash.replace('#', '') || 'overview', false);
}

renderHeader();
renderStats();
renderOverview();
renderStatements();
renderQuarterly();
renderNews();
renderDatabase();
setupTabs();
