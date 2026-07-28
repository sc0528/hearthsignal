const DATA_URL = "../analytics-data/snapshots.json";
const fmt = new Intl.NumberFormat("en-US");
let latest;
let previous;
let activeSeries = "uniques";

const el = id => document.getElementById(id);
const total = (group, key) => group && Number.isFinite(group[key]) ? group[key] : null;
const traffic = snapshot => snapshot?.traffic?.available ? snapshot.traffic : null;

function change(current, old) {
  if (current == null || old == null) return { text: "First recorded snapshot", cls: "neutral" };
  const delta = current - old;
  if (delta === 0) return { text: "No change since prior capture", cls: "neutral" };
  return { text: `${delta > 0 ? "↑" : "↓"} ${fmt.format(Math.abs(delta))} since prior capture`, cls: delta < 0 ? "down" : "" };
}

function setMetric(id, value, prior) {
  el(id).textContent = value == null ? "—" : fmt.format(value);
  const delta = change(value, prior);
  const node = el(`${id}-delta`);
  node.textContent = delta.text;
  node.className = delta.cls;
}

function dailySeries() {
  const group = traffic(latest)?.views;
  return group?.views || [];
}

function renderChart() {
  const points = dailySeries();
  if (!points.length) {
    el("chart").innerHTML = '<p class="empty">Traffic history is temporarily unavailable.</p>';
    return;
  }
  const values = points.map(item => item[activeSeries] || 0);
  const width = 760, height = 290, left = 45, right = 18, top = 18, bottom = 42;
  const max = Math.max(...values, 1);
  const x = i => left + (i * (width - left - right) / Math.max(points.length - 1, 1));
  const y = value => top + (height - top - bottom) * (1 - value / max);
  const line = values.map((value, i) => `${i ? "L" : "M"}${x(i)},${y(value)}`).join(" ");
  const area = `${line} L${x(values.length - 1)},${height-bottom} L${x(0)},${height-bottom} Z`;
  const grid = [0,.25,.5,.75,1].map(f => {
    const gy = top + (height-top-bottom) * f;
    return `<line class="grid-line" x1="${left}" y1="${gy}" x2="${width-right}" y2="${gy}"/><text class="axis-label" x="3" y="${gy+4}">${fmt.format(Math.round(max*(1-f)))}</text>`;
  }).join("");
  const labels = points.map((point,i) => i % 2 === 0 || i === points.length-1
    ? `<text class="axis-label" text-anchor="middle" x="${x(i)}" y="${height-16}">${new Date(point.timestamp).toLocaleDateString("en-US",{month:"short",day:"numeric",timeZone:"UTC"})}</text>` : "").join("");
  const dots = values.map((value,i) => `<circle class="series-point" cx="${x(i)}" cy="${y(value)}" r="4"><title>${fmt.format(value)}</title></circle>`).join("");
  el("chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">${grid}<path class="series-area" d="${area}"/><path class="series-line" d="${line}"/>${dots}${labels}</svg>`;
}

function insight(icon, title, copy, confidence = "MEDIUM") {
  return `<div class="insight"><span class="insight-icon">${icon}</span><div><strong>${title}</strong><p>${copy}</p></div><span class="confidence">${confidence}</span></div>`;
}

function renderInsights() {
  const currentTraffic = traffic(latest);
  if (!currentTraffic) {
    el("insights").innerHTML = insight("!", "Traffic needs permission", "Public repository metrics are current, but GitHub withheld visitor and clone data.", "HIGH");
    return;
  }
  const visitors = currentTraffic.views.uniques;
  const cloners = currentTraffic.clones.uniques;
  const stars = latest.repository_metrics.stars;
  const priorVisitors = traffic(previous)?.views?.uniques;
  const direction = priorVisitors == null ? "A baseline is now recorded." : visitors > priorVisitors ? "Discovery moved up since the prior capture." : visitors < priorVisitors ? "Discovery softened since the prior capture." : "Discovery held steady.";
  const conversion = visitors ? cloners / visitors * 100 : 0;
  const issues = latest.repository_metrics.open_issues;
  el("insights").innerHTML =
    insight("↗", visitors ? `${fmt.format(visitors)} people found the repository.` : "Discovery is still at baseline.", direction, priorVisitors == null ? "BASELINE" : "MEDIUM") +
    insight("⌁", `${fmt.format(cloners)} unique cloners show trial intent.`, `${conversion.toFixed(1)} unique clones per 100 unique visitors. Treat this as directional because automation can clone too.`, "MEDIUM") +
    insight("★", `${fmt.format(stars)} stars and ${fmt.format(issues)} open issues.`, stars ? "Stars are the clearest public signal of sustained interest; issues may contain validation feedback." : "The strongest validation signal will be an unsolicited star or feedback issue.", "HIGH");
}

function renderFunnel() {
  const t = traffic(latest);
  const visitors = t?.views?.uniques;
  const cloners = t?.clones?.uniques;
  const stars = latest.repository_metrics.stars;
  const steps = [["Visitors", visitors],["Cloners",cloners],["Stars",stars]];
  el("funnel").innerHTML = steps.map(([label,value], i) => {
    const rate = i && steps[i-1][1] ? `${(value / steps[i-1][1] * 100).toFixed(1)}% of prior step` : "rolling 14-day signal";
    return `<div class="funnel-step"><div><span>${label}</span><strong>${value == null ? "—" : fmt.format(value)}</strong></div><span>${rate}</span></div>`;
  }).join("");
}

function renderTable(id, rows, labelKey) {
  el(id).innerHTML = rows?.length ? rows.slice(0,6).map(row =>
    `<tr><td title="${row[labelKey]}">${row[labelKey]}</td><td>${fmt.format(row.count)}</td><td>${fmt.format(row.uniques)}</td></tr>`
  ).join("") : '<tr><td colspan="3" class="empty">No data available</td></tr>';
}

function renderQuality() {
  const available = latest.traffic.available;
  el("quality").innerHTML = `
    <p class="quality-state ${available ? "" : "warning"}">${available ? "✓ Complete traffic capture" : "△ Public metrics only"}</p>
    <p>GitHub exposes repository traffic as a rolling 14-day window. A daily capture preserves a longer directional history without implying precision the source does not provide.</p>
    <p>${available ? "Visitors and views are people-facing discovery signals. Clones can include CI, bots, and maintainer testing." : latest.traffic.errors.join(" · ") || "Traffic details were unavailable."}</p>`;
}

function render(data) {
  const snapshots = data.snapshots || [];
  latest = snapshots.at(-1);
  previous = snapshots.at(-2);
  if (!latest) throw new Error("No snapshots");
  const t = traffic(latest), p = traffic(previous);
  setMetric("visitors", total(t?.views,"uniques"), total(p?.views,"uniques"));
  setMetric("views", total(t?.views,"count"), total(p?.views,"count"));
  setMetric("cloners", total(t?.clones,"uniques"), total(p?.clones,"uniques"));
  setMetric("stars", latest.repository_metrics.stars, previous?.repository_metrics?.stars);
  el("updated").textContent = `Last captured ${new Date(latest.captured_at).toLocaleString("en-US",{dateStyle:"medium",timeStyle:"short",timeZone:"UTC"})} UTC`;
  renderChart(); renderInsights(); renderFunnel();
  renderTable("paths", t?.popular_paths, "path");
  renderTable("referrers", t?.referrers, "referrer");
  renderQuality();
}

document.querySelectorAll("[data-series]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-series]").forEach(item => item.classList.remove("active"));
  button.classList.add("active"); activeSeries = button.dataset.series; renderChart();
}));

fetch(DATA_URL, { cache: "no-store" })
  .then(response => { if (!response.ok) throw new Error(response.statusText); return response.json(); })
  .then(render)
  .catch(() => {
    document.querySelector("main").innerHTML = '<section class="panel"><h1>Product Signal is preparing its first capture.</h1><p class="caption">The daily workflow will publish data here after its first successful run.</p></section>';
    el("updated").textContent = "No capture published yet";
  });
