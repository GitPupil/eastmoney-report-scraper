---
name: eastmoney_report_scraper
description: 基于东方财富研报中心网页与底层列表接口，按日期或日期区间批量拉取个股或行业研报列表，支持筛选、重试、断点续跑、manifest、PDF fallback、结构化分析、signal score、评分拆解、交易看板、共识简报、并发抓取，以及 markdown / SUMMARY / ANALYSIS_INPUT / TRADING_DASHBOARD / CONSENSUS_BRIEF / csv/xlsx / report_list.json 等输出。Batch scrape Eastmoney research reports by date/date range with filters, retries, resume, manifest, PDF fallback, structured analysis, scoring, dashboard and consensus outputs, and csv/xlsx/json indexes.
metadata:
  {
    "openclaw": {
      "requires": {},
      "install": [
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

这个 skill 对应的是 **“列表 API 拿 `infoCode` → 详情页抓 HTML 正文 → 必要时 PDF fallback → 本地落盘 → 结构化分析与交易化汇总”** 的 workflow，
不是妙想 `searchNews` 检索接口。

## 当前状态

当前已进入 **v2.0** 阶段。

已具备：

- 批量抓取个股 / 行业研报
- 多条件筛选
- 重试与断点续跑
- PDF fallback
- 单篇结构化分析
- 多篇横向归纳
- signal score / priority bucket
- `TRADING_DASHBOARD.md`
- `Sector Heat / Theme Heat`
- `--concurrency` 并发详情抓取
- richer csv 导出字段
- 模块化包结构
- `run_manifest.jsonl`
- 文本质量评分
- `scoreReasons` / `scoreBreakdown`
- `CONSENSUS_BRIEF.md`
- 区间任务 `RANGE_DASHBOARD.md`
- `--refresh-weak` / `--resume-errors-only` / `--min-text-length` / `--jitter`

## 已实现版本

### v1.1 稳定性增强
- 详情页抓取失败自动重试
- 列表页抓取失败自动重试
- `run.log.jsonl` 结构化日志
- 断点续跑：已存在 markdown 时默认跳过
- HTML 正文过短时自动尝试 `PDF fallback`

### v1.2 研究工具化
- 按 `股票/代码` 筛选
- 按 `机构` 筛选
- 按 `评级` 筛选
- 按 `行业` 筛选
- 支持日期区间批量抓取
- 支持增量更新 / resume
- 生成 `report_index.csv`
- 可选生成 `report_index.xlsx`
- 保留 `SUMMARY.md` / `ANALYSIS_INPUT.md` / `ANALYSIS_INPUT.json`

### v1.3 单篇结构化分析
- 每篇研报自动生成：
  - `一句话结论`
  - `核心驱动`
  - `正向信号`
  - `负向信号`
  - `估值/评级`
  - `交易含义`
  - `风险`
- 结构化分析会写入：
  - 单篇 `.md`
  - `ANALYSIS_INPUT.md`
  - `ANALYSIS_INPUT.json`

### v1.4 多篇横向归纳
- 自动生成 `DAILY_BRIEF.md`
- 自动生成 `TOP_SIGNALS.md`
- 自动生成 `SECTOR_BRIEF.md`
- 自动生成 `THEME_BRIEF.md`
- 聚合当天：
  - 主线
  - 重点个股
  - 机构活跃度
  - 可交易线索
  - 风险信号
  - 行业分组
  - 主题分组

### v1.5 alpha
- 风险提取增强
- 基于财务信号的结构化分析
- `signal_score` 与 `priority_bucket`
- richer valuation fields：
  - `ratingChange`
  - `targetPrice`
  - `epsForecast`
  - `peForecast`
- 自动生成 `TRADING_DASHBOARD.md`
- 看板新增：
  - `Sector Heat`
  - `Theme Heat`
  - `Active Brokers`
- 支持 `--concurrency` 控制详情页并发抓取

### v2.0（当前）
- 核心逻辑拆分到 `eastmoney_report_scraper/`
- `scripts/fetch_reports.py` 保持兼容入口
- `run_manifest.jsonl` 记录状态、来源、质量分、错误和输出文件
- HTML 结构化解析，缺少 BeautifulSoup 时回退基础解析
- HTML / PDF 按文本质量分选择
- 评分原因与评分拆解导出
- 自动生成 `CONSENSUS_BRIEF.md`
- 区间任务自动生成 `RANGE_DASHBOARD.md`
- 新增弱结果 / 错误结果续跑和请求 jitter 参数

## 快速开始

### 单日全量

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12
```

### 单日 + 并发抓取

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --concurrency 2
```

### 单日 + 股票筛选

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --stock 润本股份
```

### 单日 + 机构筛选

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --org 中邮证券 --org 国泰海通
```

### 单日 + 行业筛选 + 小样本

```bash
python3 {baseDir}/scripts/fetch_reports.py --date 2026-05-12 --industry 化学制药 --limit 5
```

### 日期区间 + 增量更新

```bash
python3 {baseDir}/scripts/fetch_reports.py --start-date 2026-05-09 --end-date 2026-05-12
```

## 参数说明

| 参数 | 说明 |
|---|---|
| `--date` | 单日抓取，格式 `YYYY-MM-DD` |
| `--start-date` | 区间开始日期 |
| `--end-date` | 区间结束日期 |
| `--limit` | 每个日期仅抓前 N 篇 |
| `--qtype` | `0=个股研报`，`1=行业研报` |
| `--page-size` | 列表接口页大小 |
| `--delay` | 每篇详情页抓取间隔秒数 |
| `--timeout` | HTTP 超时秒数 |
| `--retries` | 列表/详情重试次数 |
| `--retry-delay` | 重试间隔秒数 |
| `--concurrency` | 详情页并发抓取 worker 数 |
| `--stock` | 按股票名/代码筛选，可重复传 |
| `--org` | 按机构筛选，可重复传 |
| `--rating` | 按评级筛选，可重复传 |
| `--industry` | 按行业筛选，可重复传 |
| `--force` | 忽略已抓文件，强制重抓 |
| `--no-pdf-fallback` | 禁用 PDF fallback |
| `--no-xlsx` | 跳过 xlsx 索引导出 |
| `--refresh-weak` | 仅重抓历史弱提取结果 |
| `--resume-errors-only` | 仅重试历史失败结果 |
| `--min-text-length` | 低于该正文长度时标记为 weak |
| `--jitter` | 为详情页请求增加随机等待秒数 |
| `--manifest-name` | 自定义运行状态文件名 |

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

## 自动摘要与二次分析

- `SUMMARY.md`：规则版摘要汇总
- `ANALYSIS_INPUT.md`：适合直接继续做 AI 分析
- `ANALYSIS_INPUT.json`：适合程序化二次处理
- `TRADING_DASHBOARD.md`：适合先看当日交易优先级和热度

推荐工作流：

1. 先抓取与摘要
2. 先看 `TRADING_DASHBOARD.md`
3. 再读取 `SUMMARY.md` / `ANALYSIS_INPUT.md`
4. 继续输出：
   - 单篇核心结论
   - 多篇共识主线
   - 券商分歧点
   - 业绩/估值/评级变化
   - 可交易线索与风险

## 风险与限制

- 这是 **页面抓取型** workflow，不是稳定的官方内容 API
- `PDF fallback` 依赖系统存在 `pdftotext`
- `xlsx` 导出依赖 `openpyxl`
- 当前筛选主要是抓取后本地过滤，不是请求端精准 query
- 当前并发主要用于详情页抓取，进度输出可能按完成顺序出现
- 当前已模块化，结构化分析仍为规则驱动，适合研究初筛和归档
