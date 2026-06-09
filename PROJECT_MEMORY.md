# PROJECT_MEMORY.md
> 每次打开新会话，先读这个文件，再继续开发。
> 新智能体请同时阅读 `docs/AGENT_ONBOARDING.md`。
> 餐饮日报/周报自动化的 Skill 规范（输入/规则/输出/验收/禁止事项）见 `docs/SKILLS_SPEC.md`。
> 产品全景图见 `docs/product_panorama.md`，产品体检报告见 `docs/product_health_check.md`。

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
- 2026-06-09 新电脑迁移修复已完成并 push：项目使用独立 `.venv`，launchd watcher 使用 `.venv/bin/python`，2026-06-08 日报已重跑成功并推送飞书，旧的 83 个 watcher 失败日志 commits 已清理。

### 新电脑环境（2026-06-09）

- 项目路径：`/Users/ming/Restaurant/restaurant-ai-bot`
- 日报输入目录：`/Users/ming/Restaurant/daily-input/马连道`
- Python 虚拟环境：`/Users/ming/Restaurant/restaurant-ai-bot/.venv/bin/python`
- launchd watcher：`~/Library/LaunchAgents/com.restaurant.daily-watcher.plist` 的 `ProgramArguments` 使用项目 `.venv/bin/python` 执行 `watch_daily_folder.py`
- 当前本机代理端口：`127.0.0.1:7890`
- 旧代理端口 `127.0.0.1:7897` 曾导致 `fetch/push` 失败，不要继续误用

进入项目后的最小健康检查：

```bash
git status
which python
.venv/bin/python -c "import openai, pydantic, pydantic_core, pandas, PIL"
scripts/status_watcher_launchd.sh
git config --get http.proxy
git config --get https.proxy
```

Git 远程操作如需代理，优先使用临时 `7890` 代理，不修改全局配置：

```bash
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 fetch origin main
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push origin main
```

watcher 自动流程不应自动 `git commit` / `git push`。Git 提交、推送必须由用户确认后执行，且只能 `git add <具体文件>`。

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
- [x] `run_daily_report.py`：一键处理截图 → Excel → 日报 → 飞书 → pipeline 状态；Git commit/push 必须由用户确认后执行
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
- [x] 当前监听服务已重载到 `/Users/ming/Restaurant/daily-input/马连道`，并使用项目 `.venv/bin/python`；历史日志中可能仍有旧 Desktop 路径残留，但不再新增

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

当前新电脑 watcher 使用：

```text
/Users/ming/Restaurant/restaurant-ai-bot/.venv/bin/python
```

若 `scripts/status_watcher_launchd.sh` 或 plist 显示 `/usr/bin/python3`，需要重新执行 `scripts/install_watcher_launchd.sh` 重载。

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

看板默认只生成 HTML/PNG，不调用飞书。需要发送到飞书群时显式增加 `--send-to-feishu`；脚本会在 PNG 生成成功后复用现有 `feishu_bot` 推送标题、说明和看板图片，PNG 不存在或图片上传配置不可用时会报错中止，且不输出任何 `.env`、webhook、token 或 app secret。

#### 2026-06-01 周报看板字段增强器

`skills/weekly_dashboard/render_weekly_dashboard.py` 已新增 `weekly field enhancer`，优先读取 `output/report_*.json` 的日报结构化字段，再结合 `field_map.yaml` 和 `store_history.csv` 生成更完整的周经营看板。当前看板不仅展示营业额，还会展示经营结构、客流、客单价、会员活动、关键品类销量、烤鸭专项和底部经营诊断。

字段缺失时系统会降级显示为 `暂无` 或直接隐藏模块，不会伪造数据，也不会修改历史业务日期。周一自动触发周报时，`weekly_auto.py` 会沿用这一版增强看板；如果本机配置了图片上传凭证，会尝试同步推送到飞书群。

#### 2026-06-01 周报看板飞书图片推送经验

本次 `2026-05-25` 到 `2026-05-31` 周报看板图片已成功推送到飞书。关键经验：

- Codex 环境可能无法访问 Mac 本机代理；当前新电脑代理端口是 `127.0.0.1:7890`，旧端口 `127.0.0.1:7897` 不要再用。
- 推送前 `.env` 需要配置 `FEISHU_WEBHOOK`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET`，但任何文档、日志和提交信息都不得记录真实值。
- 如果 Python `requests` 无法解析 `open.feishu.cn`，但 `curl` 可以访问，优先怀疑 Python 代理或 DNS 路径问题。
- 本机 Terminal 执行前可设置：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

成功命令示例：

```bash
python3 skills/weekly_dashboard/render_weekly_dashboard.py \
  --store "便宜坊马连道" \
  --start-date 2026-05-25 \
  --end-date 2026-05-31 \
  --send-to-feishu
```

禁止记录任何真实 webhook、App Secret、token 或 `image_key`。

---

## 13. 2026-06-01 周报标准升级：经营大屏 + 管理诊断长图版（V1，已固定）

周报默认看板标准已正式升级并**固定为 V1**：**“经营大屏 + 管理诊断”长图版**。

### 标准定义（不再随意增删模块）

- 入口脚本：`scripts/render_manager_weekly_fusion.py`
- 产物 1：**完整 HTML**——固定 1600px 宽的「长图导出画布」，不依赖浏览器缩放，正文字号大、模块间距足、底部不裁切，用于本地归档和打开查看。
- 产物 2：**高清长图 PNG**——由本机 Chrome 无头模式整页截图导出，用于飞书群推送。
- 固定导出参数（脚本顶部常量 `STANDARD_*`，作为单一事实来源）：
  - `STANDARD_VIEWPORT_WIDTH = 1600`
  - `STANDARD_SCALE = 2`（deviceScaleFactor，高清不压缩）
  - `STANDARD_PNG_ENGINE = "chrome"`
- 固定模块（上半经营大屏 + 下半管理诊断）：核心指标 / 营收趋势×折扣率 / 收入结构 / 客单价 / 渠道收入 / 客流×烤鸭 / 关键品类 TOP / 会员 / 烤鸭专项 / 本周经营判断 / 风险预警 / 经营洞察 / 下周行动建议 / 数据质量说明。

### 长图 PNG 导出机制（Chrome 两遍法）

1. 第一遍 `--headless --dump-dom` 读取 HTML 末尾 `data-page-h`（页面真实 `scrollHeight`）；图表容器高度固定，scrollHeight 稳定。
2. 第二遍 `--window-size=1600,<真实高度+留白> --force-device-scale-factor=2 --screenshot` 整页截图，不裁切、不压缩低清。
3. Chrome 路径自动探测（`_find_chrome`：Google Chrome / Chromium / Edge）。本机无 Chrome 或截图失败时自动退回 PIL 兜底绘制（`--png-engine pil`），保证主流程不中断。
4. ECharts 从 jsdelivr CDN 加载，截图需联网；离线则图表空白但 HTML 仍可归档。

### 默认推送链路与 fallback

- `weekly_auto.py._push_weekly_dashboard`：周一处理完周日日报触发周报时，**默认调用融合版长图脚本**生成 HTML+PNG；`.env` 配了 `FEISHU_APP_ID/SECRET` 时推送高清长图 PNG。
- Fallback 顺序：融合版失败 → 退 PIL 兜底 PNG → 退原 `skills/weekly_dashboard/` 基础看板。原普通周报保留，不删除。

### 数据纪律

- 只读取真实日报数据（`data/store_history.csv` + `output/report_MLD_*.json`），不造数、不改历史数据。
- 7 天完整窗口（history）与结构明细窗口（report JSON）分别标注口径；缺失日期（如 2026-05-25 / 05-28）在 HTML 和 PNG 上均显式标注“结构明细 5/7 天”，不补全、不插值。

### 本地验证（2026-06-01，未推送飞书）

- 区间 2026-05-25~05-31：HTML + 高清长图 PNG 生成成功。
- PNG 实测尺寸 **3200 × 9866**（viewport 1600 / scale 2），整页无裁切，顶部图表→中部品类/会员/烤鸭→底部风险预警/洞察/下周建议/数据质量/footer 全部完整。
- `python3 -m unittest test_weekly_auto.py` 9 个测试通过。

### 默认生成命令

```bash
python3 scripts/render_manager_weekly_fusion.py \
  --store 便宜坊马连道 --start 2026-05-25 --end 2026-05-31
# 推送飞书：追加 --send-to-feishu；只要 HTML：追加 --no-png；更高清：--scale 3
```

## 14. 2026-06-01 数据口径治理：日报升级为「数据资产」

**Why:** 6 月起要做月报、同比、环比。日报不能只是单日记录，必须带齐日期维度、对比基准、来源版本，且严防日期污染。

**How to apply:**
- 日期维度单一真相源 `date_dimension.py`（纯函数派生：business_year/month、自然周、is_workday/holiday、previous_*、MTD 窗口、跨月周）。节假日来自 `data/holiday_calendar_cn.json`（config-driven，不硬编码、不推农历，缺失按周末默认）。
- 富字段入库到**新表** `data/daily_facts.csv`（`daily_facts.py`），**绝不动 `store_history.csv`**，不影响周报标准 V1。字段口径分四层（营收语义/渠道结构/支付结构/折扣结构），不混用。
- 入库防污染：同 store+business_date 默认禁止覆盖（`blocked_duplicate`）；**截图表头日期≠business_date → 硬阻止**（绝不把 05-31 写成 06-01）；`source_image_hash` 命中其它日期告警；与前一天关键指标全等告警；更正需 `mode='amend'+reason`，旧记录备份到 `daily_facts_backup.csv` + 审计 `daily_facts_audit.csv`。
- 月度只读聚合 `monthly_metrics.py`：MTD 累计、上月同期（缺日取上月末，如 3/31→2/28）、环比 MoM、工作日/周末均、最高/最低/异常日。缺失日期不补全、不伪造。
- 集成：`run_daily_report._write_daily_facts_hook` 在日报成功后附加入库 + 打印月度口径提示；**try/except 包裹**，失败不影响 V1 主流程，可整体回退。入库路径以 `config.DATA_DIR` 为准（测试隔离，不污染真实 data/）。

**MTD 数学验证：** 2026-06-01 → MTD=06-01~06-01、上月同期=05-01~05-01、上周同星期=05-25、week=06-01~06-07（周一）；2026-03-31 上月同期夹到 2026-02-28。

**边界（req 15）：** 本次只改代码与文档，不改历史业务数据、不伪造 6 月数据、不推送飞书、不生成正式日报、不影响 V1，可回退。

**文档：** `docs/date_and_metric_policy.md`、`docs/data_schema.md`。

**注意（已知遗留）：** `store_history.csv` 仍有一条 2026-06-01 行（= 05-31 的旧污染重复，本任务不修改历史数据故保留）。明天真实 06-01 日报入主链路时，现有 `store_history_has_row` 守卫会因该行而拦截，需要 `--force` 或先由用户处理该污染行——属于既有数据问题，不在本次代码改造范围。
