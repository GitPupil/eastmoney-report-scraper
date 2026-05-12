# eastmoney-report-scraper

[English](./README.md) | 简体中文

一个面向研究场景的东方财富研报抓取工具。

它可以按日期或日期区间批量抓取东方财富研报中心的**个股研报**和**行业研报**，从网页详情页提取正文，必要时自动走 **PDF fallback**，并输出适合阅读、归档、AI 分析和程序化二次处理的本地研究文件、日报与交易看板。

## 项目亮点

- 支持东方财富 **个股研报** 与 **行业研报** 抓取
- 支持 **单日抓取** 与 **日期区间批量抓取**
- 支持按 **股票、机构、评级、行业** 筛选
- 自动重试列表页和详情页请求
- 支持基于已有 markdown 的断点续跑
- HTML 抽取偏弱时可自动使用 **PDF fallback**
- 支持通过 `--concurrency` 做可控并发抓取
- 自动生成摘要、分析输入、索引、日报和交易看板类研究产物

## 当前版本状态

当前已实现：

- **v1.1**：稳定性增强
- **v1.2**：研究流程化输出
- **v1.3**：单篇结构化分析
- **v1.4**：多篇横向归纳
- **v1.5 alpha**：分析、评分、看板、并发基础能力已落地

当前 `v1.5 alpha` 已新增：

- 风险提取增强
- 基于财务信号的结构化分析
- `signal score` 与 `priority bucket`
- 更丰富的估值导出字段（`ratingChange`、`targetPrice`、`epsForecast`、`peForecast`）
- `TRADING_DASHBOARD.md`
- `Sector Heat / Theme Heat`
- `--concurrency` 并发详情抓取

相关文档：

- [ROADMAP.md](./ROADMAP.md)
- [TODO.md](./TODO.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [DEVELOPMENT.md](./DEVELOPMENT.md)

## 仓库结构

```text
.
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── CHANGELOG.md
├── ROADMAP.md
├── TODO.md
├── DEVELOPMENT.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── scripts/
    ├── __init__.py
    └── fetch_reports.py
```

## 工作流程

本项目的核心抓取流程是：

1. 调用东方财富研报列表接口，拿到 `infoCode`
2. 请求对应研报详情页 HTML
3. 从 HTML 页面提取正文
4. 如果 HTML 抽取结果过弱，则尝试 **PDF fallback**
5. 生成结构化摘要、风险、估值字段、评分和主题标签
6. 输出本地研报 markdown、索引、日报和交易看板

这是一套**页面抓取型 workflow**，不是官方稳定内容 API。

## 功能列表

### 数据抓取

- 单日抓取
- 日期区间批量抓取
- 个股研报抓取（`--qtype 0`）
- 行业研报抓取（`--qtype 1`）

### 条件筛选

- 按股票名或代码筛选
- 按机构筛选
- 按评级筛选
- 按行业筛选
- 支持限制每日抓取前 N 篇

### 稳定性能力

- 列表页失败自动重试
- 详情页失败自动重试
- `run.log.jsonl` 结构化日志
- 已有 markdown 默认断点续跑
- 支持 `--force` 强制重抓
- HTML 正文过弱时自动尝试 PDF fallback
- 支持 `--concurrency` 做可控并发详情抓取

### 研究输出

- 每篇研报一个 markdown 文件
- `README.md` 任务汇总
- `SUMMARY.md`
- `ANALYSIS_INPUT.md`
- `ANALYSIS_INPUT.json`
- `DAILY_BRIEF.md`
- `TOP_SIGNALS.md`
- `SECTOR_BRIEF.md`
- `THEME_BRIEF.md`
- `TRADING_DASHBOARD.md`
- `report_list.json`
- `report_index.csv`
- `report_index.xlsx`（可选）

### 当前结构化分析字段

当前输出已包含：

- 一句话结论
- 核心驱动
- 正向信号
- 负向信号
- 估值 / 评级字段
- 风险项
- 主题标签
- 信号评分
- 优先级分桶

## 环境要求

### 运行环境

- Python 3.9+

### 可选依赖

- `pdftotext`：用于 PDF fallback
- `openpyxl`：用于导出 XLSX

安装运行依赖：

```bash
pip install -r requirements.txt
```

也可以直接安装 XLSX 导出依赖：

```bash
pip install openpyxl
```

## 安装

### 方式一：直接从仓库运行

```bash
git clone https://github.com/GitPupil/eastmoney-report-scraper.git
cd eastmoney-report-scraper
pip install -r requirements.txt
```

### 方式二：按标准 Python 项目安装

```bash
pip install .
```

## 快速开始

### 抓取某一天的全部研报

```bash
python3 scripts/fetch_reports.py --date 2026-05-12
```

### 使用并发抓取

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --concurrency 2
```

### 抓取日期区间研报

```bash
python3 scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12
```

### 按股票筛选

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份
```

### 按机构筛选

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --org 中邮证券 --org 国泰海通
```

### 抓行业研报并按行业筛选

```bash
python3 scripts/fetch_reports.py --date 2026-05-12 --qtype 1 --industry 化学制药
```

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--date` | 单日抓取，格式 `YYYY-MM-DD` |
| `--start-date` | 区间开始日期 |
| `--end-date` | 区间结束日期 |
| `--limit` | 每个日期仅抓前 N 篇 |
| `--qtype` | `0=个股研报`，`1=行业研报` |
| `--page-size` | 列表接口页大小 |
| `--delay` | 每篇详情页之间的等待秒数 |
| `--timeout` | HTTP 超时秒数 |
| `--retries` | 列表/详情抓取重试次数 |
| `--retry-delay` | 重试间隔秒数 |
| `--concurrency` | 详情页并发抓取 worker 数 |
| `--output-dir` | 输出根目录 |
| `--stock` | 按股票名/代码筛选，可重复传 |
| `--org` | 按机构筛选，可重复传 |
| `--rating` | 按评级筛选，可重复传 |
| `--industry` | 按行业筛选，可重复传 |
| `--force` | 即使已存在 markdown 也强制重抓 |
| `--no-pdf-fallback` | 禁用 PDF fallback |
| `--no-xlsx` | 跳过 XLSX 导出 |

## 输出结构

### 单日任务

```text
eastmoney_reports/
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
    ├── report_list.json
    ├── report_index.csv
    ├── report_index.xlsx
    └── run.log.jsonl
```

### 区间任务

```text
eastmoney_reports/
└── 研报_2026-05-09_to_2026-05-12/
    ├── RANGE_SUMMARY.md
    ├── 研报_2026-05-09/
    ├── 研报_2026-05-10/
    ├── 研报_2026-05-11/
    └── 研报_2026-05-12/
```

## 推荐使用流程

1. 先按目标日期或日期区间执行抓取
2. 用 `SUMMARY.md` 快速浏览当天样本
3. 用 `TRADING_DASHBOARD.md` 看交易优先级与热度
4. 用 `ANALYSIS_INPUT.md` 或 `ANALYSIS_INPUT.json` 做 AI / 程序化二次分析
5. 用 `DAILY_BRIEF.md`、`TOP_SIGNALS.md`、`SECTOR_BRIEF.md`、`THEME_BRIEF.md` 做多篇横向归纳

## 限制说明

- 本项目不是官方稳定内容 API
- 东方财富页面结构发生变化时，抓取逻辑可能需要调整
- PDF fallback 依赖本地 `pdftotext`
- XLSX 导出依赖 `openpyxl`
- 当前筛选主要还是抓取后本地过滤
- 当前并发主要用于详情页抓取，进度输出可能按完成顺序出现
- 当前版本仍然是 script-first 结构，尚未完全模块化

## 免责声明

本项目用于研究、流程自动化和本地知识归档。请在使用时自行确认符合目标网站的相关条款、使用政策与适用法规。
