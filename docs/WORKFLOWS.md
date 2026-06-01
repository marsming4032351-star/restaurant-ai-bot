# WORKFLOWS.md

本文整理当前项目的业务 workflow 与可沉淀 skill。

## Workflow 与 Skill 的区别

**Workflow** 是端到端业务流程，描述“从什么输入开始，经过哪些处理步骤，最终产生什么业务结果”。它通常串联多个脚本、数据文件、人工确认点和外部系统，例如飞书推送。

**Skill** 是可复用能力模块，描述“某一类任务怎么稳定完成”。它可以被多个 workflow 调用，例如报表解析、历史写入、经营分析、飞书卡片生成。

简单说：
- Workflow 关注业务闭环：谁触发、输入是什么、输出给谁。
- Skill 关注能力复用：怎样解析、校验、分析、生成、推送。

---

## Workflow 1：每日经营日报自动推送

### 目标

把单日餐厅经营日报转成结构化数据，沉淀到历史 CSV，并推送飞书经营日报卡片。

### 输入

支持三类输入：
- 日报图片：通常先人工或模型识别成结构化 JSON。
- Excel：标准日报 Excel，如 `data/便宜坊马连道_YYYY-MM-DD.xlsx`。
- daily JSON：结构化日报数据，如 `daily/YYYY-MM-DD.json`。

### 处理

1. 识别或接收日报数据。
   - 图片输入先提取表格字段。
   - JSON 输入先校验必需字段。
   - Excel 输入由 `parser.py` 解析。

2. 校验字段。
   - 核对日期、门店、本日收入、来客数、客单价等核心字段。
   - 检查数值格式、空值、重复日期。
   - 如发现 `date + store_name` 已存在于 `data/store_history.csv`，应先提示，不重复追加。

3. 写入历史。
   - 将核心字段写入 `data/store_history.csv`。
   - 不覆盖已有历史，除非明确使用覆盖流程。
   - 保留既有日期数据。

4. AI 经营分析。
   - `analyst.py` 基于日报结构化数据生成经营诊断 JSON。
   - 输出健康等级、今日总结、诊断维度和明日建议。

5. 生成图表。
   - `visualizer.py` 生成 KPI、收入结构、会员消费、品类等分析图。
   - 图片保存到 `output/`。

6. 生成并推送飞书卡片。
   - `feishu_bot.py` 生成互动卡片。
   - 卡片标题格式：`便宜坊马连道 · YYYY-MM-DD 经营日报`。
   - 若配置飞书 App 凭证，可额外上传图表；否则只推送卡片，图表留存在本地。

### 输出

- 飞书日报互动卡片。
- `data/store_history.csv` 中新增一条历史记录。
- `output/report_<store>_<date>.json` 留档。
- `output/*.png` 图表文件。

### 关键约束

- 不打印 `.env` 敏感内容。
- 不删除或覆盖 `data/store_history.csv`。
- 重复日期先提示，不静默追加。
- 正式推送前可使用 dry-run 或摘要预览确认关键字段。

---

## Workflow 1.1：一键日报截图处理

### 目标

把“截图 → Excel → 日报分析 → 飞书推送 → 状态更新 → git commit/push”固化成一个稳定入口，避免每次让新智能体重新扫描整个仓库或手工串命令。

### 命令

推荐日常用法：先把截图放入默认输入目录，再执行一键日报命令。

```text
/Users/ming/Restaurant/daily-input/马连道
```

```bash
python3 run_daily_report.py --image "/Users/ming/Restaurant/daily-input/马连道/xxx.png" --store 便宜坊马连道
```

如果不传 `--image`，脚本会自动使用 `/Users/ming/Restaurant/daily-input/马连道` 文件夹中最近修改的一张 `png/jpg/jpeg/webp` 图片：

```bash
python3 run_daily_report.py --store 便宜坊马连道
```

如果当天截图放在其他目录，保留手动覆盖能力：

```bash
python3 run_daily_report.py --input-folder "/path/to/screenshots" --store 便宜坊马连道
```

如果要指定某一张截图，`--image` 优先级最高：

```bash
python3 run_daily_report.py --image "/path/to/daily.png" --store 便宜坊马连道
```

### 启动读取

脚本启动时只读取必要上下文，不做全仓库扫描：

1. `PROJECT_MEMORY.md`
2. `docs/WORKFLOWS.md`
3. `data/pipeline_state.json`

随后检查 `data/pipeline_log.csv` 中目标日期和门店是否已经 `status=done` 且 `feishu_pushed=true` 或 `feishu_push_success=true`。如已成功推送，默认跳过；确需重跑时使用 `--force`。

脚本还会只读检查 `data/store_history.csv` 是否已有同日同店记录。若已有记录且未使用 `--force`，会停止并写入失败流水，避免进入交互确认卡住自动流程。

### 处理步骤

1. 调用 OpenAI-compatible vision 模型识别截图，输出 `image_to_excel.py` 所需的扁平 JSON。
2. 复用 `image_to_excel.build_excel()` 生成 `data/便宜坊马连道_YYYY-MM-DD.xlsx`。
3. 复用 `main.run()` 执行日报主链路：解析、AI 诊断、图表生成、飞书推送、写入 `data/store_history.csv`。
4. 成功后更新 `data/pipeline_state.json`：
   - `last_completed_date` 为本次日期。
   - `current_target_date` 推进到下一天。
   - `last_feishu_pushed=true`。
5. 成功后追加 `data/pipeline_log.csv`：
   - `status=done`
   - `feishu_pushed=true`
   - `feishu_push_success=true`
   - `report_file=output/report_MLD_YYYY-MM-DD.json`
6. 自动执行指定文件提交和推送：

```bash
git add data/pipeline_state.json data/pipeline_log.csv
git commit -m "日报推送完成：YYYY-MM-DD 便宜坊马连道"
git push origin main
```

7. 如果本次日报真实日期是周日，自动触发自然周周报条件检查：
   - 周报周期固定为周一到周日。
   - 通过 `weekly_auto.py` 读取 `data/store_history.csv` 中真实存在的日报日期。
   - 如果本周有真实数据，则推送周报。
   - 如果周中缺一天或多天，周报照常推送，并在卡片中标注缺失日期。
   - 如果 `data/weekly_state.json` 已记录该自然周周期，则跳过避免重复。

### 失败处理

如果图片识别、Excel 生成、LLM 诊断、飞书推送或主链路任一步失败，脚本会：

- 追加 `data/pipeline_log.csv` 失败记录。
- 设置 `status=failed`。
- 设置 `feishu_pushed=false`。
- 设置 `feishu_push_success=false`。
- 将错误摘要写入 `error_message`。
- 尝试提交并推送失败流水：

```bash
git add data/pipeline_log.csv
git commit -m "记录日报失败：YYYY-MM-DD 便宜坊马连道"
git push origin main
```

失败时不会把该日期标记为 `last_completed_date`。

### 配置要求

图片识别依赖 OpenAI-compatible vision 接口：

```env
LLM_PROVIDER=openai
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_VISION_MODEL=
```

`LLM_VISION_MODEL` 可选；如果不填，脚本会使用 `LLM_MODEL`。若当前文本模型不支持图片输入，需要在 `.env` 中配置支持视觉识别的模型。

### 安全边界

- 不打印 `.env`。
- 不使用 `git add .` 或 `git add -A`。
- 不提交真实 Excel、图片、日志、parquet、输出图或 `store_history.csv`。
- 不直接写入 crontab。
- 日报业务日期必须来自图片表头/真实营业数据；图片表头日期识别失败时必须中止，不允许 fallback 到系统日期；不允许用系统运行日期、文件创建日期、当前日期覆盖真实数据日期；周一只是周报触发时机，不得覆盖日报日期。
- 不允许为了凑周报或补齐周期而修改日报日期。
- 不改 `main.py` / `weekly_report.py` 的核心业务逻辑。
- `data/store_history.csv` 仍由 `main.run()` 写入，保持现有重复保护逻辑。

---

## Workflow 1.2：后台监听日报截图文件夹

### 目标

让项目持续监听默认截图目录。当 `/Users/ming/Restaurant/daily-input/马连道` 中出现新的 `png/jpg/jpeg/webp` 图片，或已有图片被更新后，自动等待文件写入稳定，再调用 `run_daily_report.py` 完整日报流程。

当前默认输入目录放在项目外部固定路径，避免 macOS 后台 launchd 访问 Desktop 时被隐私权限拦截：

```text
/Users/ming/Restaurant/daily-input/马连道
```

### macOS 开机自动启动

首次安装 launchd 服务：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
scripts/install_watcher_launchd.sh
```

安装脚本会生成：

```text
~/Library/LaunchAgents/com.restaurant.daily-watcher.plist
```

plist 配置：

- `ProgramArguments`: `/usr/bin/python3 /Users/ming/Restaurant/restaurant-ai-bot/watch_daily_folder.py`
- `WorkingDirectory`: `/Users/ming/Restaurant/restaurant-ai-bot`
- `StandardOutPath`: `/Users/ming/Restaurant/restaurant-ai-bot/logs/watch_daily_folder.log`
- `StandardErrorPath`: `/Users/ming/Restaurant/restaurant-ai-bot/logs/watch_daily_folder.log`
- `KeepAlive=true`
- `RunAtLoad=true`

安装脚本会自动创建 `/Users/ming/Restaurant/daily-input/马连道` 和日志目录，并自动 `launchctl unload/load` 或 `bootstrap/kickstart`，让服务立即生效。以后 macOS 登录后会自动监听。

当前机器检查结果：`~/Library/LaunchAgents/com.restaurant.daily-watcher.plist` 已存在，`gui/501/com.restaurant.daily-watcher` 已 loaded/running。若最近日志仍显示旧路径 `/Users/ming/Desktop/临时/马连道` 的 `PermissionError`，说明运行中的服务需要重载；重新执行安装脚本即可刷新 plist 和进程。

查看服务状态：

```bash
scripts/status_watcher_launchd.sh
```

停止并卸载服务：

```bash
scripts/uninstall_watcher_launchd.sh
```

卸载脚本只停止服务并删除 plist，不删除任何业务数据、日志、截图、Excel 或日报文件。

### 手动启动监听

前台运行，适合调试：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
python3 watch_daily_folder.py
```

临时后台运行：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
nohup python3 watch_daily_folder.py >> logs/watch_daily_folder.log 2>&1 &
```

默认参数：

- 监听目录：`/Users/ming/Restaurant/daily-input/马连道`
- 门店：`便宜坊马连道`
- 日期：日报业务日期以图片表头识别结果为准；`--date` 仅作为处理日期参考，不得为了触发周报而伪造或覆盖业务日期
- 去重状态文件：`data/watch_state.json`

也可以手动指定日期或只扫描一次：

```bash
python3 watch_daily_folder.py --once
```

也可以指定其他监听目录：

```bash
python3 watch_daily_folder.py --folder "/path/to/screenshots" --once
```

### 停止监听

前台运行时按：

```bash
Ctrl+C
```

临时后台运行时先查进程，再停止：

```bash
pgrep -fl watch_daily_folder.py
pkill -f watch_daily_folder.py
```

### 去重逻辑

监听脚本会记录每张已处理图片的：

- 文件路径
- 修改时间
- 文件大小
- SHA-256 hash

记录保存在 `data/watch_state.json`。同一张图片如果路径、修改时间、大小和 hash 都没有变化，不会重复触发。图片内容更新后会重新处理。

### 排查错误

1. 查看监听日志：

```bash
tail -50 logs/watch_daily_folder.log
```

或直接运行状态脚本：

```bash
scripts/status_watcher_launchd.sh
```

2. 查看日报 pipeline 流水：

```bash
tail -5 data/pipeline_log.csv
```

3. 如果日报流程失败，`run_daily_report.py` 会在 `data/pipeline_log.csv` 中写入：
   - `status=failed`
   - `feishu_push_success=false`
   - `error_message=<错误摘要>`

4. 如果同一天已经成功推送，`run_daily_report.py` 默认会跳过；需要重跑时手动执行：

```bash
python3 run_daily_report.py --image "/Users/ming/Restaurant/daily-input/马连道/xxx.png" --store 便宜坊马连道 --force
```

5. 如果日志中仍出现 Desktop 权限错误：

```bash
scripts/install_watcher_launchd.sh
scripts/status_watcher_launchd.sh
```

确认 recent log 中不再访问 `/Users/ming/Desktop/临时/马连道`。

### 关键约束

- 监听脚本不改 `main.py`、`weekly_report.py` 或日报主链路。
- 监听脚本只调用 `run_daily_report.py`。
- 监听脚本不直接提交真实图片、Excel、图表、日志或 `store_history.csv`。
- `data/watch_state.json` 是本地运行态去重文件，不进入 Git。

---

## Workflow 2：日报完成后自动触发自然周周报

### 目标

当周一处理上一天（周日）真实日期的日报并成功推送后，自动统计上一自然周经营数据，并推送飞书周报卡片。该流程不依赖 crontab，也不固定周一 9 点。

### 输入

- `data/store_history.csv`
- `data/weekly_state.json`
- 本次日报真实日期
- 当前运行日期

### 处理

1. 判断是否触发。
   - 每次日报处理成功后，读取本次日报真实日期。
   - 如果不是周日，只记录日志，不触发周报。
   - 如果当前运行日不是周一，只记录日志，不触发周报。
   - 如果本次日报真实日期不是当前运行日前一天，只记录日志，不触发周报。
   - 如果当前运行日是周一，且本次日报真实日期是上一天（周日），计算该业务日期所在自然周：周一到周日。
   - 周六日报完成不触发周报。

2. 防重复。
   - 使用 `data/weekly_state.json` 记录已推送周期。
   - 周期 key 格式为 `{store_name}:{start_date}_{end_date}`。
   - 同一个自然周周期只推送一次。

3. 读取历史数据。
   - 从 `store_history.csv` 中筛选指定门店和日期范围。
   - 周报统计必须基于真实存在的日报日期。
   - 若范围内完全没有真实数据，停止并返回 `no_data`。
   - 发送前检查区间内业务日期是否连号。
   - 若周中缺一天或多天，不补造数据，不改日期，不用前后日期补齐。
   - 默认 `STRICT_WEEKLY_DATE_CHECK=false`：继续生成周报，并在卡片开头标注缺失日期。
   - 若 `STRICT_WEEKLY_DATE_CHECK=true`：缺日期则不发送周报，只提示缺失日期。

4. 计算 KPI。
   - 本周总收入。
   - 日均收入。
   - 总来客数。
   - 平均客单价。
   - 最高收入日和最低收入日。
   - 平均折扣率。
   - 烤鸭周销量和日均销量。

5. 识别异常。
   - 统计健康、警示、异常天数。
   - 标记折扣率高于阈值的日期。
   - 根据历史日报中的 warning_level 汇总周度风险。

6. 生成经营建议。
   - 调用 LLM 生成本周主要问题、下周建议、趋势总结和重点关注指标。

7. 推送飞书周报卡片。
   - 自动入口：`run_daily_report.py` 成功后调用 `weekly_auto.check_and_push(...)`。
   - 手动运行：`python3 weekly_report.py --last-week` 或 `python3 weekly_report.py --start YYYY-MM-DD --end YYYY-MM-DD`。
   - 验证不推送：`python3 weekly_report.py --last-week --dry-run`。

8. 记录周报状态。
   - 推送成功后写入 `data/weekly_state.json`。
   - 记录门店、周期、触发日期、推送时间、实际数据天数和缺失日期。

### 输出

- 飞书周报互动卡片。
- 周报卡片中的缺失日期提示，例如：`本周缺失数据：2026-05-28`。
- `data/weekly_state.json` 中新增已推送周期记录。

### 关键约束

- 周报周期固定为自然周：周一到周日。
- 周报触发点是周一处理上一天（周日）真实日报并成功推送日报之后。
- 不使用 crontab，不固定周一 9 点。
- 周六日报完成不触发周报。
- 周一收到并完成上周日日报后，先推送日报，再检查并推送周报。
- `--dry-run` 不推送飞书，但仍可能调用 LLM。
- 未经确认不写入 crontab。
- 日期缺失要如实显示，不补造数据；周报发送前必须执行日期连号检查。
- 周报统计以 `store_history.csv` 中真实存在的日报日期为准。

### 2026-05-31 实现记录

- 新增 `weekly_auto.py`。
- 修改 `run_daily_report.py`：日报完全成功后触发周报条件检查。
- 修改 `weekly_report.py`：支持缺失日期提示。
- 新增 `test_weekly_auto.py`。
- 新增 `data/weekly_state.json`。
- 验证命令：`python3 -m unittest test_run_daily_report.py test_weekly_auto.py`，共 15 个测试 OK。

### 2026-06-01 真实流程验证

本次项目从“能识别日报并推送”升级为“能防止日期污染历史数据，并能在周一收到周日数据后自动触发上周周报”。

已完成工作流约束：
- 日报 `business_date` 只来自图片表头日期。
- 系统当天日期、文件创建日期、监听日期不能覆盖业务日期。
- `processing_date` 只用于日志，不用于日报标题、Excel 文件名、`store_history.csv` 业务日期或 `pipeline_log.csv` 业务日期。
- 图片表头日期识别失败时流程中止，不 fallback 到今天。
- `--date` 与图片表头日期不一致时，以图片表头日期为准，并记录 warning。
- 周报发送前检查自然周日期完整性。
- 默认允许缺失日期时发送周报，但卡片提示缺失日期；`STRICT_WEEKLY_DATE_CHECK=true` 时，缺失日期阻止周报发送。
- 周一收到周日数据图后，先推送周日日报，再自动触发上一周周报。

真实链路结果：
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
- 最新状态提交 commit：`a3a4040`

---

## Workflow 3：周报可视化看板

### 目标

在不改变现有日报、周报推送逻辑的前提下，把已验证过的周报数据渲染成 ECharts 风格经营看板图片，用于飞书汇报和经营复盘。

### 输入

- `data/store_history.csv`
- 显式传入的周报区间：`--start-date` 和 `--end-date`
- 门店名：`--store`

### 处理

1. 读取指定门店在指定周报区间内的真实历史数据。
2. 检查区间内日期是否缺失。
3. 生成深色科技感 HTML 看板和 16:9 PNG 看板。
4. 默认不推送飞书；如后续需要，可用独立 `--push-feishu` 参数，不接入现有 `weekly_auto.py` 主流程。

### 输出

```bash
python3 skills/weekly_dashboard/render_weekly_dashboard.py \
  --store "便宜坊马连道" \
  --start-date 2026-05-25 \
  --end-date 2026-05-31
```

- `output/weekly_dashboard_便宜坊马连道_2026-05-25_2026-05-31.html`
- `output/weekly_dashboard_便宜坊马连道_2026-05-25_2026-05-31.png`

### 关键约束

- 这是周报数据可视化增强层，只读取已验证周报数据。
- 不修改 `store_history.csv`、`pipeline_log.csv` 或任何业务日期。
- 周报区间必须显式传入，不能用系统日期推断。
- 缺失日期必须显示提示，不伪造、不补齐。
- `STRICT_WEEKLY_DATE_CHECK=true` 时，缺失日期会阻止生成推送图片。

---

## Workflow 4：项目健康检查

### 目标

在不改变项目状态的前提下，检查项目是否具备继续运行日报、周报和自动化的基础条件。

### 输入

- 项目核心文件：
  - `README.md`
  - `PROJECT_MEMORY.md`
  - `docs/AGENT_ONBOARDING.md`
  - `docs/WORKFLOWS.md`
- 历史数据：
  - `data/store_history.csv`
- 配置文件：
  - `.env`
- 日志目录：
  - `logs/`
- 定时任务：
  - 当前用户 crontab

### 处理

1. 只读检查文件存在性。
   - 不修改代码。
   - 不创建或删除数据。

2. 检查 `.env` 配置状态。
   - 只确认必要 key 是否存在。
   - 不打印 webhook、API key、secret 等敏感值。

3. 检查 `store_history.csv`。
   - 文件是否存在。
   - 字段是否完整。
   - 最近有哪些日期数据。
   - 是否有重复日期。
   - 是否有空值或异常格式。
   - 当前数据是否足够支撑 `weekly_report.py --last-week` 生成有效周报。

4. 检查周报脚本。
   - 是否支持 `--last-week`。
   - 是否支持 `--dry-run`。
   - `--last-week` 是否统计上周一到上周日。

5. 检查周报 cron 脚本。
   - `scripts/run_weekly.sh` 是否存在。
   - 是否有执行权限。
   - 是否进入正确项目目录。
   - 是否写入 `logs/weekly_report.log`。

6. 检查 `logs/`。
   - 是否存在。
   - 是否可写。

7. 检查 crontab。
   - 只读运行 `crontab -l`。
   - 不写入 crontab。

### 输出

- 项目健康检查报告，包含：
  - 已通过项。
  - 风险项。
  - 当前最应该优先处理的问题。
  - 下一步建议。

### 关键约束

- 不推送飞书。
- 不改代码。
- 不写 crontab。
- 不打印敏感内容。
- 不覆盖或删除历史数据。

---

## 发布与文档同步规则

以后涉及代码变更并需要 `git push` 后，必须主动询问用户：
`是否需要更新技术文档并推送到飞书？`

未经用户确认，不得调用 `lark-cli docs +update`。如果用户确认，需要先生成或更新 `/private/tmp/restaurant-ai-bot-feishu-sync.md`，再追加写入飞书文档。不得读取、打印 `.env`、token、webhook、app secret。

如果只是检查文档，不要修改代码，不要 `git commit`，不要 `git push`。后续推荐新增 `scripts/push-and-feishu-doc.sh`，把 `git push` 和飞书同步确认做成固定脚本。

---

## 当前可沉淀的 Skill 列表

## GitHub 版本管理阶段

当前项目已经进入 GitHub 版本管理阶段，仓库地址：
`https://github.com/marsming4032351-star/restaurant-ai-bot.git`

协作约定：
- 文档变更、代码变更都需要 commit。
- 每次重要功能完成后要更新 `PROJECT_MEMORY.md`。
- 提交前运行 `git status`，确认没有 `.env`、真实经营数据、日志、Excel、图片、parquet 文件进入暂存区。
- 当前仓库用于 CaiHub 餐饮经营数据 Agent 原型的版本管理，后续 Claude / Codex / 新智能体接入时应先读项目文档再改动。

### 报表解析 Skill

将日报图片、Excel 或 daily JSON 转为统一结构化字段。核心能力包括字段识别、日期和门店识别、数值标准化、重复字段前缀处理，以及图片字段和推断字段的来源标注。

### 历史数据写入 Skill

负责把结构化日报安全写入 `data/store_history.csv`。核心能力包括字段校验、重复日期检测、dry-run 校验、追加写入、覆盖保护和历史日期覆盖检查。

### 经营分析 Skill

基于日报结构化数据和历史上下文生成经营诊断。核心能力包括健康等级判断、同比和折扣分析、客流客单分析、收入结构分析、品类洞察和明日建议生成。

### 飞书卡片生成 Skill

将日报或周报分析结果渲染为飞书互动卡片。核心能力包括标题生成、红黄绿状态模板、KPI 列、诊断区域、建议列表、note 提示和可选图片上传。

### 周报统计 Skill

从 `store_history.csv` 中筛选指定自然周数据并计算周报 KPI。核心能力包括上周一到上周日范围计算、收入和客流统计、最高最低日识别、折扣异常识别、烤鸭趋势和 warning_level 汇总。

### 项目健康检查 Skill

按只读原则检查项目可运行状态。核心能力包括核心文件检查、CSV 字段和质量检查、`.env` 配置存在性检查、日志目录检查、周报 dry-run 检查和 crontab 只读检查。

### 故障自愈 Skill

当日报或周报流程失败时定位并恢复。核心能力包括依赖缺失识别、网络或 LLM 调用失败判断、重复日期保护、date 序列化问题处理、飞书推送失败排查和“修复后重跑”的最小化操作建议。
