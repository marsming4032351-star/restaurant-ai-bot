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

```bash
python3 run_daily_report.py --image "/Users/ming/Desktop/临时/马连道/xxx.png" --store 便宜坊马连道 --date 2026-05-29
```

如果不传 `--image`，脚本会自动使用 `/Users/ming/Desktop/临时/马连道` 文件夹中最近修改的一张 `png/jpg/jpeg/webp` 图片：

```bash
python3 run_daily_report.py --store 便宜坊马连道 --date 2026-05-29
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
- 不改 `main.py` / `weekly_report.py` 的核心业务逻辑。
- `data/store_history.csv` 仍由 `main.run()` 写入，保持现有重复保护逻辑。

---

## Workflow 2：每周一自动生成上周周报

### 目标

每周一自动统计上一完整自然周的经营数据，并推送飞书周报卡片。

### 输入

- `data/store_history.csv`

### 处理

1. 确定统计范围。
   - 使用 `weekly_report.py --last-week`。
   - 固定统计上周一到上周日，不等同于最近 7 天。

2. 读取历史数据。
   - 从 `store_history.csv` 中筛选指定门店和日期范围。
   - 若范围内没有数据，停止并提示先积累日报。

3. 计算 KPI。
   - 本周总收入。
   - 日均收入。
   - 总来客数。
   - 平均客单价。
   - 最高收入日和最低收入日。
   - 平均折扣率。
   - 烤鸭周销量和日均销量。

4. 识别异常。
   - 统计健康、警示、异常天数。
   - 标记折扣率高于阈值的日期。
   - 根据历史日报中的 warning_level 汇总周度风险。

5. 生成经营建议。
   - 调用 LLM 生成本周主要问题、下周建议、趋势总结和重点关注指标。

6. 推送飞书周报卡片。
   - 手动运行：`python3 weekly_report.py --last-week`。
   - 验证不推送：`python3 weekly_report.py --last-week --dry-run`。
   - cron 触发脚本：`scripts/run_weekly.sh`。

### 输出

- 飞书周报互动卡片。
- `logs/weekly_report.log` 运行日志。
- cron 场景下还有 `logs/cron_weekly.log` 标准输出和错误输出。

### 关键约束

- `--last-week` 是上一完整自然周。
- `--dry-run` 不推送飞书，但仍可能调用 LLM。
- 未经确认不写入 crontab。
- 周报质量依赖 `store_history.csv` 的日期覆盖完整度。

---

## Workflow 3：项目健康检查

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
