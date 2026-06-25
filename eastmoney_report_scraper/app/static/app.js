const $ = (id) => document.getElementById(id);
const levelRank = { STRONG: 0, HOT: 1, WATCH: 2 };
const filterIds = [
  "globalStartDate", "globalEndDate", "companyFilter", "industryFilter", "brokerFilter",
  "ratingFilter", "hotspotFilter", "priorityFilter", "themeFilter", "reasonFilter",
  "minScoreFilter", "globalSearch"
];
let reportPage = 1;
let fetchTuningTouched = false;
let analysisData = { reports: [], hotspots: [], entityDrilldowns: [], opinionTrends: [], meta: {} };
let aiSettings = { hasToken: false, maskedToken: "", baseUrl: "", model: "", apiFormat: "auto", timeout: 60 };
let aiTemplatePromptDirty = false;
let latestHealth = null;
let latestRuns = { items: [] };
let filtersInitialized = false;
const api = async (path, options = {}) => {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
};
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
const split = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
function setStatus(message, kind = "") {
  const el = $("status");
  el.className = `status ${kind}`.trim();
  el.textContent = message;
}
function setTopBusy(busy) {
  $("importBtn").disabled = busy;
  $("refreshBtn").disabled = busy;
}
function formatImported(imported) {
  const safe = imported || {};
  return `研报 ${safe.reports || 0}，热点 ${safe.hotspots || 0}，覆盖历史 ${safe.coverage_history || 0}，manifest ${safe.manifests || 0}`;
}
function pill(value) {
  const lower = String(value || "").toLowerCase();
  const cls = lower === "done" || lower === "ok" ? "good"
    : lower === "failed" || lower === "error" ? "bad"
    : lower === "strong" ? "strong"
    : lower === "hot" ? "hot"
    : lower === "watch" ? "watch"
    : lower === "a" ? "a"
    : lower === "b" ? "b"
    : lower === "up" ? "up"
    : lower === "down" ? "down"
    : lower === "flat" ? "flat"
    : "";
  return `<span class="pill ${cls}">${esc(value || "-")}</span>`;
}
function numberField(row, names) {
  for (const name of names) {
    const raw = row && row[name];
    if (raw === undefined || raw === null || raw === "") continue;
    const value = Number(raw);
    if (Number.isFinite(value)) return value;
  }
  return 0;
}
function reasonCodes(row) {
  const raw = row ? row.reasonCodes || row.reason_codes || "" : "";
  if (Array.isArray(raw)) return raw.filter(Boolean);
  return String(raw).split(/[|,;，、]/).map((item) => item.trim()).filter(Boolean);
}
function reasonLabel(code) {
  const labels = {
    FIRST_COVERAGE: "首次覆盖",
    REACTIVATED_COVERAGE: "重新覆盖",
    MULTI_BROKER: "多券商",
    COVERAGE_ACCELERATION: "覆盖加速",
    INDUSTRY_RESONANCE: "行业共振",
    HIGH_BUY_RATIO: "高买入率",
  };
  return labels[code] || code;
}
function uniq(values) {
  return [...new Set((values || []).filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b, "zh-CN"));
}
function optionList(values, label) {
  return [`<option value="">全部${label}</option>`, ...values.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`)].join("");
}
function setSelectOptions(id, values, label) {
  const el = $(id);
  const current = el.value;
  const options = uniq(values);
  el.innerHTML = optionList(options, label);
  if (current && options.includes(current)) el.value = current;
}
function allReports() {
  return (analysisData && analysisData.reports) || [];
}
function allHotspots() {
  return (analysisData && analysisData.hotspots) || [];
}
function allEntities() {
  return (analysisData && analysisData.entityDrilldowns) || [];
}
function dashboardDates() {
  return uniq(allReports().map((row) => row.date));
}
function populateGlobalFilters() {
  const reports = allReports();
  const hotspots = allHotspots();
  const dates = dashboardDates();
  if (dates.length && (!filtersInitialized || (!$("globalStartDate").value && !$("globalEndDate").value))) {
    $("globalStartDate").value = dates[0];
    $("globalEndDate").value = dates[dates.length - 1];
  }
  setSelectOptions("companyFilter", [
    ...reports.map((row) => row.stockName || row.stockCode),
    ...hotspots.filter((row) => row.entityType === "company").map((row) => row.entityName),
  ], "公司");
  setSelectOptions("industryFilter", [
    ...reports.map((row) => row.industryName),
    ...hotspots.map((row) => row.industryName || (row.entityType === "industry" ? row.entityName : "")),
  ], "行业");
  setSelectOptions("brokerFilter", reports.map((row) => row.orgName), "券商");
  setSelectOptions("ratingFilter", reports.map((row) => row.rating), "评级");
  setSelectOptions("hotspotFilter", hotspots.map((row) => row.hotspotLevel), "热点");
  setSelectOptions("priorityFilter", reports.map((row) => row.priorityBucket), "优先级");
  setSelectOptions("themeFilter", reports.flatMap((row) => row.themeTags || []), "主题");
  setSelectOptions("reasonFilter", hotspots.flatMap((row) => reasonCodes(row)), "原因");
  filtersInitialized = true;
}
function readFilters() {
  return {
    startDate: $("globalStartDate").value,
    endDate: $("globalEndDate").value,
    company: $("companyFilter").value,
    industry: $("industryFilter").value,
    broker: $("brokerFilter").value,
    rating: $("ratingFilter").value,
    hotspot: $("hotspotFilter").value,
    priority: $("priorityFilter").value,
    theme: $("themeFilter").value,
    reason: $("reasonFilter").value,
    minScore: Number($("minScoreFilter").value || 0),
    search: $("globalSearch").value.trim().toLowerCase(),
  };
}
function inDate(date, filters) {
  if (!date) return true;
  if (filters.startDate && date < filters.startDate) return false;
  if (filters.endDate && date > filters.endDate) return false;
  return true;
}
function includesText(row, text) {
  if (!text) return true;
  const haystack = [
    row.stockName, row.stockCode, row.industryName, row.title, row.orgName, row.rating, row.summary,
    ...(row.themeTags || []), ...(row.scoreReasons || []), ...(row.reasonCodes || []), ...(row.reasons || [])
  ].join(" ").toLowerCase();
  return haystack.includes(text);
}
function entityKeyForReport(row) {
  const entities = allEntities();
  const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
  if (company) return company.entityKey;
  const industry = entities.find((entity) => entity.entityType === "industry" && entity.label === row.industryName);
  return industry ? industry.entityKey : "";
}
function entityKeysForReport(row) {
  const entities = allEntities();
  const keys = [];
  const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
  const industry = entities.find((entity) => entity.entityType === "industry" && entity.label === row.industryName);
  if (company) keys.push(company.entityKey);
  if (industry) keys.push(industry.entityKey);
  return keys;
}
function entityKeyForHotspot(row) {
  const entities = allEntities();
  const company = entities.find((entity) => entity.entityType === "company" && row.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.entityName));
  if (company) return company.entityKey;
  const industry = entities.find((entity) => entity.entityType === "industry" && (entity.label === row.entityName || entity.label === row.industryName));
  return industry ? industry.entityKey : "";
}
function entityKeyForOpinion(row) {
  const entities = allEntities();
  const company = entities.find((entity) => entity.entityType === "company" && ((row.stockCode && entity.stockCode === row.stockCode) || entity.label === row.stockName));
  if (company) return company.entityKey;
  const industry = entities.find((entity) => entity.entityType === "industry" && (entity.label === row.industryName || entity.label === row.stockName));
  return industry ? industry.entityKey : "";
}
function reportMatches(row, filters) {
  if (!inDate(row.date, filters)) return false;
  if (!includesText(row, filters.search)) return false;
  if (filters.company && row.stockName !== filters.company && row.stockCode !== filters.company) return false;
  if (filters.industry && row.industryName !== filters.industry) return false;
  if (filters.broker && row.orgName !== filters.broker) return false;
  if (filters.rating && row.rating !== filters.rating) return false;
  if (filters.priority && row.priorityBucket !== filters.priority) return false;
  if (filters.theme && !(row.themeTags || []).includes(filters.theme)) return false;
  if (Number(row.signalScore || 0) < filters.minScore) return false;
  if (filters.hotspot || filters.reason) {
    const keys = new Set(entityKeysForReport(row));
    const matchedHotspot = allHotspots().some((hotspot) => {
      const key = entityKeyForHotspot(hotspot);
      return key && keys.has(key)
        && (!filters.hotspot || hotspot.hotspotLevel === filters.hotspot)
        && (!filters.reason || reasonCodes(hotspot).includes(filters.reason));
    });
    if (!matchedHotspot) return false;
  }
  return true;
}
function hotspotMatches(row, filters, reportKeys) {
  const directText = !filters.search || includesText(row, filters.search);
  if (!inDate(row.latestPublishDate || row.latestDate, filters)) return false;
  if (!directText) return false;
  if (filters.company && row.entityName !== filters.company && row.stockCode !== filters.company) return false;
  if (filters.industry && row.industryName !== filters.industry && row.entityName !== filters.industry) return false;
  if (filters.hotspot && row.hotspotLevel !== filters.hotspot) return false;
  if (filters.reason && !reasonCodes(row).includes(filters.reason)) return false;
  const needsReportContext = Boolean(filters.broker || filters.rating || filters.priority || filters.theme || filters.minScore);
  if (needsReportContext) {
    const key = entityKeyForHotspot(row);
    if (!key || !reportKeys.has(key)) return false;
  }
  return true;
}
function opinionMatches(row, filters, reportKeys) {
  const haystack = [row.stockName, row.stockCode, row.industryName, row.orgName, row.ratingChange, row.latestRating, row.previousRating].join(" ").toLowerCase();
  if (!inDate(row.latestDate, filters)) return false;
  if (filters.search && !haystack.includes(filters.search)) return false;
  if (filters.company && row.stockName !== filters.company && row.stockCode !== filters.company) return false;
  if (filters.industry && row.industryName !== filters.industry) return false;
  if (filters.broker && row.orgName !== filters.broker) return false;
  const needsReportContext = Boolean(filters.rating || filters.priority || filters.theme || filters.hotspot || filters.reason || filters.minScore);
  if (needsReportContext) {
    const key = entityKeyForOpinion(row);
    if (!key || !reportKeys.has(key)) return false;
  }
  return true;
}
function filteredDashboardData() {
  const filters = readFilters();
  const reports = allReports().filter((row) => reportMatches(row, filters));
  const reportKeys = new Set(reports.flatMap((row) => entityKeysForReport(row)));
  const hotspots = allHotspots().filter((row) => hotspotMatches(row, filters, reportKeys));
  const opinions = ((analysisData && analysisData.opinionTrends) || []).filter((row) => opinionMatches(row, filters, reportKeys));
  return { filters, reports, hotspots, opinions, reportKeys };
}
function countUnique(rows, getter) {
  return new Set((rows || []).map(getter).filter(Boolean)).size;
}
function countBy(rows, getter, limit = 12) {
  const counter = {};
  (rows || []).forEach((row) => {
    const value = getter(row);
    if (!value) return;
    counter[value] = (counter[value] || 0) + 1;
  });
  return Object.keys(counter).map((name) => ({ name, count: counter[name] })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN")).slice(0, limit);
}
function countTokens(rows, getter, limit = 12) {
  const counter = {};
  (rows || []).forEach((row) => (getter(row) || []).forEach((value) => {
    if (!value) return;
    counter[value] = (counter[value] || 0) + 1;
  }));
  return Object.keys(counter).map((name) => ({ name, count: counter[name] })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN")).slice(0, limit);
}
function seriesByDay(rows, getDate, getKey) {
  const grouped = {};
  (rows || []).forEach((row) => {
    const date = getDate(row);
    if (!date) return;
    if (!grouped[date]) grouped[date] = new Set();
    grouped[date].add(getKey ? getKey(row) : `${date}-${grouped[date].size}`);
  });
  return Object.keys(grouped).sort().map((date) => ({ name: date.slice(5), date, count: grouped[date].size }));
}
function renderKpis(reports, hotspots) {
  const weak = reports.filter((row) => row.status === "weak" || row.status === "error").length;
  const ab = reports.filter((row) => ["A", "B"].includes(row.priorityBucket)).length;
  const strong = hotspots.filter((row) => row.hotspotLevel === "STRONG" || row.hotspotLevel === "HOT").length;
  $("kpis").innerHTML = [
    ["研报", reports.length, "筛选后样本"],
    ["公司", countUnique(reports, (row) => row.stockCode || row.stockName), "覆盖标的"],
    ["行业", countUnique(reports, (row) => row.industryName), "覆盖行业"],
    ["券商", countUnique(reports, (row) => row.orgName), "参与机构"],
    ["热点", hotspots.length, `HOT/STRONG ${strong}`],
    ["A/B", ab, "优先级样本"],
    ["弱/错", weak, "数据质量"],
    ["历史", analysisData.coverageHistoryCount || 0, "coverage rows"],
  ].map(([label, value, sub]) => `<div class="kpi"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
}
function renderRadar(hotspots, reports) {
  const items = [...(hotspots || [])].sort((a, b) => (levelRank[a.hotspotLevel] ?? 9) - (levelRank[b.hotspotLevel] ?? 9) || Number(b.coverage30d || 0) - Number(a.coverage30d || 0));
  const strongCount = items.filter((item) => String(item.hotspotLevel || "").toUpperCase() === "STRONG").length;
  const multiBroker = items.filter((item) => numberField(item, ["brokerCount30d", "brokerCount", "orgCount30d"]) >= 2).length;
  const firstCoverage = items.filter((item) => reasonCodes(item).includes("FIRST_COVERAGE")).length;
  const coverageTotal = items.reduce((sum, item) => sum + numberField(item, ["coverage30d", "reportCount30d", "coverageCount30d"]), 0);
  $("radarUpdated").textContent = `刷新 ${new Date().toLocaleTimeString()}`;
  $("radarMetrics").innerHTML = [
    ["热点信号", items.length, "当前列表"],
    ["强热点", strongCount, "STRONG"],
    ["多券商共振", multiBroker, "30日内 >= 2家"],
    ["首次覆盖", firstCoverage, `覆盖合计 ${coverageTotal} / 研报 ${reports.length}`],
  ].map(([label, value, sub]) => `<div class="radar-metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
  if (!items.length) {
    $("radarList").innerHTML = `<div class="radar-item"><div class="muted">暂无热点信号。可先导入已有输出，或完成一次抓取。</div></div>`;
    $("radarFocus").innerHTML = `<div class="muted">导入或刷新后显示当前最值得关注的信号。</div>`;
    return;
  }
  $("radarList").innerHTML = items.slice(0, 6).map((item) => {
    const level = String(item.hotspotLevel || "").toUpperCase();
    const codes = reasonCodes(item).slice(0, 4);
    const cls = level === "STRONG" ? "strong" : numberField(item, ["brokerCount30d", "brokerCount"]) >= 2 ? "watch" : "";
    const entityKey = entityKeyForHotspot(item);
    return `<div class="radar-item ${cls}">
      <div class="radar-item-head">
        <div>
          <div class="radar-name">${esc(item.entityName || item.stockName || "-")}</div>
          <div class="radar-meta">${esc(item.industryName || item.entityType || "-")} · ${esc(item.latestPublishDate || item.latestDate || "")}</div>
        </div>
        ${pill(item.hotspotLevel || "-")}
      </div>
      <div class="radar-stats">
        <span>覆盖 ${numberField(item, ["coverage30d", "reportCount30d", "coverageCount30d"])}</span>
        <span>券商 ${numberField(item, ["brokerCount30d", "brokerCount", "orgCount30d"])}</span>
        <span>公司 ${numberField(item, ["coveredCompanyCount30d", "coveredCompanyCount"])}</span>
      </div>
      <div class="reason-list">${codes.map((code) => `<span class="pill">${esc(reasonLabel(code))}</span>`).join("") || '<span class="pill">关注</span>'}</div>
      ${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : ""}
    </div>`;
  }).join("");
  const top = items[0];
  $("radarFocus").innerHTML = `<div class="eyebrow">当前焦点</div>
    <div class="name">${esc(top.entityName || top.stockName || "-")}</div>
    <div class="radar-meta">${esc(top.industryName || "-")} · ${esc(top.latestPublishDate || top.latestDate || "")}</div>
    <div class="radar-stats">
      <span>30日覆盖 ${numberField(top, ["coverage30d", "reportCount30d", "coverageCount30d"])}</span>
      <span>券商 ${numberField(top, ["brokerCount30d", "brokerCount", "orgCount30d"])}</span>
    </div>
    <div class="reason-list">${reasonCodes(top).slice(0, 5).map((code) => `<span class="pill">${esc(reasonLabel(code))}</span>`).join("") || '<span class="pill">关注</span>'}</div>`;
}
function rowsWithDateNames(rows) {
  return (rows || []).map((row) => ({ name: row.name || String(row.date || "").slice(5), count: Number(row.count || 0) }));
}
function emptyChart(id, text = "暂无数据") {
  $(id).innerHTML = `<div class="empty">${esc(text)}</div>`;
}
function formatChartNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value || "-");
  if (Number.isInteger(number)) return String(number);
  return String(Math.round(number * 100) / 100);
}
function singlePointChart(id, row, color) {
  $(id).innerHTML = `<div class="single-point">
    <div class="value">${esc(formatChartNumber(row.count))}</div>
    <div class="label">${esc(row.name || "单点记录")}</div>
    <span class="dot" style="background:${color}"></span>
  </div>`;
}
function drawLine(id, rows, color = "var(--blue)") {
  const el = $(id);
  const data = rowsWithDateNames(rows).filter((row) => Number.isFinite(row.count));
  if (!data.length) { emptyChart(id); return; }
  if (data.length === 1) { singlePointChart(id, data[0], color); return; }
  const max = Math.max(...data.map((row) => row.count), 1);
  const min = Math.min(...data.map((row) => row.count), 0);
  const spread = Math.max(max - min, 1);
  const step = data.length > 1 ? 560 / (data.length - 1) : 0;
  const points = data.map((row, index) => `${50 + index * step},${168 - ((row.count - min) / spread) * 116}`).join(" ");
  el.innerHTML = `<svg viewBox="0 0 640 220" width="100%" height="100%" role="img">
    <line x1="50" y1="180" x2="610" y2="180" stroke="#d9d3c6"></line>
    <line x1="50" y1="38" x2="50" y2="180" stroke="#d9d3c6"></line>
    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
    ${data.map((row, index) => {
      const x = 50 + index * step;
      const y = 168 - ((row.count - min) / spread) * 116;
      const label = data.length <= 8 || index % Math.ceil(data.length / 8) === 0 ? `<text x="${x}" y="207" text-anchor="middle" font-size="13" fill="#65717d">${esc(row.name)}</text>` : "";
      const value = data.length <= 12 || index % Math.ceil(data.length / 12) === 0 ? `<text x="${x}" y="${y - 11}" text-anchor="middle" font-size="13" fill="#33404a">${esc(formatChartNumber(row.count))}</text>` : "";
      return `<circle cx="${x}" cy="${y}" r="5" fill="${color}"><title>${esc(row.name)}: ${esc(formatChartNumber(row.count))}</title></circle>${value}${label}`;
    }).join("")}
  </svg>`;
}
function drawBar(id, rows, color = "var(--teal)") {
  const data = (rows || []).filter((row) => row.name && Number(row.count || 0) > 0).slice(0, 10);
  if (!data.length) { emptyChart(id); return; }
  const max = Math.max(...data.map((row) => Number(row.count || 0)), 1);
  $(id).innerHTML = `<svg viewBox="0 0 640 210" width="100%" height="100%" role="img">
    ${data.map((row, index) => {
      const width = Math.max(4, (Number(row.count || 0) / max) * 410);
      const y = 14 + index * Math.max(18, 180 / data.length);
      return `<g><text x="0" y="${y + 12}" font-size="13" fill="#65717d">${esc(String(row.name).slice(0, 12))}</text><rect x="142" y="${y}" width="${width}" height="14" rx="4" fill="${color}"></rect><text x="${152 + width}" y="${y + 12}" font-size="13" fill="#33404a">${esc(formatChartNumber(row.count))}</text></g>`;
    }).join("")}
  </svg>`;
}
function reportMatchesEntity(row, entity) {
  if (!entity) return false;
  if (entity.entityType === "company") {
    return (entity.stockCode && row.stockCode === entity.stockCode) || row.stockName === entity.label;
  }
  return row.industryName === entity.label || row.industryName === entity.industryName;
}
function directionSummary(summary) {
  const safe = summary || {};
  return `上修 ${safe.up || 0} / 下修 ${safe.down || 0} / 持平 ${safe.flat || 0}`;
}
function selectedAnalysisEntity() {
  const entities = filteredAnalysisEntities();
  const selectedKey = $("analysisEntity").value;
  return entities.find((entity) => entity.entityKey === selectedKey) || entities[0] || null;
}
function entityMatchesFilters(entity, filters) {
  const text = [entity.label, entity.stockCode, entity.industryName, entity.entityType, ...(entity.reasonCodes || [])].join(" ").toLowerCase();
  return (!filters.search || text.includes(filters.search))
    && (!filters.company || entity.label === filters.company || entity.stockCode === filters.company)
    && (!filters.industry || entity.industryName === filters.industry || entity.label === filters.industry)
    && (!filters.hotspot || entity.hotspotLevel === filters.hotspot)
    && (!filters.reason || (entity.reasonCodes || []).includes(filters.reason));
}
function filteredAnalysisEntities() {
  const entities = allEntities();
  const filters = readFilters();
  const query = $("analysisSearch").value.trim().toLowerCase();
  return entities.filter((entity) => {
    const text = [entity.label, entity.stockCode, entity.industryName, entity.entityType, ...(entity.reasonCodes || [])].join(" ").toLowerCase();
    return entityMatchesFilters(entity, filters) && (!query || text.includes(query));
  });
}
function renderAnalysisOptions() {
  const allEntities = (analysisData && analysisData.entityDrilldowns) || [];
  const entities = filteredAnalysisEntities();
  const current = $("analysisEntity").value;
  if (!allEntities.length) {
    $("analysisEntity").innerHTML = `<option value="">暂无可分析对象</option>`;
    return;
  }
  if (!entities.length) {
    $("analysisEntity").innerHTML = `<option value="">无匹配对象</option>`;
    return;
  }
  $("analysisEntity").innerHTML = entities.map((entity) => {
    const type = entity.entityType === "company" ? "公司" : "行业";
    return `<option value="${esc(entity.entityKey)}">${type}｜${esc(entity.label)}（${entity.reportCount || 0}篇 / ${entity.brokerCount || 0}家）</option>`;
  }).join("");
  if (current && entities.some((entity) => entity.entityKey === current)) {
    $("analysisEntity").value = current;
  }
}
function renderAnalysisLatestReports(entity) {
  const reports = (entity.latestReports || []).slice(0, 12);
  if (!reports.length) {
    $("analysisLatestReports").innerHTML = `<tbody><tr><td><div class="empty">暂无最新研报</div></td></tr></tbody>`;
    return;
  }
  $("analysisLatestReports").innerHTML = `<thead><tr><th>日期</th><th>券商</th><th>评级</th><th>分数</th><th>主题</th><th>摘要</th><th>文件</th></tr></thead><tbody>${reports.map((row) => `<tr>
    <td>${esc(row.date)}</td>
    <td>${esc(row.orgName)}</td>
    <td>${esc(row.rating || "-")}</td>
    <td>${pill(row.priorityBucket)} ${esc(row.signalScore)}</td>
    <td><div class="tags">${(row.themeTags || []).slice(0, 4).map((tag) => `<span class="pill">${esc(tag)}</span>`).join("")}</div></td>
    <td class="summary">${esc(row.summary || row.title || "")}</td>
    <td>${row.fileHref ? `<a href="/preview/${esc(row.fileHref)}">${esc(row.file || "预览")}</a>` : `<span class="muted">-</span>`}</td>
  </tr>`).join("")}</tbody>`;
}
function renderAnalysis() {
  const entity = selectedAnalysisEntity();
  if (!entity) {
    $("analysisKpis").innerHTML = `<div class="empty">暂无分析数据。请先导入已有输出，或完成一次抓取。</div>`;
    ["analysisCoverageChart", "analysisBrokerChart", "analysisScoreChart", "analysisTargetChart", "analysisEpsChart", "analysisRatingChart", "analysisPriorityChart", "analysisBrokerMix", "analysisThemeMix"].forEach((id) => emptyChart(id));
    $("analysisOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无变化记录</div></td></tr></tbody>`;
    $("analysisLatestReports").innerHTML = `<tbody><tr><td><div class="empty">暂无最新研报</div></td></tr></tbody>`;
    return;
  }
  const entityReports = ((analysisData && analysisData.reports) || []).filter((row) => reportMatchesEntity(row, entity));
  const summary = entity.opinionSummary || {};
  const kpis = [
    ["对象", entity.label, entity.entityType === "company" ? entity.stockCode || "公司" : "行业"],
    ["覆盖", entity.reportCount || 0, `${entity.firstDate || "-"} → ${entity.latestDate || "-"}`],
    ["券商", entity.brokerCount || 0, "不同机构"],
    ["均分", entity.avgScore || 0, "signalScore"],
    ["热点", entity.hotspotLevel || "-", (entity.reasonCodes || []).join(" | ") || "无"],
    ["观点变化", summary.trendCount || 0, `目标价 ${directionSummary(summary.target)}；EPS ${directionSummary(summary.eps)}`],
  ];
  $("analysisKpis").innerHTML = kpis.map(([label, value, sub]) => `<div class="analysis-kpi"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
  drawLine("analysisCoverageChart", entity.coverageByDay || [], "var(--blue)");
  drawLine("analysisBrokerChart", entity.brokerByDay || [], "var(--teal)");
  drawLine("analysisScoreChart", entity.scoreByDay || [], "#15803d");
  drawLine("analysisTargetChart", entity.targetTimeline || [], "#b45309");
  drawLine("analysisEpsChart", entity.epsTimeline || [], "var(--rose)");
  drawBar("analysisRatingChart", entity.ratingDistribution || [], "var(--blue)");
  drawBar("analysisPriorityChart", countBy(entityReports, (row) => row.priorityBucket || "未评级"), "#15803d");
  drawBar("analysisBrokerMix", entity.topBrokers || [], "var(--teal)");
  drawBar("analysisThemeMix", entity.topThemes || [], "#b45309");

  const trends = entity.opinionTrends || [];
  if (!trends.length) {
    $("analysisOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无同一机构连续观点，评级/目标价/EPS 变化暂不可判断。</div></td></tr></tbody>`;
    renderAnalysisLatestReports(entity);
    return;
  }
  $("analysisOpinionTable").innerHTML = `<thead><tr><th>券商</th><th>日期</th><th>评级变化</th><th>目标价变化</th><th>EPS 变化</th><th>评分变化</th></tr></thead><tbody>${trends.map((row) => `<tr>
    <td>${esc(row.orgName)}</td>
    <td>${esc(row.previousDate)} → ${esc(row.latestDate)}</td>
    <td>${esc(row.previousRating || "-")} → ${esc(row.latestRating || "-")}<div class="muted">${esc(row.ratingChange || "")}</div></td>
    <td>${esc(row.previousTargetPrice || "-")} → ${esc(row.latestTargetPrice || "-")} ${pill(row.targetDirection)}</td>
    <td>${esc(row.previousEps || "-")} → ${esc(row.latestEps || "-")} ${pill(row.epsDirection)}</td>
    <td>${row.previousScore} → ${row.latestScore} ${pill(row.scoreDirection)}</td>
  </tr>`).join("")}</tbody>`;
  renderAnalysisLatestReports(entity);
}
function renderRuns(runs) {
  const rows = (runs && runs.items) || [];
  if (!rows.length) {
    $("runs").innerHTML = `<tbody><tr><td><div class="empty">暂无任务</div></td></tr></tbody>`;
    return;
  }
  $("runs").innerHTML = `<thead><tr><th>ID</th><th>状态</th><th>开始</th><th>结束</th><th>OK/W/E</th><th>错误</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(String(r.run_id).slice(0, 8))}</td><td>${pill(r.status)}</td><td>${esc(r.started_at)}</td><td>${esc(r.ended_at || "")}</td><td>${r.ok_count}/${r.weak_count}/${r.error_count}</td><td>${esc(r.error_text || "")}</td></tr>`).join("")}</tbody>`;
}
function renderOverviewCharts(reports, hotspots) {
  drawLine("reportTrendChart", seriesByDay(reports, (row) => row.date), "var(--blue)");
  drawLine("brokerTrendChart", seriesByDay(reports, (row) => row.date, (row) => row.orgName), "var(--teal)");
  drawBar("industryHeatChart", countBy(reports, (row) => row.industryName, 10), "var(--amber)");
  drawBar("themeHeatChart", countTokens(reports, (row) => row.themeTags, 10), "var(--teal)");
  drawBar("reasonTrendChart", countTokens(hotspots, (row) => reasonCodes(row), 10), "var(--rose)");
  drawBar("qualityChart", countBy(reports, (row) => row.status || "unknown", 8), "#15803d");
  drawBar("sourceChart", countBy(reports, (row) => row.source || "unknown", 8), "var(--blue)");
}
function renderHotspotsTable(rows) {
  const limited = [...(rows || [])].sort((a, b) => (levelRank[a.hotspotLevel] ?? 9) - (levelRank[b.hotspotLevel] ?? 9) || Number(b.coverage30d || 0) - Number(a.coverage30d || 0)).slice(0, 120);
  if (!limited.length) {
    $("hotspots").innerHTML = `<tbody><tr><td><div class="empty">暂无热点信号</div></td></tr></tbody>`;
    return;
  }
  $("hotspots").innerHTML = `<thead><tr><th>标的</th><th>等级</th><th>行业</th><th>30日/7日</th><th>券商</th><th>加速</th><th>买入比</th><th>原因</th><th>操作</th></tr></thead><tbody>${limited.map((row) => {
    const entityKey = entityKeyForHotspot(row);
    return `<tr>
      <td><strong>${esc(row.entityName)}</strong><div class="muted">${esc(row.stockCode || row.entityType)}</div></td>
      <td>${pill(row.hotspotLevel)}</td>
      <td>${esc(row.industryName)}</td>
      <td>${numberField(row, ["coverage30d"])} / ${numberField(row, ["coverage7d"])}</td>
      <td>${numberField(row, ["brokerCount30d"])}<div class="muted">新增 ${numberField(row, ["newBrokerCount30d"])}</div></td>
      <td>${numberField(row, ["coverageAcceleration"])}</td>
      <td>${Math.round(Number(row.buyRatio || 0) * 100)}%</td>
      <td><div class="tags">${reasonCodes(row).map((code) => `<span class="pill">${esc(reasonLabel(code))}</span>`).join("")}</div><div class="muted">${esc((row.reasons || []).join("；"))}</div></td>
      <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
    </tr>`;
  }).join("")}</tbody>`;
}
function renderGlobalOpinion(rows) {
  const limited = (rows || []).slice(0, 120);
  if (!limited.length) {
    $("globalOpinionTable").innerHTML = `<tbody><tr><td><div class="empty">暂无连续观点记录</div></td></tr></tbody>`;
    return;
  }
  $("globalOpinionTable").innerHTML = `<thead><tr><th>标的</th><th>券商</th><th>日期</th><th>评级</th><th>目标价</th><th>EPS</th><th>分数</th><th>次数</th><th>操作</th></tr></thead><tbody>${limited.map((row) => {
    const entityKey = entityKeyForOpinion(row);
    return `<tr>
      <td><strong>${esc(row.stockName)}</strong><div class="muted">${esc(row.stockCode || row.industryName)}</div></td>
      <td>${esc(row.orgName)}</td>
      <td>${esc(row.previousDate)} → ${esc(row.latestDate)}</td>
      <td>${esc(row.previousRating || "-")} → ${esc(row.latestRating || "-")}<div class="muted">${esc(row.ratingChange || "")}</div></td>
      <td>${esc(row.previousTargetPrice || "-")} → ${esc(row.latestTargetPrice || "-")} ${pill(row.targetDirection)}</td>
      <td>${esc(row.previousEps || "-")} → ${esc(row.latestEps || "-")} ${pill(row.epsDirection)}</td>
      <td>${esc(row.previousScore)} → ${esc(row.latestScore)} ${pill(row.scoreDirection)}</td>
      <td>${esc(row.count)}</td>
      <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
    </tr>`;
  }).join("")}</tbody>`;
}
function reportLimit() {
  return Number($("reportLimit").value || 100);
}
function reportSearchMatches(row) {
  const text = $("reportSearch").value.trim().toLowerCase();
  return includesText(row, text);
}
function renderReportPager(total, shown, offset) {
  const limit = reportLimit();
  if (limit > 0 && total > 0 && shown === 0 && offset >= total) {
    reportPage = Math.max(1, Math.ceil(total / limit));
    renderDashboardViews();
    return;
  }
  if (limit <= 0) {
    $("reportPageInfo").textContent = `全部 ${total} 条`;
    $("reportPrevBtn").disabled = true;
    $("reportNextBtn").disabled = true;
    return;
  }
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.min(totalPages, Math.max(1, reportPage));
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(total, offset + shown);
  $("reportPageInfo").textContent = `${first}-${last} / ${total} · 第 ${currentPage}/${totalPages} 页`;
  $("reportPrevBtn").disabled = currentPage <= 1;
  $("reportNextBtn").disabled = currentPage >= totalPages;
}
function renderReports(rows) {
  const searched = [...(rows || [])].filter(reportSearchMatches).sort((a, b) => String(b.date).localeCompare(String(a.date)) || Number(b.signalScore || 0) - Number(a.signalScore || 0));
  const limit = reportLimit();
  const offset = limit > 0 ? Math.max(0, reportPage - 1) * limit : 0;
  const pageRows = limit > 0 ? searched.slice(offset, offset + limit) : searched;
  renderReportPager(searched.length, pageRows.length, offset);
  if (!pageRows.length) {
    $("reports").innerHTML = `<tbody><tr><td><div class="muted">暂无匹配研报</div></td></tr></tbody>`;
    return;
  }
  $("reports").innerHTML = `<thead><tr><th>日期</th><th>标的</th><th>行业</th><th>券商</th><th>评级</th><th>分数</th><th>主题</th><th>摘要</th><th>质量</th><th>文件</th><th>操作</th></tr></thead><tbody>${pageRows.map((r) => {
    const entityKey = entityKeyForReport(r);
    return `<tr>
      <td>${esc(r.date)}</td>
      <td><strong>${esc(r.stockName || r.industryName)}</strong><div class="muted">${esc(r.stockCode || "")}</div></td>
      <td>${esc(r.industryName)}</td>
      <td>${esc(r.orgName)}</td>
      <td>${esc(r.rating || "-")}</td>
      <td>${pill(r.priorityBucket)} <strong>${esc(r.signalScore || 0)}</strong></td>
      <td><div class="tags">${(r.themeTags || []).slice(0, 5).map((tag) => `<span class="pill">${esc(tag)}</span>`).join("")}</div></td>
      <td class="summary">${esc(r.summary || r.title || "")}</td>
      <td>${esc(r.status || "-")}<div class="muted">${esc(r.source || "-")} / Q ${esc(r.qualityScore || 0)}</div></td>
      <td>${r.fileHref ? `<a href="/preview/${esc(r.fileHref)}">${esc(r.file || "预览")}</a>` : `<span class="muted">-</span>`}</td>
      <td>${entityKey ? `<button type="button" class="link-button" data-entity-key="${esc(entityKey)}">查看</button>` : `<span class="muted">-</span>`}</td>
    </tr>`;
  }).join("")}</tbody>`;
}
function bindEntityButtons() {
  document.querySelectorAll("[data-entity-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.entityKey || "";
      renderAnalysisOptions();
      $("analysisEntity").value = key;
      renderAnalysis();
      const entity = selectedAnalysisEntity();
      if (entity) $("aiQuery").value = entity.label || entity.stockCode || "";
      $("analysisPanel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}
function renderDashboardViews() {
  const { reports, hotspots, opinions } = filteredDashboardData();
  renderRadar(hotspots, reports);
  renderKpis(reports, hotspots);
  renderOverviewCharts(reports, hotspots);
  renderHotspotsTable(hotspots);
  renderGlobalOpinion(opinions);
  renderAnalysisOptions();
  populateAiEntityOptions();
  renderAnalysis();
  renderReports(reports);
  bindEntityButtons();
  const meta = (analysisData && analysisData.meta) || {};
  $("dashboardFooter").textContent = `显示 ${reports.length} 篇研报，${hotspots.length} 条热点信号，索引文件 ${meta.reportIndexCount || 0} 个`;
}
function activeAiProfile() {
  const profiles = aiSettings.profiles || [];
  return profiles.find((profile) => profile.id === aiSettings.activeProfileId) || profiles[0] || aiSettings;
}
function fillAiProfileForm(profile) {
  const safeProfile = profile || {};
  $("aiProfile").value = safeProfile.id || aiSettings.activeProfileId || "default";
  $("aiProfileName").value = safeProfile.name || safeProfile.id || "Default";
  $("aiProvider").value = safeProfile.provider || "openai-compatible";
  $("aiBaseUrl").value = safeProfile.baseUrl || "";
  $("aiApiFormat").value = safeProfile.apiFormat || "auto";
  $("aiModel").value = safeProfile.model || "";
  $("aiTimeout").value = safeProfile.timeout || 60;
  $("aiToken").value = "";
}
function renderAiProfiles() {
  const profiles = aiSettings.profiles || [];
  if (!profiles.length) {
    $("aiProfile").innerHTML = `<option value="default">Default</option>`;
    return;
  }
  $("aiProfile").innerHTML = profiles.map((profile) => {
    const active = profile.id === aiSettings.activeProfileId ? " *" : "";
    return `<option value="${esc(profile.id)}">${esc(profile.name || profile.id)}${active}</option>`;
  }).join("");
}
function renderAiTemplates(settings) {
  const templates = (settings && settings.templates) || [];
  if (!templates.length) return;
  const current = $("aiTemplate").value || "general_research";
  $("aiTemplate").innerHTML = templates.map((template) => (
    `<option value="${esc(template.id)}">${esc(template.name || template.id)}</option>`
  )).join("");
  $("aiTemplate").value = templates.some((template) => template.id === current) ? current : "general_research";
  syncAiTemplatePrompt(true);
}
function selectedAiTemplate() {
  const templates = aiSettings.templates || [];
  return templates.find((template) => template.id === $("aiTemplate").value) || templates[0] || {};
}
function syncAiTemplatePrompt(force = false) {
  const template = selectedAiTemplate();
  if (!template.instruction) return;
  if (force || !aiTemplatePromptDirty) {
    $("aiTemplatePrompt").value = template.instruction || "";
    aiTemplatePromptDirty = false;
  }
}
function toggleAiPromptEditor() {
  const wrap = $("aiTemplatePromptWrap");
  const willShow = wrap.hidden;
  wrap.hidden = !willShow;
  $("aiEditPromptBtn").textContent = willShow ? "隐藏 Prompt" : "编辑 Prompt";
  if (willShow) {
    syncAiTemplatePrompt(false);
    $("aiTemplatePrompt").focus();
  }
}
function resetAiTemplatePrompt() {
  aiTemplatePromptDirty = false;
  syncAiTemplatePrompt(true);
  $("aiTemplatePromptWrap").hidden = false;
  $("aiEditPromptBtn").textContent = "隐藏 Prompt";
  $("aiTemplatePrompt").focus();
}
function populateAiEntityOptions() {
  const el = $("aiEntityKeys");
  if (!el) return;
  const selected = new Set([...el.selectedOptions].map((option) => option.value));
  const entities = allEntities();
  el.innerHTML = entities.map((entity) => {
    const typeLabel = entity.entityType === "company" ? "公司" : "行业";
    const detail = entity.stockCode ? ` / ${entity.stockCode}` : "";
    return `<option value="${esc(entity.entityKey)}">${esc(typeLabel)}：${esc(entity.label || entity.industryName || entity.stockCode)}${esc(detail)}</option>`;
  }).join("");
  [...el.options].forEach((option) => { option.selected = selected.has(option.value); });
  renderAiEntityCheckboxes();
  updateAiEntityDropdownLabel();
  const dates = dashboardDates();
  if (dates.length && !$("aiStartDate").value && !$("aiEndDate").value) {
    $("aiStartDate").value = dates[0];
    $("aiEndDate").value = dates[dates.length - 1];
  }
}
function aiEntityOptionLabel(option) {
  return option ? option.textContent || option.value : "";
}
function selectedAiEntityOptions() {
  return [...$("aiEntityKeys").selectedOptions];
}
function updateAiEntityDropdownLabel() {
  const selected = selectedAiEntityOptions();
  if (!selected.length) {
    $("aiEntityDropdownBtn").textContent = "选择公司 / 行业";
    return;
  }
  const names = selected.slice(0, 2).map(aiEntityOptionLabel).join("，");
  $("aiEntityDropdownBtn").textContent = selected.length > 2 ? `${names} 等 ${selected.length} 个` : names;
}
function renderAiEntityCheckboxes() {
  const select = $("aiEntityKeys");
  const container = $("aiEntityOptions");
  if (!select || !container) return;
  const search = ($("aiEntitySearch").value || "").trim().toLowerCase();
  const options = [...select.options].filter((option) => !search || option.textContent.toLowerCase().includes(search));
  if (!options.length) {
    container.innerHTML = `<div class="multi-select-empty">没有匹配对象</div>`;
    return;
  }
  container.innerHTML = options.map((option) => (
    `<label class="multi-select-option"><input type="checkbox" data-ai-entity-key="${esc(option.value)}" ${option.selected ? "checked" : ""}>${esc(option.textContent)}</label>`
  )).join("");
  container.querySelectorAll("[data-ai-entity-key]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const option = [...select.options].find((item) => item.value === checkbox.dataset.aiEntityKey);
      if (option) option.selected = checkbox.checked;
      updateAiEntityDropdownLabel();
    });
  });
}
function toggleAiEntityMenu(event) {
  if (event) event.stopPropagation();
  const menu = $("aiEntityMenu");
  menu.hidden = !menu.hidden;
  if (!menu.hidden) {
    $("aiEntitySearch").focus();
    renderAiEntityCheckboxes();
  }
}
function closeAiEntityMenu() {
  $("aiEntityMenu").hidden = true;
}
function renderAiSettings(settings) {
  aiSettings = settings || aiSettings;
  renderAiProfiles();
  renderAiTemplates(aiSettings);
  fillAiProfileForm(activeAiProfile());
  populateAiEntityOptions();
  const label = aiSettings.hasToken ? `AI 已配置 ${aiSettings.maskedToken || ""}` : "AI 未配置";
  $("aiSettingsStatus").textContent = label;
  $("aiSettingsStatus").className = `ai-settings-status ${aiSettings.hasToken ? "ready" : ""}`.trim();
}
async function loadAiSettings(options = {}) {
  const silent = Boolean(options.silent);
  try {
    const settings = await api("/api/ai/settings");
    renderAiSettings(settings);
    return true;
  } catch (error) {
    if (!silent) setStatus(`AI 设置读取失败：${error.message}`, "error");
    return false;
  }
}
async function saveAiSettings() {
  const payload = {
    profileId: $("aiProfile").value || "default",
    profileName: $("aiProfileName").value.trim() || $("aiProfile").value || "Default",
    provider: $("aiProvider").value,
    baseUrl: $("aiBaseUrl").value.trim(),
    apiFormat: $("aiApiFormat").value,
    model: $("aiModel").value.trim(),
    apiToken: $("aiToken").value.trim(),
    timeout: Number($("aiTimeout").value || 60),
  };
  $("aiSaveBtn").disabled = true;
  setStatus("正在保存 AI 设置...");
  try {
    const result = await api("/api/ai/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderAiSettings(result.settings || result);
    setStatus("AI 设置已保存", "good");
  } catch (error) {
    setStatus(`AI 设置保存失败：${error.message}`, "error");
  } finally {
    $("aiSaveBtn").disabled = false;
  }
}
async function clearAiToken() {
  const profileId = $("aiProfile").value || "default";
  $("aiClearTokenBtn").disabled = true;
  setStatus("正在清除 AI Token...");
  try {
    const result = await api("/api/ai/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profileId, clearToken: true }),
    });
    renderAiSettings(result.settings || result);
    $("aiToken").value = "";
    $("aiResult").textContent = "当前 Profile 的 API Token 已清除。";
    setStatus("AI Token 已清除", "good");
  } catch (error) {
    setStatus(`AI Token 清除失败：${error.message}`, "error");
  } finally {
    $("aiClearTokenBtn").disabled = false;
  }
}
async function switchAiProfile() {
  const profileId = $("aiProfile").value;
  const profile = (aiSettings.profiles || []).find((item) => item.id === profileId);
  fillAiProfileForm(profile);
  if (!profileId || profileId === aiSettings.activeProfileId) return;
  try {
    const result = await api("/api/ai/profiles/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profileId }),
    });
    renderAiSettings(result.settings || result);
    setStatus(`已切换 AI Profile：${profile ? profile.name || profile.id : profileId}`, "good");
  } catch (error) {
    setStatus(`AI Profile 切换失败：${error.message}`, "error");
  }
}
function newAiProfile() {
  const profileId = `profile-${Date.now()}`;
  aiSettings = {
    ...aiSettings,
    activeProfileId: profileId,
    profiles: [
      ...(aiSettings.profiles || []),
      {
        id: profileId,
        name: "New Profile",
        provider: "openai-compatible",
        baseUrl: "",
        model: "",
        apiFormat: "auto",
        hasToken: false,
        maskedToken: "",
        timeout: 60,
      },
    ],
  };
  renderAiSettings(aiSettings);
  $("aiToken").value = "";
  $("aiProfileName").focus();
}
async function deleteAiProfile() {
  const profileId = $("aiProfile").value;
  if (!profileId || profileId === "default") {
    setStatus("Default Profile 不能删除", "error");
    return;
  }
  $("aiDeleteProfileBtn").disabled = true;
  try {
    const result = await api("/api/ai/profiles/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profileId }),
    });
    renderAiSettings(result.settings || result);
    setStatus("AI Profile 已删除", "good");
  } catch (error) {
    setStatus(`AI Profile 删除失败：${error.message}`, "error");
  } finally {
    $("aiDeleteProfileBtn").disabled = false;
  }
}
async function importCcSwitchSettings() {
  $("aiImportCcSwitchBtn").disabled = true;
  setStatus("正在读取 cc-switch 当前 Claude 配置...");
  try {
    const result = await api("/api/ai/import-cc-switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        overwriteProfileId: $("aiProfile").value || "",
        profileName: $("aiProfileName").value.trim() || "cc-switch",
      }),
    });
    renderAiSettings(result.settings || result);
    const source = result.ccSwitch || {};
    setStatus(`已导入 cc-switch：${source.providerName || "Claude provider"} / ${source.model || ""}`, "good");
  } catch (error) {
    setStatus(`cc-switch 导入失败：${error.message}`, "error");
  } finally {
    $("aiImportCcSwitchBtn").disabled = false;
  }
}
function readAiEntityKeys() {
  return [...$("aiEntityKeys").selectedOptions].map((option) => option.value).filter(Boolean);
}
async function testAiConnection() {
  $("aiTestBtn").disabled = true;
  $("aiResult").textContent = "正在测试 AI 连接...";
  try {
    const result = await api("/api/ai/test-connection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profileId: $("aiProfile").value || "default",
        profileName: $("aiProfileName").value.trim() || $("aiProfile").value || "Default",
        provider: $("aiProvider").value,
        baseUrl: $("aiBaseUrl").value.trim(),
        apiFormat: $("aiApiFormat").value,
        model: $("aiModel").value.trim(),
        apiToken: $("aiToken").value.trim(),
        timeout: Number($("aiTimeout").value || 60),
      }),
    });
    $("aiResult").textContent = JSON.stringify(result, null, 2);
    setStatus(result.ok ? "AI 连接测试成功" : "AI 连接测试失败", result.ok ? "good" : "error");
  } catch (error) {
    $("aiResult").textContent = `AI 连接测试失败：${error.message}`;
    setStatus(`AI 连接测试失败：${error.message}`, "error");
  } finally {
    $("aiTestBtn").disabled = false;
  }
}
function aiEvidenceSummary(evidence) {
  const counts = (evidence && evidence.sampleCounts) || {};
  const summary = (evidence && evidence.selectedScopeSummary) || {};
  const entity = (evidence && evidence.entity) || {};
  const label = entity.label || evidence.query || summary.scope || "当前筛选结果";
  return `${label}：研报 ${counts.reports || 0}，公司 ${summary.companyCount || 0}，行业 ${summary.industryCount || 0}，券商 ${summary.brokerCount || 0}，热点 ${counts.hotspots || 0}，观点变化 ${counts.opinionTrends || 0}`;
}
async function runAiAnalysis() {
  const entity = selectedAnalysisEntity();
  const scope = $("aiScope").value;
  const entityKeys = readAiEntityKeys();
  const query = $("aiQuery").value.trim() || (entity ? entity.label || entity.stockCode || "" : "");
  if (scope === "selected" && !entity && !query) {
    setStatus("请先选择研究对象，或把 AI 分析范围改为关键词/对象。", "error");
    return;
  }
  const payload = {
    scope,
    templateId: $("aiTemplate").value || "general_research",
    templatePrompt: aiTemplatePromptDirty ? $("aiTemplatePrompt").value.trim() : "",
    entityKey: scope === "selected" && entity ? entity.entityKey : (entityKeys[0] || ""),
    entityKeys,
    startDate: $("aiStartDate").value,
    endDate: $("aiEndDate").value,
    query,
    filters: readFilters(),
    instruction: $("aiInstruction").value,
    maxReports: 8,
  };
  $("aiAnalyzeBtn").disabled = true;
  $("aiResult").textContent = "AI 分析中...";
  $("aiEvidenceNote").textContent = "正在整理结构化 evidence...";
  try {
    const result = await api("/api/ai/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("aiEvidenceNote").textContent = aiEvidenceSummary(result.evidence || {});
    if (!result.ok) {
      $("aiResult").textContent = `AI 分析失败：${result.error || "未知错误"}`;
      setStatus("AI 分析失败", "error");
      return;
    }
    $("aiResult").textContent = result.analysis || "";
    setStatus("AI 分析完成", "good");
  } catch (error) {
    $("aiResult").textContent = `AI 分析失败：${error.message}`;
    setStatus(`AI 分析失败：${error.message}`, "error");
  } finally {
    $("aiAnalyzeBtn").disabled = false;
  }
}
async function loadAnalysis(options = {}) {
  const silent = Boolean(options.silent);
  if (!silent) setStatus("分析数据刷新中...");
  try {
    analysisData = await api("/api/dashboard-data");
    populateGlobalFilters();
    renderDashboardViews();
    if (!silent) setStatus(`分析已刷新：${new Date().toLocaleTimeString()}`, "good");
    return true;
  } catch (error) {
    if (!silent) setStatus(`分析刷新失败：${error.message}`, "error");
    return false;
  }
}
async function refresh(options = {}) {
  const silent = Boolean(options.silent);
  if (!silent) setStatus("刷新中...");
  const [health, runs, dashboard] = await Promise.all([
    api("/api/health"), api("/api/runs"), api("/api/dashboard-data")
  ]);
  latestHealth = health;
  latestRuns = runs;
  analysisData = dashboard;
  $("meta").textContent = "";
  populateGlobalFilters();
  renderRuns(latestRuns);
  renderDashboardViews();
  if (!silent) setStatus(`已刷新：${new Date().toLocaleTimeString()}`, "good");
}
async function safeRefresh(options = {}) {
  try {
    await refresh(options);
  } catch (error) {
    setStatus(`刷新失败：${error.message}`, "error");
  }
}
async function importExisting() {
  setTopBusy(true);
  setStatus("正在导入已有输出...");
  try {
    const payload = await api("/api/import-existing", { method: "POST" });
    reportPage = 1;
    await refresh({ silent: true });
    setStatus(`导入完成：${formatImported(payload.imported)}`, "good");
  } catch (error) {
    setStatus(`导入失败：${error.message}`, "error");
  } finally {
    setTopBusy(false);
  }
}
async function refreshAll() {
  await safeRefresh();
}
function resetGlobalFilters() {
  const dates = dashboardDates();
  filterIds.forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.value = "";
  });
  if (dates.length) {
    $("globalStartDate").value = dates[0];
    $("globalEndDate").value = dates[dates.length - 1];
  }
  reportPage = 1;
  renderDashboardViews();
}
$("importBtn").addEventListener("click", importExisting);
$("refreshBtn").addEventListener("click", refreshAll);
$("analysisRefreshBtn").addEventListener("click", () => loadAnalysis());
$("analysisEntity").addEventListener("change", renderAnalysis);
$("analysisSearch").addEventListener("input", () => { renderAnalysisOptions(); renderAnalysis(); });
$("aiProfile").addEventListener("change", switchAiProfile);
$("aiTemplate").addEventListener("change", () => { aiTemplatePromptDirty = false; syncAiTemplatePrompt(true); });
$("aiTemplatePrompt").addEventListener("input", () => { aiTemplatePromptDirty = true; });
$("aiEditPromptBtn").addEventListener("click", toggleAiPromptEditor);
$("aiResetPromptBtn").addEventListener("click", resetAiTemplatePrompt);
$("aiEntityDropdownBtn").addEventListener("click", toggleAiEntityMenu);
$("aiEntitySearch").addEventListener("input", renderAiEntityCheckboxes);
$("aiEntityMenu").addEventListener("click", (event) => event.stopPropagation());
document.addEventListener("click", closeAiEntityMenu);
$("aiNewProfileBtn").addEventListener("click", newAiProfile);
$("aiDeleteProfileBtn").addEventListener("click", deleteAiProfile);
$("aiImportCcSwitchBtn").addEventListener("click", importCcSwitchSettings);
$("aiSaveBtn").addEventListener("click", saveAiSettings);
$("aiClearTokenBtn").addEventListener("click", clearAiToken);
$("aiTestBtn").addEventListener("click", testAiConnection);
$("aiAnalyzeBtn").addEventListener("click", runAiAnalysis);
filterIds.forEach((id) => $(id).addEventListener("input", () => { reportPage = 1; renderDashboardViews(); }));
$("resetFiltersBtn").addEventListener("click", resetGlobalFilters);
$("reportLimit").addEventListener("change", () => { reportPage = 1; renderDashboardViews(); });
$("reportSearchBtn").addEventListener("click", () => { reportPage = 1; renderDashboardViews(); });
$("reportClearBtn").addEventListener("click", () => { $("reportSearch").value = ""; reportPage = 1; renderDashboardViews(); });
$("reportSearch").addEventListener("keydown", (event) => { if (event.key === "Enter") { reportPage = 1; renderDashboardViews(); } });
$("reportPrevBtn").addEventListener("click", () => { reportPage = Math.max(1, reportPage - 1); renderDashboardViews(); });
$("reportNextBtn").addEventListener("click", () => { reportPage += 1; renderDashboardViews(); });
$("concurrency").addEventListener("input", () => { fetchTuningTouched = true; });
$("jitter").addEventListener("input", () => { fetchTuningTouched = true; });
$("qtype").addEventListener("change", () => {
  if (fetchTuningTouched) return;
  if ($("qtype").value === "2") {
    $("concurrency").value = "2";
    $("jitter").value = "0.5";
  } else {
    $("concurrency").value = "1";
    $("jitter").value = "0";
  }
});
$("runBtn").addEventListener("click", async () => {
  const payload = {
    date: $("date").value,
    start_date: $("startDate").value,
    end_date: $("endDate").value,
    qtype: Number($("qtype").value),
    stock: split($("stock").value),
    industry: split($("industry").value),
    org: split($("org").value),
    rating: split($("rating").value),
    limit: $("limit").value ? Number($("limit").value) : null,
    concurrency: Number($("concurrency").value || 1),
    jitter: Number($("jitter").value || 0),
    no_xlsx: true
  };
  $("runBtn").disabled = true;
  setStatus("任务已提交，正在启动...");
  try {
    const run = await api("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    await safeRefresh({ silent: true });
    setStatus(`任务已启动：${String(run.run_id || "").slice(0, 8)}`, "good");
  } catch (error) {
    setStatus(`任务启动失败：${error.message}`, "error");
  } finally {
    $("runBtn").disabled = false;
  }
});
if ($("qtype").value === "2") {
  $("concurrency").value = "2";
  $("jitter").value = "0.5";
}
loadAiSettings({ silent: true });
safeRefresh({ silent: true });
setInterval(() => safeRefresh({ silent: true }), 5000);
