# eastmoney-report-scraper

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status](https://img.shields.io/badge/Status-v0.2.0-orange)](./CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-pytest-informational)](./tests)

简体中文 | [English](./README.en.md)

面向研究场景的东方财富研报抓取与本地归档工具。它可以按日期或日期区间批量抓取东方财富研报中心的个股研报和行业研报，自动提取正文、生成摘要、打分、横向归纳，并输出适合阅读、AI 分析和程序化二次处理的本地研究文件。

> 这是页面抓取型 workflow，不是东方财富官方稳定内容 API。请自行确认使用方式符合目标网站条款、政策和适用法规。

## 目录

- [功能亮点](#功能亮点)
- [快速开始](#快速开始)
- [安装](#安装)
- [常用命令](#常用命令)
- [输出内容](#输出内容)
- [CLI 参数](#cli-参数)
- [项目结构](#项目结构)
- [开发与测试](#开发与测试)
- [限制与免责声明](#限制与免责声明)

## 功能亮点

- 支持东方财富个股研报与行业研报抓取。
- 支持单日和日期区间批量任务。
- 支持按股票/代码、机构、评级、行业筛选。
- 自动重试列表页和详情页请求。
- 支持基于已有 Markdown 与 `run_manifest.jsonl` 的断点续跑。
- HTML 抽取偏弱时自动尝试 PDF fallback。
- 使用文本质量分选择 HTML / PDF 结果。
- 自动生成单篇 Markdown、摘要、日报、行业/主题归纳、交易看板和共识简报。
- 输出 `scoreReasons` / `scoreBreakdown`，让信号评分更透明。
- 累计 `COVERAGE_HISTORY.jsonl`，生成公司/行业覆盖汇总。
- 自动生成 `HOTSPOT_DASHBOARD.md` 和 `HOTSPOT_SIGNALS.csv`，识别近期首次覆盖、沉寂后再覆盖、多券商集中覆盖和行业共振。
- v2 已拆分为模块化包结构，并补充 pytest 回归测试。

## 快速开始

```bash
git clone https://github.com/GitPupil/eastmoney-report-scraper.git
cd eastmoney-report-scraper
pip install -r requirements.txt
python scripts/fetch_reports.py --date 2026-05-12 --limit 5
```

运行后默认输出到：

```text
eastmoney_reports/研报_2026-05-12/
```

同时会在输出根目录累计历史覆盖记录：

```text
eastmoney_reports/
├── COVERAGE_HISTORY.jsonl
├── COMPANY_COVERAGE_SUMMARY.csv
├── INDUSTRY_COVERAGE_SUMMARY.csv
├── HOTSPOT_DASHBOARD.md
└── HOTSPOT_SIGNALS.csv
```

安装为 Python 包后，也可以使用命令行入口：

```bash
pip install .
eastmoney-report-scraper --date 2026-05-12 --limit 5
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

## 输出内容

### 单日任务

```text
eastmoney_reports/
├── COVERAGE_HISTORY.jsonl
├── COMPANY_COVERAGE_SUMMARY.csv
├── INDUSTRY_COVERAGE_SUMMARY.csv
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

1. `HOTSPOT_DASHBOARD.md`：先看近期首次覆盖、沉寂后再覆盖、多券商集中覆盖和行业共振。
2. `TRADING_DASHBOARD.md`：看交易优先级、风险和热度。
3. `SUMMARY.md`：快速扫当天所有样本。
4. `TOP_SIGNALS.md`：看正向/风险/估值评级信号。
5. `CONSENSUS_BRIEF.md`：看同一标的的多机构覆盖和分歧。
6. `COMPANY_COVERAGE_SUMMARY.csv` / `INDUSTRY_COVERAGE_SUMMARY.csv`：看历史覆盖次数。
7. `ANALYSIS_INPUT.md` / `ANALYSIS_INPUT.json`：交给 AI 或程序继续分析。

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--date` | 单日抓取，格式 `YYYY-MM-DD` |
| `--start-date` | 区间开始日期 |
| `--end-date` | 区间结束日期 |
| `--limit` | 每个日期仅抓前 N 篇 |
| `--qtype` | `0=个股研报`，`1=行业研报` |
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
| `--no-pdf-fallback` | 禁用 PDF fallback |
| `--no-xlsx` | 跳过 XLSX 导出 |

## 项目结构

```text
.
├── eastmoney_report_scraper/
│   ├── client.py       # 列表/详情请求与重试
│   ├── parser.py       # HTML/PDF 抽取与文本质量评分
│   ├── analysis.py     # 摘要、风险、财务信号、估值字段
│   ├── scoring.py      # signal score 与 priority bucket
│   ├── exporters.py    # Markdown、CSV、XLSX、日报和看板
│   ├── hotspots.py     # 公司/行业近期热度和覆盖变化识别
│   └── cli.py          # CLI 参数与主流程编排
├── scripts/
│   └── fetch_reports.py # 兼容入口
├── tests/
│   └── test_core.py
├── README.md
├── README.en.md
├── CHANGELOG.md
├── ROADMAP.md
├── TODO.md
└── DEVELOPMENT.md
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

当前主线：0.2.0

- 已完成模块化重构。
- 已增加 manifest、文本质量评分和弱/错误结果续跑。
- 已增加评分原因、评分拆解、共识简报和区间看板。
- 已增加历史覆盖明细、公司/行业覆盖汇总和热点识别看板。
- 后续重点见 [ROADMAP.md](./ROADMAP.md) 与 [TODO.md](./TODO.md)。

## 限制与免责声明

- 本项目不是官方稳定内容 API。
- 东方财富页面结构变化可能导致抽取逻辑需要调整。
- PDF fallback 依赖本地 `pdftotext`。
- 当前结构化分析是规则驱动，适合研究初筛和归档，不构成投资建议。
- 请在使用时自行确认符合目标网站条款、使用政策与适用法规。

## License

[MIT](./LICENSE)
