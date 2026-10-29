// Horizontal bar charts drawn from the same numbers as the results table (measured, mean of 3 seeds).
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  function el(name, attrs, text) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function bars(id, rows, opts) {
    const host = document.getElementById(id);
    if (!host) return;
    const rowH = 38, left = 210, right = 70, top = 8, W = 760;
    const H = top + rows.length * rowH + 8;
    const svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'chart', role: 'img', 'aria-label': opts.label });
    const max = opts.max || 100, plot = W - left - right;
    rows.forEach((r, i) => {
      const y = top + i * rowH;
      svg.appendChild(el('text', { x: left - 12, y: y + 20, 'text-anchor': 'end' }, r.name));
      svg.appendChild(el('rect', { x: left, y: y + 6, width: plot, height: 16, rx: 3, class: 'track' }));
      const w = Math.max(1.5, plot * r.value / max);
      svg.appendChild(el('rect', { x: left, y: y + 6, width: w, height: 16, rx: 3, class: 'bar ' + (r.cls || '') }));
      svg.appendChild(el('text', { x: left + w + 8, y: y + 20, class: 'val' }, r.value.toFixed(1) + '%'));
    });
    host.appendChild(svg);
  }
  const ROWS = [
    { name: 'No defense', asr: 83.1, util: 100.0, cls: 'base' },
    { name: 'Retrieval-time filter', asr: 46.0, util: 61.4 },
    { name: 'Write-time filter', asr: 45.8, util: 61.4 },
    { name: 'Provenance + risk engine', asr: 3.3, util: 99.9, cls: 'mg' },
    { name: 'MemGuard, no detector', asr: 2.1, util: 98.4, cls: 'mg' },
    { name: 'MemGuard, full', asr: 1.0, util: 88.3, cls: 'mg' }
  ];
  bars('chart-asr', ROWS.map(r => ({ name: r.name, value: r.asr, cls: r.cls })),
    { label: 'Attack success rate by defense, lower is better', max: 100 });
  bars('chart-util', ROWS.map(r => ({ name: r.name, value: r.util, cls: r.cls === 'mg' ? 'mg' : '' })),
    { label: 'Benign task completion by defense, higher is better', max: 100 });

  const KINDS = [
    { name: 'Explicit injection', a: 100, b: 0.0, c: 0.0 },
    { name: 'Jailbreak text', a: 100, b: 74.4, c: 2.0 },
    { name: 'Declarative statement', a: 100, b: 82.8, c: 0.4 },
    { name: 'External share request', a: 100, b: 48.9, c: 0.6 },
    { name: 'Payee account swap', a: 13.0, b: 18.1, c: 1.8 }
  ];
  const host = document.getElementById('chart-kind');
  if (host) {
    const rowH = 54, left = 190, right = 20, top = 6, W = 760, plot = W - left - right;
    const H = top + KINDS.length * rowH + 30;
    const svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'chart', role: 'img', 'aria-label': 'Attack success by poison class for three defenses' });
    KINDS.forEach((k, i) => {
      const y = top + i * rowH;
      svg.appendChild(el('text', { x: left - 12, y: y + 26, 'text-anchor': 'end' }, k.name));
      [['a', 'base'], ['b', ''], ['c', 'mg']].forEach((s, j) => {
        const v = k[s[0]], w = Math.max(1.5, plot * v / 100);
        svg.appendChild(el('rect', { x: left, y: y + 6 + j * 14, width: w, height: 10, rx: 2, class: 'bar ' + s[1] }));
        svg.appendChild(el('text', { x: left + w + 6, y: y + 15 + j * 14, class: 'val', style: 'font-size:11px' }, v.toFixed(1) + '%'));
      });
    });
    const ly = top + KINDS.length * rowH + 14;
    [['No defense', 'base', 0], ['Write-time filter', '', 150], ['MemGuard full', 'mg', 320]].forEach(l => {
      svg.appendChild(el('rect', { x: left + l[2], y: ly - 9, width: 12, height: 12, rx: 2, class: 'bar ' + l[1] }));
      svg.appendChild(el('text', { x: left + l[2] + 18, y: ly + 1 }, l[0]));
    });
    host.appendChild(svg);
  }
})();
