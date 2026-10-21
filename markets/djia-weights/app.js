(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const COLORS = ['#14324f','#1f8b82','#9460b2','#da8734','#b3372f','#4f7fbf','#7a9a3c','#b06a9e','#6f879e','#c09a3e','#3f6b5a','#8a5a44'];
  const OTHER_COLOR = '#b7c1cf';
  const monthLabel = key => new Date(Date.parse(key + '-01T12:00:00Z')).toLocaleDateString('en-US', {month:'short', year:'numeric', timeZone:'UTC'});
  const dayLabel = key => new Date(Date.parse(key + 'T12:00:00Z')).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric', timeZone:'UTC'});
  const fmtWeight = v => v == null ? '—' : v.toFixed(v >= 10 ? 1 : 2) + '%';
  const fmtPrice = v => v == null ? '—' : '$' + v.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  const fmtIndex = v => v.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const debounce = (fn, wait = 120) => { let t; return () => { clearTimeout(t); t = setTimeout(fn, wait); }; };

  const avgWeights = {};
  for (const [ticker, series] of Object.entries(DATA.weights)) {
    const vals = series.filter(v => v != null);
    avgWeights[ticker] = vals.length ? vals.reduce((a,b) => a + b, 0) / vals.length : 0;
  }
  const byAverage = Object.keys(avgWeights).sort((a,b) => avgWeights[b] - avgWeights[a]);
  const byLatest = DATA.current.map(row => row.ticker);
  const colorTickers = [...new Set([...byAverage.slice(0,10), ...byLatest.slice(0,10)])];
  const colorMap = {};
  colorTickers.forEach((ticker, i) => { colorMap[ticker] = COLORS[i % COLORS.length]; });

  const state = { historyMode: 'average', historyPlot: null, concPlot: null };

  function statistics() {
    const top = DATA.current[0];
    const top10 = DATA.current.slice(0,10).reduce((sum, row) => sum + row.weight, 0);
    $('stats').innerHTML = [
      [fmtIndex(DATA.indexClose), 'Dow close · ' + dayLabel(DATA.asOf)],
      [DATA.impliedDivisor.toFixed(6), 'Dow divisor'],
      [top.ticker + ' ' + fmtWeight(top.weight), 'Largest weight'],
      [top10.toFixed(1) + '%', 'Top 10 share'],
    ].map(([value, label]) => '<div class="stat"><div class="value">' + value + '</div><div class="label">' + esc(label) + '</div></div>').join('');
  }

  function renderCurrent() {
    const max = DATA.current[0].weight;
    $('current-rows').innerHTML = DATA.current.map((row, i) =>
      '<tr><td class="num">' + (i + 1) + '</td>' +
      '<td><span class="ticker">' + esc(row.ticker) + '</span><span class="company">' + esc(row.name) + '</span></td>' +
      '<td class="num">' + fmtPrice(row.price) + '</td>' +
      '<td class="num">' + fmtWeight(row.weight) + '</td>' +
      '<td class="bar-col"><div class="bar"><i style="width:' + (100 * row.weight / max).toFixed(1) + '%"></i></div></td></tr>'
    ).join('');
    $('current-asof').textContent = 'Close of ' + dayLabel(DATA.asOf) + ' · all 30 members priced · total price sum ' + fmtPrice(DATA.totalPrice) + '.';
    $('current-note').textContent = 'The published divisor since June 29, 2026 is ' + DATA.publishedDivisor.toFixed(11) + '; the current price sum implies ' + DATA.impliedDivisor.toFixed(11) + '.';
  }

  function setupCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return {ctx, width, height};
  }

  function grid(ctx, box, yTicks, yMax, xTicks, xLabel) {
    ctx.save();
    ctx.strokeStyle = '#e8edf3';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#7a8593';
    ctx.font = '11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const value of yTicks) {
      const y = box.y + box.h * (1 - value / yMax);
      ctx.beginPath(); ctx.moveTo(box.x, y); ctx.lineTo(box.x + box.w, y); ctx.stroke();
      ctx.fillText(xLabel(value), box.x - 8, y);
    }
    const visibleTicks = xTicks.filter((tick, i) =>
      i === 0 || i === xTicks.length - 1 || (xTicks[i + 1].pos - tick.pos) * box.w >= 50);
    ctx.textBaseline = 'top';
    for (const tick of visibleTicks) {
      const x = box.x + box.w * tick.pos;
      ctx.textAlign = tick.pos === 0 ? 'left' : (tick.pos === 1 ? 'right' : 'center');
      ctx.beginPath(); ctx.moveTo(x, box.y); ctx.lineTo(x, box.y + box.h); ctx.stroke();
      ctx.fillText(tick.label, x, box.y + box.h + 8);
    }
    ctx.restore();
  }

  function xTicksFor(months) {
    const out = [];
    const firstYear = months[0].slice(0,4);
    const lastYear = months[months.length - 1].slice(0,4);
    months.forEach((key, i) => {
      const year = Number(key.slice(0,4));
      if (key.slice(5,7) === '01' && year % 4 === 0) out.push({pos: i / (months.length - 1), label: String(year)});
    });
    if (!out.some(tick => tick.label === firstYear)) out.unshift({pos: 0, label: firstYear});
    if (!out.some(tick => tick.label === lastYear)) out.push({pos: 1, label: lastYear});
    return out;
  }

  function topForMonth(index) {
    const rows = [];
    for (const [ticker, series] of Object.entries(DATA.weights)) {
      const value = series[index];
      if (value != null) rows.push([ticker, value]);
    }
    rows.sort((a,b) => b[1] - a[1]);
    return rows.slice(0, 5);
  }

  function renderHistory() {
    const canvas = $('history-chart');
    const {ctx, width, height} = setupCanvas(canvas);
    const box = {x: 46, y: 12, w: width - 62, h: height - 38};
    const months = DATA.months;
    const chosen = (state.historyMode === 'latest' ? byLatest : byAverage).slice(0, 10);
    const topSet = new Set(chosen);
    const stacks = [];
    const series = {};
    for (const ticker of chosen) {
      series[ticker] = months.map((_, i) => DATA.weights[ticker]?.[i] ?? 0);
    }
    const others = months.map((_, i) => {
      let sum = 0;
      for (const ticker of chosen) sum += series[ticker][i];
      return Math.max(0, 100 - sum);
    });
    for (const ticker of chosen) stacks.push({label: ticker, color: colorMap[ticker], values: series[ticker]});
    stacks.push({label: 'Others', color: OTHER_COLOR, values: others});
    const cumulative = months.map(() => 0);

    ctx.clearRect(0, 0, width, height);
    grid(ctx, box, [0,20,40,60,80,100], 100, xTicksFor(months), value => value + '%');

    for (const stack of stacks) {
      const topEdge = [];
      const bottomEdge = [];
      for (let i = 0; i < months.length; i++) {
        const x = box.x + box.w * (i / (months.length - 1));
        const y0 = box.y + box.h * (1 - cumulative[i] / 100);
        const next = cumulative[i] + stack.values[i];
        const y1 = box.y + box.h * (1 - next / 100);
        bottomEdge.push([x, y0]);
        topEdge.push([x, y1]);
        cumulative[i] = next;
      }
      ctx.beginPath();
      bottomEdge.forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
      for (let i = topEdge.length - 1; i >= 0; i--) ctx.lineTo(topEdge[i][0], topEdge[i][1]);
      ctx.closePath();
      ctx.fillStyle = stack.color;
      ctx.globalAlpha = stack.label === 'Others' ? 0.75 : 0.92;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 0.6;
      ctx.stroke();
    }

    const latestWeights = {};
    for (const row of DATA.current) latestWeights[row.ticker] = row.weight;
    $('history-legend').innerHTML = stacks.map(stack => {
      const value = state.historyMode === 'latest' ? latestWeights[stack.label] : avgWeights[stack.label];
      const suffix = state.historyMode === 'latest' ? ' now' : ' avg';
      return '<span class="chip"><i style="background:' + stack.color + '"></i>' + esc(stack.label) +
        (stack.label === 'Others' ? '' : ' <span style="color:#929ba7">' + fmtWeight(value) + suffix + '</span>') + '</span>';
    }).join('');

    state.historyPlot = {canvas, box, months, topSet};
  }

  function renderConcentration() {
    const canvas = $('conc-chart');
    const {ctx, width, height} = setupCanvas(canvas);
    const box = {x: 46, y: 12, w: width - 78, h: height - 38};
    const months = DATA.months;
    const yMax = Math.max(60, Math.ceil(Math.max(...DATA.top10) / 20) * 20);
    const effMax = Math.ceil(Math.max(...DATA.effective) / 5) * 5;
    const yTicks = [];
    for (let value = 0; value <= yMax; value += 20) yTicks.push(value);

    ctx.clearRect(0, 0, width, height);
    grid(ctx, box, yTicks, yMax, xTicksFor(months), value => value + '%');

    ctx.save();
    ctx.fillStyle = '#7a8593';
    ctx.font = '11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (let value = 0; value <= effMax; value += 5) {
      const y = box.y + box.h * (1 - value / effMax);
      ctx.fillText(String(value), box.x + box.w + 9, y);
    }
    ctx.restore();

    const plot = (values, color, scale, dash = []) => {
      ctx.save();
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash(dash);
      values.forEach((value, i) => {
        const x = box.x + box.w * (i / (months.length - 1));
        const y = box.y + box.h * (1 - value / scale);
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.stroke();
      ctx.restore();
    };
    plot(DATA.top10, '#14324f', yMax);
    plot(DATA.top5, '#1f8b82', yMax);
    plot(DATA.top1, '#da8734', yMax);
    plot(DATA.effective, '#7a8593', effMax, [5,4]);

    state.concPlot = {canvas, box, months, yMax, effMax};
  }

  function renderEras() {
    $('eras').innerHTML = DATA.snapshots.map(snapshot => {
      const max = Math.max(...snapshot.rows.map(row => row.weight));
      return '<div class="era-card' + (snapshot.date === DATA.asOf ? ' now' : '') + '">' +
        '<h3>' + esc(snapshot.label) + '</h3>' +
        '<p class="meta">' + snapshot.coverage + '/30 priced · ' +
        (snapshot.coverage < 30 ? 'renormalized' : 'full coverage') + '</p>' +
        snapshot.rows.map(row => '<div class="era-row" title="' + esc(row.name) + '">' +
          '<span class="t">' + esc(row.ticker) + '</span>' +
          '<span class="bar"><i style="width:' + (100 * row.weight / max).toFixed(1) + '%"></i></span>' +
          '<span class="w">' + fmtWeight(row.weight) + '</span></div>').join('') +
        '</div>';
    }).join('');
  }

  function renderChanges() {
    $('change-rows').innerHTML = DATA.changes.slice().reverse().map(change => {
      const names = list => list.map(row => '<span class="ticker">' + esc(row.ticker === 'ATTC' ? 'T' : row.ticker) + '</span><span class="who">' + esc(row.name) + '</span>').join('') || '<span class="hint">—</span>';
      return '<tr><td class="date">' + esc(dayLabel(change.date)) + '</td>' +
        '<td>' + names(change.added) + '</td>' +
        '<td>' + names(change.removed) + '</td>' +
        '<td class="note">' + esc(change.note || '') + '</td></tr>';
    }).join('');
  }

  function pointerMonth(event, plot) {
    const rect = plot.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    if (x < plot.box.x || x > plot.box.x + plot.box.w) return null;
    const ratio = (x - plot.box.x) / plot.box.w;
    return clamp(Math.round(ratio * (plot.months.length - 1)), 0, plot.months.length - 1);
  }

  function showTip(tip, event, html) {
    const box = tip.parentElement.getBoundingClientRect();
    tip.innerHTML = html;
    tip.style.display = 'block';
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    tip.style.left = clamp(x + 14, 8, box.width - tw - 8) + 'px';
    tip.style.top = clamp(y - th - 12, 8, box.height - th - 8) + 'px';
  }

  function historyTooltip(event) {
    const plot = state.historyPlot;
    if (!plot) return;
    const index = pointerMonth(event, plot);
    if (index == null) { $('history-tip').style.display = 'none'; return; }
    const month = plot.months[index];
    const rows = topForMonth(index);
    showTip($('history-tip'), event,
      '<b>' + esc(monthLabel(month)) + '</b> · ' + fmtIndex(DATA.index[index]) + ' points' +
      '<div class="hint">' + DATA.coverage[index] + '/30 priced</div>' +
      rows.map(([ticker, value]) => {
        const color = colorMap[ticker] || '#929ba7';
        return '<div class="tip-row"><span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + color + ';margin-right:6px"></i>' + esc(ticker) + '</span><span>' + fmtWeight(value) + '</span></div>';
      }).join(''));
  }

  function concTooltip(event) {
    const plot = state.concPlot;
    if (!plot) return;
    const index = pointerMonth(event, plot);
    if (index == null) { $('conc-tip').style.display = 'none'; return; }
    showTip($('conc-tip'), event,
      '<b>' + esc(monthLabel(plot.months[index])) + '</b>' +
      '<div class="tip-row"><span>Top 10</span><span>' + fmtWeight(DATA.top10[index]) + '</span></div>' +
      '<div class="tip-row"><span>Top 5</span><span>' + fmtWeight(DATA.top5[index]) + '</span></div>' +
      '<div class="tip-row"><span>Top 1</span><span>' + fmtWeight(DATA.top1[index]) + '</span></div>' +
      '<div class="tip-row"><span>Effective N</span><span>' + DATA.effective[index].toFixed(1) + '</span></div>');
  }

  function bindHover(canvas, tip, handler) {
    canvas.addEventListener('pointermove', event => { handler(event); });
    canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
  }

  function renderAll() {
    statistics();
    renderCurrent();
    renderHistory();
    renderConcentration();
    renderEras();
    renderChanges();
  }

  $('history-mode').addEventListener('change', event => {
    state.historyMode = event.target.value;
    renderHistory();
  });
  bindHover($('history-chart'), $('history-tip'), historyTooltip);
  bindHover($('conc-chart'), $('conc-tip'), concTooltip);
  window.addEventListener('resize', debounce(() => { renderHistory(); renderConcentration(); }, 160));
  renderAll();
})();
