# eastmoney-report-scraper

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status](https://img.shields.io/badge/Status-v0.5.0-orange)](./CHANGELOG.md)
[![CI](https://github.com/GitPupil/eastmoney-report-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/GitPupil/eastmoney-report-scraper/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-pytest-informational)](./tests)

简体中文 | [English](./README.en.md)

把东方财富研报抓到本地，并自动整理成 Markdown、CSV、热点信号、趋势看板和本地 Web App 的研究工具。你可以用它查看近期哪些公司/行业被密集覆盖、哪些券商在写、评级/目标价/EPS 有没有变化，以及每篇研报的原文摘要。

如果你是第一次使用，建议直接从“一键启动本地 App”开始，不需要先理解所有 CLI 参数。

## 目录

- [功能亮点](#功能亮点)
- [入口怎么选](#入口怎么选)
- [一键启动本地 App](#一键启动本地-app)
- [第一次抓取研报](#第一次抓取研报)
- [输出文件怎么看](#输出文件怎么看)
- [安装](#安装)
- [常用命令](#常用命令)
- [输出内容](#输出内容)
- [未来集成计划](#未来集成计划)
- [CLI 参数](#cli-参数)
- [项目结构](#项目结构)
- [开发与测试](#开发与测试)
- [已知限制](#已知限制)

## 功能亮点

- 抓取对象：支持个股研报、行业研报，也支持两者一起抓。
- 抓取范围：支持单日、日期区间、股票/代码、行业、券商、评级筛选。
- 本地 App：浏览器里发起抓取、查看热点、趋势、观点变化和研报 Markdown。
- 静态 Dashboard：生成 `DASHBOARD.html`，不启动服务也能打开查看。
- 热点识别：识别近期首次覆盖、多券商覆盖、覆盖加速、行业共振。
- 观点变化：跟踪评级、目标价、EPS、信号评分的连续变化。
- 断点续跑：已有文件不会重复抓，弱抽取和失败项可以单独重试。
- 输出完整：Markdown、CSV/XLSX、JSON、日报、主题/行业归纳、共识简报。
- 轻量模式：支持环境检查、只看列表、只重算热点、只重建 Dashboard。

## 入口怎么选

这个项目有两个入口，但它们使用同一套数据和输出目录，不是两个独立项目。

| 你是谁 / 场景 | 推荐入口 | 适合做什么 |
|---|---|---|
| 普通本地用户 | `start_local_app.bat` / `start_local_app.sh` | 打开浏览器工作台，点按钮抓取、筛选、看热点、预览 Markdown |
| OpenClaw / Codex / agent | `python scripts/fetch_reports.py ...` | 自动抓取、续跑、重算热点、生成静态 `DASHBOARD.html` 和 Markdown/CSV/JSONL 输出 |
| 熟悉命令行的用户 | `eastmoney-report-scraper ...` | 用安装后的 CLI 运行同样的抓取和分析流程 |

OpenClaw 或其他 agent 默认应该走 CLI workflow，不需要启动本地 Web App。Local App 主要给人在自己电脑上交互使用；它会读取同一个 `eastmoney_reports/` 输出目录，并把已有 CSV/JSONL 导入 `eastmoney.db` 作为本地查询缓存。`eastmoney.db` 不是唯一数据源，删掉后可以重新导入生成。

## 一键启动本地 App

本地 App 是最适合新手的入口。它会在浏览器里打开一个工作台，你可以在页面上点按钮抓研报、看热点、筛选公司/行业、预览 Markdown 原文。

### Windows

下载项目后，进入项目文件夹，双击：

```text
start_local_app.bat
```

脚本会自动做这些事：

- 检查 Python。
- 如果没有 Python，会尝试用 `winget` 安装 Python 3.12。
- 安装本地 App 依赖。
- 导入已有输出。
- 打开浏览器访问 `http://127.0.0.1:8765`。

### macOS / Linux

第一次运行：

```bash
chmod +x start_local_app.sh
./start_local_app.sh
```

以后再启动：

```bash
./start_local_app.sh
```

如果不想改权限，也可以直接运行：

```bash
bash start_local_app.sh
```

macOS / Linux 脚本会创建项目内 `.venv`，安装 `.[app]` 依赖，导入已有输出并打开浏览器。如果 macOS 没有 Python 且已经安装 Homebrew，脚本会尝试用 Homebrew 安装 Python；如果没有 Homebrew，会提示你先安装 Python。

### 启动后看到什么

- 浏览器地址：`http://127.0.0.1:8765`
- 页面上方：近期热点、趋势总览、全局筛选。
- 页面中部：公司/行业可视化分析、观点变化、研报明细。
- 页面底部：发起抓取、近期抓取记录。

界面截图后续放在 `docs/assets/`：

- `docs/assets/local-app-radar.png`：交易雷达首页。
- `docs/assets/local-app-analysis.png`：公司/行业可视化分析。
- `docs/assets/local-app-preview.png`：Markdown 预览页。

当前仓库不放占位图；等有真实截图后再在这里嵌入图片。

启动 App 的终端窗口需要保持开启。关闭终端后，本地 App 服务也会停止。

## 第一次抓取研报

### 在本地 App 里抓取

打开本地 App 后，滑到页面底部的“发起抓取”：

1. 选择“单日日期”，或填写“区间开始 / 区间结束”。
2. 类型选择“全部”“个股研报”或“行业研报”。
3. 可以按股票、行业、券商、评级筛选；不填就是不过滤。
4. 点“开始”。
5. 抓取完成后点“刷新”，查看热点、趋势和研报明细。

几个容易混淆的参数：

| 参数 | 小白解释 |
|---|---|
| `limit` | 每个日期最多抓多少篇；留空表示不限制 |
| `并发` | 同时抓多少篇详情页；本地 App 抓“全部”时默认更保守 |
| `jitter` | 每次请求之间随机等一小会儿，适合批量抓取时放慢节奏 |

### 用命令行抓取

如果你熟悉终端，可以直接运行：

```bash
git clone https://github.com/GitPupil/eastmoney-report-scraper.git
cd eastmoney-report-scraper
pip install -r requirements.txt
python scripts/fetch_reports.py --date 2026-05-12 --limit 5
```

同时抓个股研报和行业研报：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --qtype 2
```

抓一个日期区间：

```bash
python scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12
```

## 输出文件怎么看

默认输出目录是：

```text
eastmoney_reports/
```

最常看的文件：

| 文件 | 适合什么时候看 |
|---|---|
| `DASHBOARD.html` | 想快速看热点、趋势、筛选、观点变化 |
| `HOTSPOT_DASHBOARD.md` | 想看近期首次覆盖、多券商共振、行业共振 |
| `HOTSPOT_SIGNALS.csv` | 想用表格筛选热点信号 |
| `TRADING_DASHBOARD.md` | 想看交易优先级、风险、行业/主题热度 |
| `CONSENSUS_BRIEF.md` | 想看同一公司多家券商覆盖和分歧 |
| `report_index.csv` | 想用 Excel 或程序处理研报字段 |
| 单篇 `.md` | 想看某篇研报的正文、摘要、风险和结构化信号 |

抓取后会看到类似结构：

```text
eastmoney_reports/
├── DASHBOARD.html
├── HOTSPOT_DASHBOARD.md
├── HOTSPOT_SIGNALS.csv
├── COVERAGE_HISTORY.jsonl
├── COMPANY_COVERAGE_SUMMARY.csv
├── INDUSTRY_COVERAGE_SUMMARY.csv
└── 研报_2026-05-12/
    ├── 001——某公司——某标题.md
    ├── SUMMARY.md
    ├── ANALYSIS_INPUT.json
    ├── TRADING_DASHBOARD.md
    ├── CONSENSUS_BRIEF.md
    └── report_index.csv
```

## 安装

### 运行环境

- Python 3.9+
- `beautifulsoup4`：HTML 结构化解析
- `openpyxl`：导出 XLSX

### 可选工具

- `pdftotext`：HTML 正文过弱时用于 PDF fallback

### 安装依赖

```bash
pip install -r requirements.txt
```

开发环境：

```bash
pip install -r requirements-dev.txt
```

本地 App 依赖：

```bash
pip install ".[app]"
```

## 常用命令

抓取某一天的个股研报：

```bash
python scripts/fetch_reports.py --date 2026-05-12
```

抓取日期区间：

```bash
python scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12
```

按股票名或代码筛选：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份
```

按机构筛选：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --org 中邮证券 --org 国泰海通
```

抓行业研报并按行业筛选：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --qtype 1 --industry 化学制药
```

同时抓个股研报和行业研报：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --qtype 2
```

并发抓取详情页：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --concurrency 2 --jitter 0.5
```

只重抓历史弱提取结果：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --refresh-weak
```

只重试历史失败结果：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --resume-errors-only
```

调整热点判断窗口：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --hotspot-days 45 --hotspot-broker-threshold 4
```

检查本地环境：

```bash
python scripts/fetch_reports.py --doctor
```

只基于历史记录重算热点：

```bash
python scripts/fetch_reports.py --hotspots-only --output-dir ./eastmoney_reports
```

只基于已有输出重建可视化 Dashboard：

```bash
python scripts/fetch_reports.py --dashboard-only --output-dir ./eastmoney_reports
```

只查看当天列表和筛选结果，不抓详情：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --list-only --stock 润本股份
```

导入已有输出到本地 SQLite：

```bash
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports
```

启动本地 Web App：

```bash
eastmoney-report-scraper app --output-dir ./eastmoney_reports --port 8765 --open-browser
```

## 输出内容

### 单日任务

```text
eastmoney_reports/
├── COVERAGE_HISTORY.jsonl
├── COMPANY_COVERAGE_SUMMARY.csv
├── INDUSTRY_COVERAGE_SUMMARY.csv
├── DASHBOARD.html
├── eastmoney.db
├── local_app_config.json
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

### 区间任务

```text
eastmoney_reports/
└── 研报_2026-05-09_to_2026-05-12/
    ├── RANGE_SUMMARY.md
    ├── RANGE_DASHBOARD.md
    ├── 研报_2026-05-09/
    ├── 研报_2026-05-10/
    ├── 研报_2026-05-11/
    └── 研报_2026-05-12/
```

### 推荐阅读顺序

1. `DASHBOARD.html`：先用浏览器看近期热点、趋势、筛选、观点变化和数据质量。
2. `HOTSPOT_DASHBOARD.md`：看近期首次覆盖、沉寂后再覆盖、多券商集中覆盖和行业共振。
3. `TRADING_DASHBOARD.md`：看交易优先级、风险和热度。
4. `SUMMARY.md`：快速扫当天所有样本。
5. `TOP_SIGNALS.md`：看正向/风险/估值评级信号。
6. `CONSENSUS_BRIEF.md`：看同一标的的多机构覆盖和分歧。
7. `COMPANY_COVERAGE_SUMMARY.csv` / `INDUSTRY_COVERAGE_SUMMARY.csv`：看历史覆盖次数。
8. `ANALYSIS_INPUT.md` / `ANALYSIS_INPUT.json`：交给 AI 或程序继续分析。

### 主要输出速览

| 文件 | 用途 |
|---|---|
| `DASHBOARD.html` | 离线可视化看板，集中查看热点、趋势、筛选、观点变化和质量 |
| `HOTSPOT_DASHBOARD.md` | 近期首次覆盖、沉寂后再覆盖、多券商覆盖、行业共振 |
| `HOTSPOT_SIGNALS.csv` | 可程序化筛选的热点指标、原因和 reason codes |
| `TRADING_DASHBOARD.md` | 交易优先级、风险、行业/主题热度 |
| `CONSENSUS_BRIEF.md` | 同一标的多机构覆盖与分歧 |
| `COVERAGE_HISTORY.jsonl` | 去重后的历史覆盖明细 |
| `report_index.csv/xlsx` | 单日研报索引和结构化字段 |
| `eastmoney.db` | 本地 App SQLite 查询缓存 |
| `local_app_config.json` | 本地 App 输出目录、端口和默认参数 |

## Local App Mode

Local App 是本地浏览器工作台，不替代 CLI / OpenClaw workflow。它默认读取同一套输出文件，并把已有 CSV/JSONL 导入 `eastmoney.db` 以便快速查询。

```bash
pip install ".[app]"
eastmoney-report-scraper import-existing --output-dir ./eastmoney_reports
eastmoney-report-scraper app --output-dir ./eastmoney_reports --host 127.0.0.1 --port 8765 --open-browser
```

一键启动：

```bash
# Windows：双击
start_local_app.bat

# macOS / Linux
chmod +x start_local_app.sh
./start_local_app.sh
```

打开：

```text
http://127.0.0.1:8765
```

Local App MVP 支持：

- 导入已有输出到 SQLite。
- 查看最近任务、热点和研报明细。
- 从页面发起单日/区间抓取。
- 通过 `/api/health`、`/api/reports`、`/api/hotspots`、`/api/dashboard-data` 读取本地数据。
- Windows 新电脑可双击 `start_local_app.bat` 一键安装依赖、导入已有输出、启动服务并打开浏览器。
- macOS / Linux 可运行 `start_local_app.sh`，脚本会创建 `.venv`、安装依赖、导入已有输出、启动服务并打开浏览器。

## 未来集成计划

以下能力尚未作为当前版本功能发布，已进入 TODO / roadmap：

- 实时数据接口 API：计划支持用户在本地 App 或 CLI 配置中提交行情/数据源 token，用于补充价格、指数、板块表现和研报信号后的市场反馈。token 只应保留在本地运行环境或被 Git 忽略的本地配置中，不写入日志、Markdown/CSV/JSONL/XLSX 输出、SQLite 数据行、Dashboard HTML 或异常信息。
- AI 分析：计划支持用户提供模型 API token，对选中的研报、公司、行业或时间区间做进一步总结、对比和观点变化解释。token 必须在 UI/CLI 诊断中脱敏显示，并从所有研究导出文件中排除。
- 实现这些能力前，需要先补齐 token 脱敏 helper、配置加载规则和回归测试，避免 token 被调试输出或导出文件带出。

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--date` | 单日抓取，格式 `YYYY-MM-DD` |
| `--start-date` | 区间开始日期 |
| `--end-date` | 区间结束日期 |
| `--limit` | 每个日期仅抓前 N 篇 |
| `--qtype` | `0=个股研报`，`1=行业研报`，`2=全部` |
| `--page-size` | 列表接口页大小 |
| `--delay` | 串行抓取时每篇详情页之间的等待秒数 |
| `--timeout` | HTTP 超时秒数 |
| `--retries` | 列表/详情抓取重试次数 |
| `--retry-delay` | 重试间隔秒数 |
| `--concurrency` | 详情页并发抓取 worker 数 |
| `--jitter` | 为详情页请求增加随机等待秒数 |
| `--output-dir` | 输出根目录 |
| `--stock` | 按股票名/代码筛选，可重复传 |
| `--org` | 按机构筛选，可重复传 |
| `--rating` | 按评级筛选，可重复传 |
| `--industry` | 按行业筛选，可重复传 |
| `--force` | 即使已存在 Markdown 也强制重抓 |
| `--refresh-weak` | 仅重抓历史弱提取结果 |
| `--resume-errors-only` | 仅重试历史失败结果 |
| `--min-text-length` | 低于该正文长度时标记为 `weak` |
| `--manifest-name` | 自定义运行状态文件名 |
| `--hotspot-days` | 热点判断主窗口天数，默认 `30` |
| `--hotspot-short-days` | 热点短窗口天数，默认 `7` |
| `--hotspot-silent-days` | 沉寂后再覆盖判断窗口，默认 `90` |
| `--hotspot-broker-threshold` | 多券商覆盖阈值，默认 `3` |
| `--hotspot-coverage-threshold` | 覆盖篇数热度阈值，默认 `3` |
| `--no-hotspot` | 跳过热点看板和热点信号表 |
| `--doctor` | 输出 JSON 环境诊断并退出 |
| `--dry-run` | 只抓列表并输出计数，不抓详情 |
| `--list-only` | 只抓列表并输出筛选后 JSON，不抓详情 |
| `--hotspots-only` | 不请求网络，只基于历史覆盖重算热点 |
| `--dashboard-only` | 不请求网络，只基于已有输出重建 `DASHBOARD.html` |
| `--no-dashboard` | 跳过静态 HTML Dashboard 生成 |
| `--dashboard-name` | 自定义 Dashboard 文件名，默认 `DASHBOARD.html` |
| `--no-pdf-fallback` | 禁用 PDF fallback |
| `--no-xlsx` | 跳过 XLSX 导出 |

### 本地 App 命令

| 命令 | 说明 |
|---|---|
| `eastmoney-report-scraper import-existing` | 把已有输出导入本地 SQLite |
| `eastmoney-report-scraper app` | 启动本地 Web App |
| `--host` | 本地 App host，默认 `127.0.0.1` |
| `--port` | 本地 App port，默认 `8765` |
| `--db-path` | 自定义 SQLite 路径 |
| `--open-browser` | 启动后自动打开默认浏览器 |

## 项目结构

```text
.
├── eastmoney_report_scraper/
│   ├── client.py       # 列表/详情请求与重试
│   ├── parser.py       # HTML/PDF 抽取与文本质量评分
│   ├── analysis.py     # 摘要、风险、财务信号、估值字段
│   ├── scoring.py      # signal score 与 priority bucket
│   ├── core/           # CLI、OpenClaw 和本地 App 共用的业务编排
│   ├── exporters/      # Markdown、CSV、XLSX、日报、覆盖历史和看板
│   ├── hotspots.py     # 公司/行业近期热度和覆盖变化识别
│   ├── dashboard.py    # 离线静态 HTML Dashboard
│   ├── storage/        # 本地 SQLite 导入和查询
│   ├── app/            # 本地 Web App 路由、模板和静态资源
│   ├── config.py       # 本地 App 配置
│   └── cli.py          # CLI 参数解析与入口分发
├── scripts/
│   └── fetch_reports.py # 兼容入口
├── tests/
│   ├── fixtures/
│   ├── test_core.py
│   ├── test_cli_modes.py
│   └── test_parser_fixtures.py
├── README.md
├── README.en.md
├── CHANGELOG.md
├── ROADMAP.md
├── TODO.md
└── DEVELOPMENT.md
```

入口关系：

```text
OpenClaw / scripts/fetch_reports.py -> CLI -> core
eastmoney-report-scraper            -> CLI -> core
Local App                           -> app services/tasks -> core
```

## 开发与测试

```bash
python scripts/fetch_reports.py --help
python -B -m pytest -q -p no:cacheprovider
python -m ruff check . --no-cache
```

最小 smoke test：

```bash
python scripts/fetch_reports.py --date 2026-05-12 --limit 2 --output-dir ./eastmoney_reports_check
```

## 版本状态

当前主线：0.5.0

- 已完成模块化重构。
- 已增加 manifest、文本质量评分和弱/错误结果续跑。
- 已增加评分原因、评分拆解、共识简报和区间看板。
- 已增加历史覆盖明细、公司/行业覆盖汇总和热点识别看板。
- 已增加 CI、fixtures、轻量 CLI 模式和 exporter 包拆分。
- 已增加离线静态 `DASHBOARD.html`，支持热点、趋势、筛选、观点变化和质量查看。
- 已增加 Local App MVP，支持 SQLite 导入、本地 API 和浏览器工作台。
- 后续重点见 [ROADMAP.md](./ROADMAP.md) 与 [TODO.md](./TODO.md)。

## 已知限制

- 本项目不是官方稳定内容 API。
- 东方财富页面结构变化可能导致抽取逻辑需要调整。
- PDF fallback 依赖本地 `pdftotext`。
- 当前结构化分析是规则驱动，适合研究初筛和归档。

## License

[MIT](./LICENSE)
