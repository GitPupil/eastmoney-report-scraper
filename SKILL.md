---
name: eastmoney_report_scraper
description: 按日期或日期区间抓取东方财富个股/行业研报，支持筛选、续跑、PDF fallback、结构化分析、评分、交易看板、共识简报、历史覆盖、近期热点识别、离线可视化 Dashboard，以及观点变化/叙事趋势/时间序列/市场联动研究辅助。
metadata:
  {
    "openclaw": {
      "requires": {},
      "install": [
        {
          "id": "html-parser",
          "kind": "python",
          "package": "beautifulsoup4",
          "label": "Install BeautifulSoup for structured HTML parsing"
        },
        {
          "id": "xlsx-export",
          "kind": "python",
          "package": "openpyxl",
          "label": "Install openpyxl for xlsx export"
        }
      ]
    }
  }
---

# 东方财富研报批量采集

这个 skill 用于执行 **东方财富研报中心列表 API → 详情页 HTML → 可选 PDF fallback → 本地研究产物输出** 的 workflow。

它不是新闻检索工具，也不是实时行情工具。遇到“抓研报、整理研报、生成研报摘要/看板/AI 分析输入”这类任务时使用它。

项目也提供可选 Local App，但 OpenClaw/agent 默认仍使用 CLI workflow；除非用户明确要求启动本地 Web App，否则不要使用 `eastmoney-report-scraper app`。

## Entry Policy

这个项目有三种常用入口，必须按场景选择：

| 场景 | 使用入口 | 说明 |
|---|---|---|
| OpenClaw / Codex / agent 自动执行 | `python3 {baseDir}/scripts/fetch_reports.py ...` | 默认入口。用于抓取、续跑、重算热点、生成 Markdown/CSV/JSONL 和静态 `DASHBOARD.html`。 |
| 本地人类用户交互使用 | `start_local_app.bat` / `start_local_app.sh` 或 `eastmoney-report-scraper app ...` | 仅在用户明确要求“打开本地 App / 本地 Web UI / 一键启动”时使用。 |
| 已安装包后的命令行使用 | `eastmoney-report-scraper ...` | 与脚本入口等价，但 agent 默认仍优先兼容入口。 |

重要规则：

- 默认不要启动长期运行的本地 Web 服务。
- 用户只说“抓研报、重算热点、更新 dashboard、生成文件、给我分析”，都走 CLI workflow。
- 用户明确说“打开本地版、本地 App、Web UI、浏览器工作台、一键启动”时，才使用 Local App 入口。
- OpenClaw workflow 的可视化需求优先用 `--dashboard-only` 生成或刷新静态 `DASHBOARD.html`，而不是启动 Local App。
- Local App 与 CLI 共用同一个 `eastmoney_reports/` 输出目录；`eastmoney.db` 只是本地查询缓存，可以通过 `import-existing` 从 CSV/JSONL 重新生成。
- Local App 提供可选 AI 分析接口；只有用户明确要求在本地 App 中配置或调用 AI 分析时，才使用 `/api/ai/settings`、`/api/ai/evidence`、`/api/ai/analyze`、`/api/ai/history` 或页面里的“AI 分析”面板。OpenClaw 默认仍读取结构化输出自行分析。

## When To Use

适合处理：

- 按日期抓取东方财富个股研报或行业研报
- 按股票、机构、评级、行业筛选研报
- 对某天或某个日期区间生成本地研报库
- 生成 `SUMMARY.md`、`TRADING_DASHBOARD.md`、`CONSENSUS_BRIEF.md`
- 生成或重建离线静态 `DASHBOARD.html`
- 判断某公司或行业是否是近期热点、近期首次被覆盖、沉寂后再覆盖、多券商集中覆盖
- 判断卖方观点是否真的变强或变弱，而不只看覆盖数量是否增加
- 跟踪评级、目标价、EPS、风险词、正向词和主题词的变化方向
- 基于本地输出做按日/周的覆盖热度、券商扩散和行业/个股热度趋势分析
- 在用户提供行情数据或允许补充数据时，做研报信号与市场表现联动分析
- 读取 `ANALYSIS_INPUT.md/json` 做后续 AI 分析
- 对弱提取、失败项做断点续跑

不适合处理：

- 实时行情查询
- 新闻搜索
- 交易下单
- 非东方财富来源的研报采集
- 在没有价格数据时，直接判断研报信号是否产生 alpha

## Default Workflow

默认执行思路：

1. 排障、首次使用或环境不确定时，先运行 `--doctor`。
2. 如果用户没有明确要全量，先用 `--limit 5` 小样本试跑。
3. 单日任务优先用 `--date`；多日任务用 `--start-date` / `--end-date`。
4. 默认使用兼容入口：`python3 {baseDir}/scripts/fetch_reports.py ...`。
5. 正式批量抓取时并发保持保守：`--concurrency 2 --jitter 0.5`。
6. 只需要重算热点时，用 `--hotspots-only`，不要重新抓取网络。
7. 只需要更新可视化看板时，用 `--dashboard-only`，不要重新抓取网络。
8. 抓取完成后优先读取：
   - `DASHBOARD.html`
   - `HOTSPOT_DASHBOARD.md`
   - `TRADING_DASHBOARD.md`
   - `SUMMARY.md`
   - `CONSENSUS_BRIEF.md`
   - `HOTSPOT_SIGNALS.csv`
   - `COMPANY_COVERAGE_SUMMARY.csv`
   - `INDUSTRY_COVERAGE_SUMMARY.csv`
   - `ANALYSIS_INPUT.md`
   - 需要观点趋势时，继续读取各日期目录下的 `report_index.csv` / `ANALYSIS_INPUT.json`
9. 排查失败或续跑时优先查看：
   - `run_manifest.jsonl`
   - `run.log.jsonl`

## Command Recipes

### 环境诊断

```bash
python3 {baseDir}/scripts/fetch_reports.py --doctor
```

### 快速小样本

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --limit 5 --no-xlsx
```

### 只查看列表

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --list-only --stock 润本股份
```

### 单日正式抓取

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --concurrency 2 --jitter 0.5
```

### 日期区间抓取

```bash
python3 {baseDir}/scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12 --concurrency 2 --jitter 0.5
```

### 按股票筛选

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份
```

### 按机构筛选

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --org 中邮证券 --org 国泰海通
```

### 抓行业研报

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --qtype 1 --industry 化学制药
```

### 同时抓个股和行业研报

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --qtype 2
```

### 重抓弱提取结果

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --refresh-weak
```

### 只重试历史失败项

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --resume-errors-only
```

### 自定义输出目录

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --output-dir ./eastmoney_reports_check
```

### 调整热点判断窗口

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --hotspot-days 45 --hotspot-broker-threshold 4
```

### 只重算热点

```bash
python3 {baseDir}/scripts/fetch_reports.py --hotspots-only --output-dir ./eastmoney_reports
```

### 只重建可视化 Dashboard

```bash
python3 {baseDir}/scripts/fetch_reports.py --dashboard-only --output-dir ./eastmoney_reports
```

### 本地 Web App（仅用户明确要求时）

```bash
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports
eastmoney-report-scraper app --output-dir ./eastmoney_reports --port 8765 --open-browser
```

Windows 本地用户可以双击项目根目录的 `start_local_app.bat`。

## Parameters

| 参数 | 用途 |
|---|---|
| `--date` | 单日抓取，格式 `YYYY-MM-DD` |
| `--start-date` / `--end-date` | 日期区间抓取 |
| `--qtype` | `0=个股研报`，`1=行业研报`，`2=全部` |
| `--limit` | 每日最多抓取 N 篇，适合试跑 |
| `--stock` | 按股票名或代码筛选，可重复传 |
| `--org` | 按机构筛选，可重复传 |
| `--rating` | 按评级关键词筛选，可重复传 |
| `--industry` | 按行业关键词筛选，可重复传 |
| `--concurrency` | 详情页并发 worker 数 |
| `--jitter` | 请求随机等待秒数，适合批量任务 |
| `--retries` | 列表/详情重试次数 |
| `--retry-delay` | 重试间隔秒数 |
| `--timeout` | HTTP 超时秒数 |
| `--force` | 忽略已有 Markdown，强制重抓 |
| `--refresh-weak` | 重抓 manifest 中历史 `weak` 项 |
| `--resume-errors-only` | 只重试 manifest 中历史 `error` 项 |
| `--min-text-length` | 低于该正文长度时标记为 `weak` |
| `--manifest-name` | 自定义运行状态文件名 |
| `--hotspot-days` | 近期热点主窗口，默认 30 天 |
| `--hotspot-short-days` | 短期加速窗口，默认 7 天 |
| `--hotspot-silent-days` | 沉寂后再覆盖窗口，默认 90 天 |
| `--hotspot-broker-threshold` | 多券商覆盖阈值，默认 3 家 |
| `--hotspot-coverage-threshold` | 覆盖篇数热度阈值，默认 3 篇 |
| `--no-hotspot` | 跳过热点看板和热点信号表 |
| `--doctor` | 输出 JSON 环境诊断并退出 |
| `--dry-run` | 只抓列表并输出计数，不抓详情 |
| `--list-only` | 只抓列表并输出筛选后 JSON，不抓详情 |
| `--hotspots-only` | 不请求网络，只基于历史覆盖重算热点 |
| `--dashboard-only` | 不请求网络，只基于已有输出重建 `DASHBOARD.html` |
| `--no-dashboard` | 跳过静态 HTML Dashboard 生成 |
| `--dashboard-name` | 自定义 Dashboard 文件名，默认 `DASHBOARD.html` |
| `--no-pdf-fallback` | 禁用 PDF fallback |
| `--no-xlsx` | 跳过 xlsx 导出 |

## Output Reading Guide

单日任务输出目录：

```text
eastmoney_reports/
├── COVERAGE_HISTORY.jsonl
├── COMPANY_COVERAGE_SUMMARY.csv
├── INDUSTRY_COVERAGE_SUMMARY.csv
├── DASHBOARD.html
├── HOTSPOT_DASHBOARD.md
├── HOTSPOT_SIGNALS.csv
└── 研报_2026-05-12/
    ├── 001——某公司——某标题.md
    ├── README.md
    ├── SUMMARY.md
    ├── ANALYSIS_INPUT.md
    ├── ANALYSIS_INPUT.json
    ├── DAILY_BRIEF.md
    ├── TOP_SIGNALS.md
    ├── SECTOR_BRIEF.md
    ├── THEME_BRIEF.md
    ├── TRADING_DASHBOARD.md
    ├── CONSENSUS_BRIEF.md
    ├── report_list.json
    ├── run_manifest.jsonl
    ├── report_index.csv
    ├── report_index.xlsx
    └── run.log.jsonl
```

重点文件：

| 文件 | 何时读取 |
|---|---|
| `DASHBOARD.html` | 想用浏览器集中查看近期热点、趋势、筛选、观点变化和数据质量 |
| `HOTSPOT_DASHBOARD.md` | 想先判断近期首次覆盖、沉寂后再覆盖、多券商集中覆盖和行业共振 |
| `HOTSPOT_SIGNALS.csv` | 想按字段筛选热点等级、覆盖加速、券商数、买入评级集中度 |
| `TRADING_DASHBOARD.md` | 想先看高优先级标的、风险、主题热度 |
| `SUMMARY.md` | 想快速浏览当天所有研报摘要 |
| `TOP_SIGNALS.md` | 想看正向信号、风险信号、估值评级信号 |
| `CONSENSUS_BRIEF.md` | 想看同一股票多机构覆盖、目标价/EPS/评级分歧 |
| `SECTOR_BRIEF.md` | 想按行业聚合 |
| `THEME_BRIEF.md` | 想按主题聚合 |
| `ANALYSIS_INPUT.md` | 想交给 AI 继续做文字分析 |
| `ANALYSIS_INPUT.json` | 想做程序化二次处理 |
| `report_index.csv` | 想用表格筛选、排序、汇总 |
| `run_manifest.jsonl` | 想判断哪些已成功、弱提取、失败、跳过 |
| `run.log.jsonl` | 想排查请求失败、PDF fallback、异常原因 |
| `COVERAGE_HISTORY.jsonl` | 想查看去重后的历史覆盖明细 |
| `COMPANY_COVERAGE_SUMMARY.csv` | 想查看公司-券商-评级组合的历史覆盖次数 |
| `INDUSTRY_COVERAGE_SUMMARY.csv` | 想查看行业-券商-评级组合的历史覆盖次数 |
| 各日期 `report_index.csv` | 想比较评级、目标价、EPS、score、主题标签的跨期变化 |
| 各日期 `ANALYSIS_INPUT.json` | 想比较摘要、风险、正向信号、结构化分析字段的跨期变化 |

区间任务额外输出：

```text
RANGE_SUMMARY.md
RANGE_DASHBOARD.md
```

优先读取 `RANGE_DASHBOARD.md` 看跨日期行业、主题和标的热度变化。

## Hotspot Workflow

当用户问“这个公司/行业是不是近期热点”“是不是第一次被调研”“有没有多家券商一起覆盖”“最近是否重新被关注”时，按这个顺序读文件：

1. `DASHBOARD.html`：先看可视化热点、趋势、筛选和明细。
2. `HOTSPOT_DASHBOARD.md`：给整体结论和分组排名。
3. `HOTSPOT_SIGNALS.csv`：定位具体公司或行业，读取 `hotspotLevel`、`coverage7d`、`coverage30d`、`coverageAcceleration`、`brokerCount30d`、`newBrokerCount30d`、`reasonCodes`、`reasons`。
4. `COVERAGE_HISTORY.jsonl`：需要解释“首次覆盖”或“沉寂后再覆盖”时，回看历史明细。
5. `COMPANY_COVERAGE_SUMMARY.csv` / `INDUSTRY_COVERAGE_SUMMARY.csv`：需要回答历史覆盖次数、券商分布、评级分布时读取。

判断口径：

- `isFirstCoverage=true`：历史中该公司或行业首次出现在近期窗口内。
- `isReactivatedCoverage=true`：历史上出现过，但在沉寂窗口内没有覆盖，近期重新出现。
- `brokerCount30d >= 3`：默认视为多券商集中覆盖。
- `coverage30d >= 3` 或 `coverageAcceleration >= 2`：默认视为近期热度抬升。
- `hotspotLevel=STRONG`：优先汇报；通常来自“首次/再覆盖 + 多券商”或“公司与行业同时升温”。
- `reasonCodes`：优先用于程序化判断，包含 `FIRST_COVERAGE`、`REACTIVATED_COVERAGE`、`MULTI_BROKER`、`COVERAGE_ACCELERATION`、`INDUSTRY_RESONANCE`、`HIGH_BUY_RATIO`。

## Opinion Trend Workflow

当用户问“观点有没有变强/变弱”“覆盖增加是不是看多加强”“同一机构观点是否连续上修”时，不要只看覆盖篇数。按这个顺序处理：

1. 先定位范围：
   - 个股问题：用 `stockCode` 优先，其次 `stockName`。
   - 行业问题：用 `industryName`。
   - 机构连续观点：同时锁定 `orgName` 和标的。
2. 读取材料：
   - 根目录 `COVERAGE_HISTORY.jsonl`：确认覆盖时间、机构、评级、是否新增机构。
   - 各日期目录 `report_index.csv`：读取 `rating`、`ratingChange`、`targetPrice`、`epsForecast`、`signalScore`、`priorityBucket`、`themeTags`。
   - 各日期目录 `ANALYSIS_INPUT.json`：读取 `structured_analysis.valuation_fields`、`positive_signals`、`negative_signals`、`risks`、`score_reasons`。
   - `CONSENSUS_BRIEF.md`：快速看多机构覆盖和显式分歧。
3. 输出判断时分成三层：
   - 覆盖变化：覆盖篇数、券商数、新增券商数。
   - 观点变化：评级是否上调/下调，目标价是否上修/下修，EPS 是否上修/下修，风险项是否增多。
   - 叙事变化：正向关键词是否更集中，风险关键词是否升温，主题标签是否扩散。
4. 结论必须避免把“覆盖增加”直接等同于“看多加强”。推荐表述：
   - `覆盖升温且观点上修`：覆盖增加，同时评级/目标价/EPS/score 至少一项增强。
   - `覆盖升温但观点未增强`：覆盖增加，但评级、目标价、EPS、score 没有明显改善。
   - `覆盖升温但分歧扩大`：覆盖增加，但评级分布或风险词同步走高。
   - `观点转弱`：评级下调、目标价/EPS 下修、风险词增多或 score 下行。

当前项目已经能从 `report_index.csv` 和 `ANALYSIS_INPUT.json` 中读取单篇估值/评级字段；但根目录 `COVERAGE_HISTORY.jsonl` 目前主要记录覆盖、机构、评级和热点字段，不是完整观点因子库。若用户要求严谨的连续目标价/EPS 趋势，应明确说明需要跨日期 `report_index.csv` 或后续新增观点历史文件。

## Time-Series Workflow

当用户问“热度是否加速、见顶、二次发酵、衰减”“行业热度 rolling trend”“券商扩散速度”时，按时间序列而不是单日 snapshot 回答：

1. 优先使用日期区间任务输出：
   - `RANGE_DASHBOARD.md`：快速看跨日期行业、主题、标的热度。
   - 各日期目录 `report_index.csv`：构建按天明细。
   - 根目录 `COVERAGE_HISTORY.jsonl`：补充历史覆盖时间线。
2. 默认聚合口径：
   - `coverage_count_by_day`：每天覆盖篇数。
   - `broker_count_by_day`：每天不同券商数。
   - `new_broker_count_by_day`：相对历史首次出现的券商数。
   - `industry_coverage_by_day`：行业每天覆盖篇数。
   - `theme_hit_rate_by_day`：主题词出现篇数 / 当天样本篇数。
3. 趋势判断口径：
   - 加速：近 7 日覆盖或券商数高于前 7 日，且差值明显扩大。
   - 见顶：覆盖高位但新增券商减少，或 risk/negative 词同步上升。
   - 二次发酵：沉寂后重新出现，且多券商或主题词再次扩散。
   - 衰减：覆盖篇数、券商数、主题命中率连续走低。
4. 如果当前输出不足以生成曲线，可以用本地临时汇总读取 CSV/JSONL，不要修改项目文件；结论里说明使用的是临时聚合。

## Narrative Trend Workflow

当用户问“卖方叙事怎么变”“哪些关键词在扩散”“景气/拐点/涨价/出海/AI/国产替代是否升温”时，按叙事因子分析：

1. 读取：
   - `ANALYSIS_INPUT.json`：摘要、正向信号、负向信号、风险、主题标签。
   - `THEME_BRIEF.md`：当天主题聚合。
   - `report_index.csv`：`themeTags`、`summary`、`scoreReasons`。
2. 默认关键词组：
   - 景气：`景气`、`需求改善`、`订单`、`产能利用率`、`放量`
   - 拐点：`拐点`、`修复`、`改善`、`触底`、`环比`
   - 涨价：`涨价`、`提价`、`价格上涨`、`价差扩大`
   - 出海：`海外`、`出海`、`出口`、`全球化`
   - AI：`AI`、`人工智能`、`算力`、`大模型`
   - 国产替代：`国产替代`、`自主可控`、`信创`、`本土化`
   - 风险：`不及预期`、`竞争加剧`、`价格波动`、`政策变化`、`需求下滑`
3. 输出时给出：
   - 主题词命中率变化。
   - 正向词与风险词是否同步上升。
   - 共识关键词是否从泛化主题转向业绩/订单/价格等更硬的变量。
   - 机构之间是否开始使用同一组叙事词。

## Market Linkage Workflow

当用户问“这个研报信号有没有 alpha”“首次覆盖后 3/5/10 日表现”“多券商共振后是否有超额收益”时，必须把研报信号和行情数据分开处理：

1. 先确认本地是否已有行情/收益率数据。如果没有，明确说明当前 skill 输出的是研报内部信号，不包含股价和指数收益。
2. 如果用户提供或允许读取行情数据，按这些事件对齐：
   - 首次覆盖日：`isFirstCoverage=true` 或 `FIRST_COVERAGE`。
   - 多券商共振日：`brokerCount30d >= 3` 或 `MULTI_BROKER`。
   - 覆盖加速日：`COVERAGE_ACCELERATION`。
   - 行业共振日：`INDUSTRY_RESONANCE`。
3. 默认观察窗口：
   - 个股：事件后 3/5/10 个交易日收益。
   - 相对收益：个股收益减同业/指数收益。
   - 行业：行业热度提升后 3/5/10 日板块收益。
4. 结论要区分：
   - `研报信号领先市场`
   - `研报信号与市场同步`
   - `研报信号滞后市场`
   - `覆盖热但无超额收益`

不要在没有价格数据时声称信号有效或无效；最多评价“研报内部信号强弱”和“需要市场数据验证”。

## Troubleshooting

### xlsx 导出失败

先看环境：

```bash
python3 {baseDir}/scripts/fetch_reports.py --doctor
```

安装 `openpyxl`，或加 `--no-xlsx` 跳过：

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --no-xlsx
```

### 正文太短或质量偏弱

检查单篇 Markdown 里的来源和文本质量；然后重抓弱结果：

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --refresh-weak
```

### 只想补失败项

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --resume-errors-only
```

### 批量任务太慢

适度增加并发，但保持 jitter：

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --concurrency 3 --jitter 0.5
```

### 页面结构变化导致抽取异常

先小样本复现：

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --limit 3 --force
```

然后检查：

- 单篇 Markdown 正文是否为空或噪声较多
- `run_manifest.jsonl` 中的 `qualityScore`
- `run.log.jsonl` 中是否出现 detail fetch 或 PDF fallback 失败
