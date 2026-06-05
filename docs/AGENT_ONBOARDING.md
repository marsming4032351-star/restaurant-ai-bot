# AGENT_ONBOARDING.md
> 新进入本项目的 Claude / Codex / 其他智能体必读。
> 读完再行动，不要一上来就重写代码。
> 业务规则速查见餐饮日报/周报自动化 Skill 规范：`docs/SKILLS_SPEC.md`。

---

## 零、入场阅读顺序

1. `README.md`
2. `PROJECT_MEMORY.md`
3. `docs/product_panorama.md`（产品全景图）
4. `docs/product_health_check.md`（产品体检报告）
5. 涉及数据字段时读 `docs/data_schema.md`
6. 涉及 skill 修改时读 `docs/SKILLS_SPEC.md`

**红线（务必遵守）：**
- 不要读取、打印或提交 `.env`。
- 不要提交 `output/`、真实业务数据、Excel、备份文件（`*.bak*` / `*.pollution_bak*`）。
- 不要用 `git add -A`；改代码前先 `git status --short`，再按文件名精确 `git add`。
- 日报业务日期必须来自图片表头识别日期，禁止用系统日期或文件时间。
- 天气 API 失败不能阻断日报/周报主流程（附加层 try/except，失败降级"暂无"）。

---

## 一、项目目标

**餐厅经营日报数据 → 结构化沉淀 → 飞书日报/周报自动推送**

这是 CaiHub 餐饮经营数据闭环的早期模块，不是单纯的图片转 Excel 工具。

核心价值链：
```
日报截图
  → Claude 读图 → JSON
  → image_to_excel.py → 标准 Excel
  → main.py → AI 诊断 → 飞书日报卡片
           → store_history.csv（历史沉淀）
  → weekly_report.py → 飞书周报卡片（周一处理上周日日报成功后自动触发）
```

---

## 二、当前文件结构

```
restaurant-ai-bot/
├── main.py               # 日报主入口
├── parser.py             # Excel 解析（关键字定位法）
├── analyst.py            # LLM 诊断（返回结构化 JSON）
├── visualizer.py         # matplotlib 出图（4 张）
├── feishu_bot.py         # 飞书互动卡片推送
├── history.py            # CSV 历史数据读写
├── weekly_report.py      # 周报生成 + 推送
├── image_to_excel.py     # JSON → 标准 Excel
├── config.py             # 从 .env 读取所有凭证
├── field_map.yaml        # 字段映射配置
├── prompts/diagnose.txt  # 日报诊断 prompt
├── scripts/
│   └── run_weekly.sh     # 手动/兼容入口：生成上周周报
├── data/
│   ├── store_history.csv # ★ 核心历史数据（只追加，不覆盖）
│   ├── data_schema.json  # 字段定义 + 告警阈值
│   └── sample_data.json  # 测试数据
├── output/               # 分析图 + JSON 留档（可重新生成）
├── logs/                 # 运行日志（不要删除此目录）
├── raw_images/           # 日报截图原图
├── .env                  # 本地凭证（不提交 git）
└── docs/
    └── AGENT_ONBOARDING.md  # 本文件
```

---

## 三、核心脚本说明

| 脚本 | 作用 | 常用命令 |
|------|------|---------|
| `main.py` | 日报全流程 | `python3 main.py --file data/便宜坊马连道_2026-05-26.xlsx` |
| `weekly_report.py` | 周报生成 | `python3 weekly_report.py --last-week` |
| `image_to_excel.py` | JSON → Excel | `python3 image_to_excel.py --date 2026-05-28 --json '{...}'` |
| `history.py` | 查看历史 | `python3 -c "import history; history.show_recent(7)"` |
| `scripts/run_weekly.sh` | 手动/兼容入口 | 当前主链路不依赖 crontab |

---

## 四、日报流程

```
1. 把日报截图发给 Claude
2. Claude 输出 JSON（注意重复字段加前缀：烤鸭_月累计、套餐_日累计）
3. python3 image_to_excel.py --date YYYY-MM-DD --json '{...}'
4. python3 main.py --file data/便宜坊马连道_YYYY-MM-DD.xlsx
   → 推送飞书互动卡片
   → 追加数据到 data/store_history.csv
```

---

## 五、周报流程

```
# 手动生成上周周报
python3 weekly_report.py --last-week

# 验证统计范围（不推送飞书）
python3 weekly_report.py --last-week --dry-run

# 自动化：周一处理上一天（周日）日报并推送成功后触发
```

**重要**：`--last-week` 固定统计「上周一～上周日」，不是最近 7 天。
- 今天 2026-06-01（周一）→ 统计 2026-05-25 ～ 2026-05-31
- 今天 2026-06-03（周三）→ 统计 2026-05-25 ～ 2026-05-31（不变）

---

## 六、历史数据文件说明

`data/store_history.csv` 是整个系统的核心数据资产。

**字段**：
```
date, store_name, revenue, customer_count, avg_ticket,
month_yoy, discount_rate, dine_in_ratio, takeaway_ratio,
roast_duck_sales, warning_level, summary, suggestions
```

详细字段说明见 `data/data_schema.json`。

**当前状态**：有 3 行数据（2026-05-24 / 25 / 26）。

**写入规则**：
- 每次 `main.py` 运行后自动追加
- 同天同店重复时：交互模式提示 y/n，cron 模式自动跳过
- `--force` 参数可强制覆盖

---

## 七、飞书 Webhook 注意事项

- Webhook 地址在 `.env` 的 `FEISHU_WEBHOOK` 字段
- **不要打印 `.env` 内容**，不要把 webhook 地址写进代码
- 自定义机器人安全设置关键词为 `日报`，所有消息必须含此词
- 发图片需要额外配置 `FEISHU_APP_ID` + `FEISHU_APP_SECRET`（当前未配置，图片存本地）
- 如果推送失败，先检查日报监听日志和 `logs/weekly_report.log`

---

## 八、定时任务说明

当前主链路不依赖 crontab，也不固定周一 9 点。`scripts/run_weekly.sh` 只作为手动/兼容入口保留。

**只读检查 crontab**：
```bash
crontab -l
```

**日志位置**：
- 周报运行详情：`logs/weekly_report.log`
- cron 系统日志：`logs/cron_weekly.log`

**确认推送成功**：
```bash
tail -20 logs/weekly_report.log
# 成功标志：[weekly] ✅ 周报已推送到飞书群
```

---

## 九、下次开发建议

按优先级排序：

1. **持续积累日报数据**：每天手动跑 `main.py`，让 CSV 数据充足后周报分析才有价值
2. **确认日报监听状态**：查看 launchd watcher 是否 running，确认日报成功后进入周报检查
3. **批量导入历史数据**：把 test/0524.png ~ 0526.png 的数据全部写入 CSV
4. **异常规则引擎**：根据 `data_schema.json` 里的阈值做规则告警，减少对 LLM 的依赖
5. **周报趋势图**：在周报卡片中加入 7 日收入曲线（matplotlib → 上传图片）
6. **飞书图片发送**：配置 App 凭证，让 4 张日报分析图发到群里
7. **多店支持**：御炉通明湖店格式不同，需新增字段映射

---

## 十、禁止事项

在未与用户确认前，以下操作**严格禁止**：

| 禁止操作 | 原因 |
|---------|------|
| ❌ 覆盖或删除 `data/store_history.csv` | 核心历史数据，一旦删除无法恢复 |
| ❌ 删除 `logs/` 目录 | 运行日志，用于排查问题 |
| ❌ 打印或输出 `.env` 内容 | 包含 webhook、API Key 等敏感信息 |
| ❌ 直接重写 `main.py` | 已跑通的核心链路，改动需充分测试 |
| ❌ 直接重写 `weekly_report.py` | 周报链路已跑通，改动需先说明方案并验证 |
| ❌ 未经用户确认写入 crontab | 自动化任务影响系统，必须先输出方案确认 |
| ❌ 把真实数据加入 git | 真实经营数据、日志、Excel、图片、parquet 均不应提交 |
| ❌ 把 `--days 7` 等同于 `--last-week` | 前者是「最近 7 天」，后者是「上周一～上周日」，含义不同 |
| ❌ 直接修改 `data/data_schema.json` 的告警阈值 | 阈值变化会影响历史数据的警示判断一致性 |

---

## 十一、快速健康检查（进入项目第一件事）

```bash
# 1. 确认 Git 状态，检查是否有未提交或敏感文件
git status

# 2. 确认历史数据存在
ls -la data/store_history.csv

# 3. 查看最近历史记录
python3 -c "import history; history.show_recent(7)"

# 4. 确认 .env 配置存在（不要打印内容）
ls -la .env

# 5. 验证周报功能（不推送）
python3 weekly_report.py --last-week --dry-run

# 6. 查看 crontab 状态，只读检查，不直接写入
crontab -l
```

进入项目后，修改任何功能前必须先阅读：
- `PROJECT_MEMORY.md`
- `README.md`
- `docs/AGENT_ONBOARDING.md`
- `docs/WORKFLOWS.md`

如果要修改功能，先向用户说明方案、影响范围和验证方式，再动代码。不要打印 `.env` 敏感值，不要直接写入 crontab，不要把真实数据加入 git。

---

## 十二、跨智能体状态共享（必读）

### 启动顺序

任何智能体（Claude Code / Codex / 其他）进入本项目执行日报 workflow，必须按顺序先读：

1. `PROJECT_MEMORY.md`
2. `docs/WORKFLOWS.md`
3. `data/pipeline_state.json` ← **读这个确认当前任务和 next_action**

### 读取 pipeline_state.json

```bash
cat data/pipeline_state.json
```

读取后确认：
- `current_target_date`：本次应处理的日期
- `next_action`：本次应执行的动作
- `last_feishu_pushed`：上一次是否推送成功

### 按需查询 pipeline_log.csv（禁止 cat 全文）

```bash
# 查某一天状态（推送前必须先执行）
grep "2026-05-28" data/pipeline_log.csv

# 查最近5条记录
tail -n 5 data/pipeline_log.csv

# 查所有已推送飞书的记录
grep ",true," data/pipeline_log.csv
```

### 推送飞书前强制检查

```bash
grep "目标日期" data/pipeline_log.csv
```

如果查询结果中 `status=done` 且 `feishu_pushed=true`，**严禁重复推送**，必须向用户确认。

### 任务完成后必须更新两个文件

1. 更新 `data/pipeline_state.json`（覆盖写，保持文件极短）
2. 追加一行到 `data/pipeline_log.csv`（只追加，不覆盖）
3. `updated_by` / `agent` 字段填写实际执行的智能体名称

### next_action 枚举

| 值 | 含义 |
|----|------|
| `process_MMDD_preview_only` | 处理指定日期，生成预览，不推飞书 |
| `process_MMDD_and_push` | 处理指定日期并推飞书 |
| `idle_all_done` | 当前无待处理任务 |
| `manual_review_required` | 需要人工介入后再继续 |
