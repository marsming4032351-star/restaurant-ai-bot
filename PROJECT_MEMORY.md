# PROJECT_MEMORY.md
> 每次打开新会话，先读这个文件，再继续开发。
> 新智能体请同时阅读 `docs/AGENT_ONBOARDING.md`。

---

## 1. 项目定位

这是一个**"餐厅经营日报数据 → 结构化沉淀 → 飞书日报/周报自动推送"**的经营数据 Agent 原型。

当前不是单纯的图片转 Excel，而是 **CaiHub 餐饮经营数据闭环**的早期模块：
- 数据采集（截图 → Excel）
- 数据沉淀（CSV 历史记录）
- AI 诊断（日报 + 周报）
- 自动推送（飞书互动卡片）
- 自动化（launchd 日报监听 + 周一处理上一天周日日报成功后自动触发上一自然周周报）

详细 workflow 见 `docs/WORKFLOWS.md`。

当前仓库用于 **CaiHub 餐饮经营数据 Agent 原型** 的版本管理。

GitHub private repo：
`https://github.com/marsming4032351-star/restaurant-ai-bot.git`

Git 状态：
- 已完成本地 Git 初始化。
- 已完成首次安全提交。
- 已 push 到 GitHub private repo。
- `.env`、真实 `store_history.csv`、真实日报 JSON、`logs/`、Excel、parquet、输出图均已通过 `.gitignore` 排除。

---

## 2. 技术栈 & 目录结构

```
restaurant-ai-bot/
├── main.py               # 主入口：解析 → AI 诊断 → 出图 → 飞书推送 → 写历史
├── parser.py             # 第1层：关键字定位法读二维 Excel 日报
├── analyst.py            # 第2层：调 LLM 输出结构化诊断 JSON
├── visualizer.py         # 第3层：matplotlib 出 4 张分析图（中文字体已修复）
├── feishu_bot.py         # 第4层：飞书互动卡片推送（webhook + 可选 App 上传图片）
├── history.py            # 历史数据管理：追加/查重/展示 store_history.csv
├── weekly_report.py      # 周报生成器：读 CSV → 统计 → AI → 飞书推送
├── weekly_auto.py        # 周报自动触发：周一处理上一天周日日报成功后检查并推送上一自然周周报
├── image_to_excel.py     # 辅助：Claude 读图后的 JSON → 标准 Excel
├── run_daily_report.py   # 一键日报：截图 → 识别 → Excel → 飞书 → pipeline 状态
├── watch_daily_folder.py # 监听截图目录，自动触发一键日报
├── config.py             # 凭证 & 路径（从 .env 读）
├── field_map.yaml        # 字段映射：中文表头 → 标准字段名
├── prompts/diagnose.txt  # 日报 AI 诊断 prompt（连锁餐饮 5 步分析法）
├── scripts/
│   ├── install_watcher_launchd.sh   # 安装/重载 macOS 开机监听服务
│   ├── status_watcher_launchd.sh    # 查看监听服务、进程和日志
│   ├── uninstall_watcher_launchd.sh # 卸载监听服务
│   └── run_weekly.sh                # 手动/兼容脚本：生成上周周报（当前不依赖 crontab）
├── data/
│   ├── store_history.csv # ★ 核心历史数据（不要手动删改）
│   ├── weekly_state.json # 周报周期防重复状态
│   ├── data_schema.json  # 字段定义 + 告警阈值
│   ├── sample_data.json  # 3 天测试数据
│   └── 便宜坊马连道_YYYY-MM-DD.xlsx  # 日报 Excel（按日期命名）
├── output/               # 生成的 4 张分析图 + report JSON（可重新生成）
├── logs/                 # 运行日志（不要删除）
├── raw_images/           # 早期日报截图原图；当前默认输入目录已迁到项目外
├── test/                 # 测试图片 0524～0527.png
├── .backup_v2/           # v2 关键文件快照（备份勿动）
├── .env                  # 本地凭证（不提交 git，不打印内容）
├── .env.example          # 配置模板
├── docs/
│   └── AGENT_ONBOARDING.md  # 智能体接入说明
├── PROJECT_MEMORY.md     # 本文件
└── README.md             # 项目运行说明
```

**核心依赖**：`openpyxl`, `pandas`, `matplotlib`, `openai`, `requests`, `python-dotenv`, `pyyaml`, `pyarrow`, `Pillow`

---

## 3. 关键配置（.env）

```env
# 必填：飞书自定义机器人 webhook（群机器人，关键词：日报）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...

# 可选：飞书自建 App 凭证（填了才能发图片，否则图片只存 output/）
FEISHU_APP_ID=
FEISHU_APP_SECRET=

# LLM（当前用阿里百炼 qwen3.6-plus，兼容 OpenAI 协议）
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_MODEL=qwen3.6-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

## 4. 当前已完成

### 日报
- [x] `main.py` 端到端跑通：Excel → 解析 → AI 诊断 → 出图 → 飞书推送
- [x] 飞书互动卡片：红/黄/绿标题 + KPI 4 列 + 诊断 2×2 + 建议列表
- [x] matplotlib 中文字体修复（Arial Unicode MS / STHeiti）
- [x] `image_to_excel.py`：Claude 读图 → JSON → 标准 Excel
- [x] `run_daily_report.py`：一键处理截图 → Excel → 日报 → 飞书 → pipeline 状态 → git commit/push
- [x] `watch_daily_folder.py`：监听 `/Users/ming/Restaurant/daily-input/马连道` 新截图并自动触发一键日报
- [x] 默认日报截图输入目录已迁出 Desktop：`/Users/ming/Restaurant/daily-input/马连道`
- [x] 日报业务日期必须来自图片表头/真实营业数据；图片表头日期识别失败时必须中止；不允许为了凑周报或补齐日期改写日报日期，也不允许用系统运行日期、文件创建日期、当前日期覆盖真实数据日期
- [x] `run_daily_report.py --input-folder` 和 `watch_daily_folder.py --folder` 保留手动目录覆盖能力
- [x] `scripts/install_watcher_launchd.sh` 会自动创建截图输入目录和日志目录
- [x] 每次运行后自动追加数据到 `data/store_history.csv`
- [x] 历史数据重复检测（同天同店提示 y/n，cron 模式自动跳过）

### 周报
- [x] `weekly_report.py` 完成：读 CSV → 统计 → AI 分析 → 飞书互动卡片
- [x] 支持 `--last-week` 参数：固定统计「上周一～上周日」
- [x] `weekly_auto.py` 完成：周一处理上一天周日日报成功后自动触发上一自然周周报
- [x] 周报周期固定为自然周（周一到周日），不依赖 crontab，不固定周一 9 点
- [x] 周六日报完成不触发周报；周一收到并完成上周日日报后，先推送日报，再检查并推送周报
- [x] 周报发送前执行日期连号检查；缺一天或多天时默认照常推送，并在卡片开头醒目标注缺失日期；不伪造数据
- [x] `data/weekly_state.json` 记录已推送自然周周期，避免重复推送
- [x] 周报统计以 `data/store_history.csv` 中真实存在的日报日期为准
- [x] 支持 `--dry-run`：只打印卡片 JSON，不推送
- [x] `scripts/run_weekly.sh` 已创建，有可执行权限（当前作为手动/兼容入口，不作为主自动化依赖）
- [x] `skills/weekly_dashboard/` 完成：独立读取已验证周报数据，生成 ECharts 风格 HTML/PNG 看板，不改变现有日报/周报业务逻辑

### 自动化
- [x] 周报自动化已改为日报成功后的条件触发，不使用 crontab
- [x] launchd 日报监听脚本已具备安装、状态查看、卸载能力
- [x] 当前机器上 `com.restaurant.daily-watcher` plist 已存在且服务处于 loaded/running
- [x] 当前监听服务已重载到 `/Users/ming/Restaurant/daily-input/马连道`；历史日志中可能仍有旧 Desktop 路径残留，但不再新增

### 数据文件与状态
- [x] `data/data_schema.json`：字段定义 + 告警阈值
- [x] `data/sample_data.json`：3 天真实测试数据（0524/0525/0526）
- [x] `data/pipeline_state.json`：当前目标日期 `2026-05-31`，最后完成日期 `2026-05-30`
- [x] `data/pipeline_log.csv`：最近成功流水覆盖到 `2026-05-30`
- [x] `data/store_history.csv`：核心历史数据持续追加，由日报主链路维护
- [x] `data/weekly_state.json`：自然周周报防重复状态

---

## 5. 自动化配置状态

### launchd（日报截图文件夹监听）

默认截图输入目录：

```text
/Users/ming/Restaurant/daily-input/马连道
```

安装或重载：

```bash
scripts/install_watcher_launchd.sh
```

查看状态、进程和最近日志：

```bash
scripts/status_watcher_launchd.sh
```

停止并卸载：

```bash
scripts/uninstall_watcher_launchd.sh
```

当前状态：`com.restaurant.daily-watcher` 已安装并 loaded/running。因为之前服务曾使用 Desktop 路径，若日志继续出现 `PermissionError: Operation not permitted: '/Users/ming/Desktop/临时/马连道'`，重新执行安装脚本即可让 launchd 重载新版默认目录。

### 周报自动触发（不依赖 crontab）

当前周报自动化不再固定周一 9 点，也不要求写入 crontab。规则是：

- 周报周期固定为自然周：周一到周日。
- 当周一处理上一天（周日）真实日报并成功推送日报后，`run_daily_report.py` 会调用 `weekly_auto.check_and_push(...)`。
- 周六日报完成不触发周报。
- 周一收到并完成上周日日报后，先推送日报，再检查并推送上一自然周周报。
- 如果周中缺一天或多天，周报照常发送，但卡片中必须标注缺失日期。
- 同一个自然周周期只推送一次，通过 `data/weekly_state.json` 防重复。
- 周报统计只基于 `data/store_history.csv` 中真实存在的日报日期。

`scripts/run_weekly.sh` 仍保留为手动/兼容入口，但不再作为当前主自动化依赖。

---

## 6. 当前已知问题

| 问题 | 状态 |
|------|------|
| 截图来源已自动监听，但仍依赖视觉模型识别截图字段 | 持续优化 |
| 4 张分析图未发到飞书（需配置 App 凭证） | 待解决 |
| 0527.png（御炉通明湖）格式完全不同，尚未适配 | 待解决 |
| 部分字段偶尔为空（回收100元代金券数量等）parser 报 warning | 低优先级 |
| 当前 launchd 日志中可能仍有旧 Desktop 权限错误历史残留 | 只要日志行数不再增长即可 |

---

## 7. 跨智能体状态共享机制

### 核心原则

- 项目状态不能依赖 Claude、Codex 或任何智能体的私有记忆系统。
- 跨智能体共享状态必须写进项目本身的文件。
- 任何智能体进入项目执行日报 workflow，必须先读状态文件，再开始执行。

### 两层结构

| 文件 | 用途 | 读取规则 |
|------|------|---------|
| `data/pipeline_state.json` | 当前轻量状态，每次进入项目必读 | 全文读取（文件极短） |
| `data/pipeline_log.csv` | 完整历史流水账 | 按需 grep/tail，**禁止 cat 全文** |

### 强制启动检查顺序

任何智能体进入本项目，必须按顺序先读：

1. `PROJECT_MEMORY.md`
2. `docs/WORKFLOWS.md`
3. `data/pipeline_state.json`

然后只按需查询 `data/pipeline_log.csv`。

### 推送飞书前必须检查

```bash
grep "目标日期" data/pipeline_log.csv
```

如果该行 `status=done` 且 `feishu_pushed=true`，**严禁重复推送**，需向用户确认后才能继续。

### 状态更新规则

- 每次任务开始前：读 `pipeline_state.json` 确认 `next_action`
- 每次任务完成后：同时更新 `pipeline_state.json` + 追加 `pipeline_log.csv` 一行
- `updated_by` 必须填写执行的智能体名称（`claude-code` / `codex` / `human`）
- 不得在任何状态文件中写入 webhook、token、手机号、营业敏感明细

---

## 8. 发布与文档同步规则

以后涉及代码变更并需要 `git push` 后，必须主动询问用户：
`是否需要更新技术文档并推送到飞书？`

未经用户确认，不得调用 `lark-cli docs +update`。如果用户确认，需要先生成或更新 `/private/tmp/restaurant-ai-bot-feishu-sync.md`，再追加写入飞书文档。不得读取、打印 `.env`、token、webhook、app secret。

如果只是检查文档，不要修改代码，不要 `git commit`，不要 `git push`。后续推荐新增 `scripts/push-and-feishu-doc.sh`，把 `git push` 和飞书同步确认做成固定脚本。

---

## 9. 2026-05-31 更新：日报完成后自动触发自然周周报

本次核心代码已提交并推送：`fb78e65 新增周日报后自动推送自然周周报`。

### 本次改动目标

把周报自动化从“依赖周一 9 点 crontab”改成“日报成功后的业务条件触发”：当周一处理上一天（周日）真实日报并成功推送日报后，立即推送上一自然周周报。

### 最终业务规则

- 日报截图日常放入 `/Users/ming/Restaurant/daily-input/马连道`。
- LaunchAgent 监听服务自动识别图片并执行 `run_daily_report.py`。
- 日报链路自动生成 Excel、JSON、飞书日报卡片，并追加 `data/store_history.csv`。
- 日报业务日期必须来自图片表头/真实营业数据。
- 图片表头日期识别失败时必须中止，不允许 fallback 到系统日期。
- 不允许为了凑周报或补齐日期而修改日报日期。
- 不允许用系统运行日期、文件创建日期、当前日期覆盖真实数据日期。
- 周一只是周报触发时机，不得覆盖日报业务日期。
- 周报周期固定为自然周：周一到周日。
- 不使用 crontab，不固定周一 9 点。
- 周六日报完成不触发周报。
- 周一收到并完成上周日日报后，先推送日报，再检查并推送上一自然周周报。
- 周报发送前必须检查区间内业务日期是否连号。
- 如果周中缺一天或多天，默认照常推送，并在卡片开头醒目标注缺失日期；如配置 `STRICT_WEEKLY_DATE_CHECK=true`，则缺日期时停止推送。
- 缺日期时不伪造、不补齐、不用前后日期替代。
- 同一个自然周周期只推送一次，通过 `data/weekly_state.json` 防重复。
- 周报统计以 `data/store_history.csv` 中真实存在的日报日期为准。

### 新增/修改文件

- `weekly_auto.py`
- `weekly_report.py`
- `run_daily_report.py`
- `test_weekly_auto.py`
- `data/weekly_state.json`

### 验证结果

- `python3 -m unittest test_run_daily_report.py test_weekly_auto.py` 通过。
- 共 15 个测试 OK。
- `python3 -m py_compile weekly_auto.py weekly_report.py run_daily_report.py test_weekly_auto.py` 通过。
- 不需要重启监听服务，因为 `watch_daily_folder.py` 没有改。
- 下一次周一收到上周日真实日报图片并成功推送日报后，会自动触发上一自然周周报。

---

## 10. 2026-06-01 日报/周报日期校验增强与真实流程验证

本次项目能力从“能识别日报并推送”升级为“能防止日期污染历史数据，并能在周一收到周日数据后自动触发上周周报”。

已完成能力：
- 日报 `business_date` 只来自图片表头日期。
- 系统当天日期、文件创建日期、监听日期不能覆盖业务日期。
- `processing_date` 只用于日志，不用于日报标题、Excel 文件名、`store_history.csv` 业务日期、`pipeline_log.csv` 业务日期。
- 图片表头日期识别失败时流程中止，不 fallback 到今天。
- `--date` 与图片表头日期不一致时，以图片表头日期为准，并记录 warning。
- 周报发送前检查自然周日期完整性。
- 默认允许缺失日期时发送周报，但卡片提示缺失日期。
- `STRICT_WEEKLY_DATE_CHECK=true` 时，缺失日期会阻止周报发送。
- 周一收到周日数据图后，先推送周日日报，再自动触发上一周周报。

真实流程验证结果：
- 图片表头日期：`2026-05-31`
- 日报推送：成功
- 日报标题：`便宜坊马连道 · 2026-05-31 经营日报`
- Excel 文件：`data/便宜坊马连道_2026-05-31.xlsx`
- Excel 表头日期：`2026 年 5 月 31 日`
- 周报触发：已触发并推送成功
- 周报统计区间：`2026-05-25` 到 `2026-05-31`
- 周报天数：`7`
- 缺失日期：无
- `date_check_status=complete`
- `pipeline_log.csv`：`business_date=2026-05-31`，`processing_date=2026-06-01`，`source_date_from_image=2026-05-31`，`date_validation_status=warning_processing_date_differs`
- git status：干净
- 最新状态提交 commit：`a3a4040`

---

## 11. 下一步任务（优先级排序）

1. **持续积累日报数据**：每天把真实截图放入 `/Users/ming/Restaurant/daily-input/马连道`
2. **标准化输入**：支持从 `daily/` 文件夹批量处理多日截图
3. **异常规则引擎**：基于 `data_schema.json` 里的阈值，自动判断告警级别
4. **趋势分析图**：周报加上 7 日收入曲线图
5. **飞书图片推送**：配置自建 App `im:resource` 权限
6. **多店支持**：适配御炉通明湖店（不同字段格式）

---

## 12. 工作约定

- **日报运行**：`python3 main.py --file data/便宜坊马连道_YYYY-MM-DD.xlsx`
- **周报运行**：`python3 weekly_report.py --last-week`
- **验证（不推送）**：`python3 weekly_report.py --last-week --dry-run`
- **周报看板**：`python3 skills/weekly_dashboard/render_weekly_dashboard.py --store "便宜坊马连道" --start-date YYYY-MM-DD --end-date YYYY-MM-DD`
- **读图流程**：截图 → 发给 Claude → Claude 输出 JSON → `image_to_excel.py --date YYYY-MM-DD --json '...'`
- **一键截图日报**：截图默认放 `/Users/ming/Restaurant/daily-input/马连道`，运行 `python3 run_daily_report.py --store 便宜坊马连道`，业务日期以图片表头为准
- **指定输入目录**：`python3 run_daily_report.py --input-folder "/path/to/screenshots" --store 便宜坊马连道`，业务日期以图片表头为准
- **监听截图文件夹**：`nohup python3 watch_daily_folder.py >> logs/watch_daily_folder.log 2>&1 &`
- **安装开机自动监听**：`scripts/install_watcher_launchd.sh`
- **查看/卸载监听服务**：`scripts/status_watcher_launchd.sh` / `scripts/uninstall_watcher_launchd.sh`
- **重复字段前缀**：`烤鸭_月累计`、`套餐_日累计`、`鱼类_月累计` 等
- **备份**：`.backup_v2/` 是 v2 版本快照，不要删除
- **敏感信息**：`.env` 内容不要打印或提交到 git

### 周报可视化看板 Skill

`skills/weekly_dashboard/` 是“周报数据可视化增强层”。它只读取 `store_history.csv` 中已验证的周报区间数据，生成：
- `output/weekly_dashboard_<store_name>_<start_date>_<end_date>.html`
- `output/weekly_dashboard_<store_name>_<start_date>_<end_date>.png`

该 skill 不修改业务数据、不覆盖日期、不接入 `weekly_auto.py` 主流程。周报区间必须显式传入，不能用系统日期推断；缺失日期会显示在看板中，`STRICT_WEEKLY_DATE_CHECK=true` 时缺失日期会阻止生成推送图片。
