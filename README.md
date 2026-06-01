> 🤖 **新进入本项目的智能体，请先阅读 `PROJECT_MEMORY.md` 与 `docs/AGENT_ONBOARDING.md`。**

# 便宜坊日报助手

餐厅经营日报截图 / Excel → AI 分析 → 飞书互动卡片自动推送。

把每天的日报截图交给 Claude 读取数字，生成标准 Excel，再一条命令跑出带 KPI、诊断、建议的飞书卡片。

GitHub private repo：
`https://github.com/marsming4032351-star/restaurant-ai-bot.git`

项目当前能力：
- 日报推送
- 历史数据沉淀
- 周报生成
- 飞书卡片推送
- 一键截图日报
- 文件夹自动监听日报
- macOS launchd 开机自动监听
- 周一处理上一天周日日报完成后自动触发上一自然周周报
- workflow 文档
- 智能体接入文档

新开发者 / 新智能体进入项目后的第一步：
先读 `PROJECT_MEMORY.md`、`README.md`、`docs/AGENT_ONBOARDING.md`、`docs/WORKFLOWS.md`。

---

## 1. 项目用途

- **输入**：日报截图（PNG）或已有 Excel
- **处理**：解析字段 → 调千问 / Claude 生成经营诊断 → matplotlib 出 4 张分析图
- **输出**：推送到飞书群的互动卡片，含标题色块、KPI 数据、AI 分析、明日建议

最终目标：做成 CaiHub 餐饮经营数据日报 Agent 的雏形，支持多店、自动异常预警、趋势分析。

详细 workflow 见 `docs/WORKFLOWS.md`。

---

## 日常使用方式

当前推荐把日报截图放到项目外部固定输入目录：

```text
/Users/ming/Restaurant/daily-input/马连道
```

日常只需要做两件事：

1. 把当天日报截图复制到上面的输入目录。
2. 确认 `watch_daily_folder.py` 或 launchd 监听服务正在运行。

如果需要手动触发日报，可以执行：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
python3 run_daily_report.py --store 便宜坊马连道
```

`--date` 只作为处理日期参考；日报业务日期必须由图片表头识别得到。

如果截图不在默认目录，也可以显式指定：

```bash
python3 run_daily_report.py --input-folder "/path/to/screenshots" --store 便宜坊马连道
python3 run_daily_report.py --image "/path/to/daily.png" --store 便宜坊马连道
```

查看自动监听状态：

```bash
scripts/status_watcher_launchd.sh
```

当前仓库已经包含 launchd 安装、状态、卸载脚本。若修改过监听脚本或默认输入目录，建议重新执行：

```bash
scripts/install_watcher_launchd.sh
```

---

## 当前自动化流程

1. `watch_daily_folder.py` 监听 `/Users/ming/Restaurant/daily-input/马连道`。
2. 发现新的 `png/jpg/jpeg/webp` 截图后，等待文件写入稳定。
3. 调用 `run_daily_report.py --image <截图> --store 便宜坊马连道`。
4. `run_daily_report.py` 用视觉模型识别截图，生成包含图片表头业务日期的结构化 JSON。
5. `image_to_excel.py` 写出标准 Excel：`data/便宜坊马连道_YYYY-MM-DD.xlsx`。
6. `main.py` 执行解析、AI 诊断、图表生成、飞书日报卡片推送、历史写入。
7. 成功后更新 `data/pipeline_state.json` 和 `data/pipeline_log.csv`，并自动提交/推送 pipeline 状态文件。
8. 如果当前运行日是周一，且本次真实日报日期是上一天（周日），则自动检查并推送上一自然周周报。

日报业务日期必须来自图片表头/真实营业数据；图片表头日期识别失败时流程必须中止，不允许 fallback 到系统日期。不允许为了凑周报或补齐日期而修改日报日期，也不允许用系统运行日期、文件创建日期、当前日期覆盖真实业务日期。周一只是触发时机，不是日报日期来源。

飞书推送链路统一走 `.env` 中的配置：`FEISHU_WEBHOOK` 用于群机器人卡片；`FEISHU_APP_ID` / `FEISHU_APP_SECRET` 可选，用于上传分析图。不要打印或提交 `.env`。

---

## 发布与文档同步规则

以后涉及代码变更并需要 `git push` 后，必须主动询问用户：
`是否需要更新技术文档并推送到飞书？`

未经用户确认，不得调用 `lark-cli docs +update`。如果用户确认，需要先生成或更新 `/private/tmp/restaurant-ai-bot-feishu-sync.md`，再追加写入飞书文档。不得读取、打印 `.env`、token、webhook、app secret。

如果只是检查文档，不要修改代码，不要 `git commit`，不要 `git push`。后续推荐新增 `scripts/push-and-feishu-doc.sh`，把 `git push` 和飞书同步确认做成固定脚本。

---

## 2. 文件结构

```
restaurant-ai-bot/
├── main.py               # 主入口：解析 → AI 诊断 → 出图 → 推送
├── parser.py             # 第1层：关键字定位法读取二维 Excel
├── analyst.py            # 第2层：调 LLM 输出结构化诊断 JSON
├── visualizer.py         # 第3层：matplotlib 出 4 张分析图
├── feishu_bot.py         # 第4层：构造飞书互动卡片并推送
├── weekly_auto.py        # 周一处理上一天周日日报后自动触发上一自然周周报
├── weekly_report.py      # 周报统计、卡片和推送
├── image_to_excel.py     # 辅助：Claude 读图后的 JSON → 标准 Excel
├── config.py             # 从 .env 读取凭证和路径
├── field_map.yaml        # 中文字段名 → 标准字段名映射表
├── prompts/
│   └── diagnose.txt      # AI 诊断 prompt（连锁餐饮 5 步分析法）
├── data/                 # 日报 Excel 放这里
├── output/               # 生成的 4 张分析图 + report JSON
├── raw_images/           # 日报原始截图放这里
├── test/                 # 测试图片（0524～0527.png）
├── .env                  # 本地凭证（不提交 git）
├── .env.example          # 配置模板
├── PROJECT_MEMORY.md     # 项目长期记忆，新会话先读这个
└── README.md             # 本文件
```

---

## 3. 环境准备

Python 3.9+，安装依赖：

```bash
pip3 install -r requirements.txt openai
```

---

## 3.1 Git 与安全

常用 Git 命令：

```bash
git status
git add .
git commit -m "xxx"
git push
```

安全提醒：
- 不要提交 `.env`。
- 不要提交真实经营数据。
- 不要提交日志、Excel、图片、parquet 文件。
- 提交前先用 `git status` 确认没有敏感文件进入暂存区。

---

## 4. 配置飞书 Webhook

### 第一步：创建自定义机器人（发卡片用，必须）

1. 打开飞书群 → 右上角「设置」→「群机器人」→「添加机器人」→「自定义机器人」
2. 安全设置里「关键词」填：`日报`
3. 复制生成的 Webhook 地址

### 第二步（可选）：创建自建 App（发图片用）

不配置此项，4 张分析图只存本地 `output/`，不会发到群里。

1. 打开 [https://open.feishu.cn/app](https://open.feishu.cn/app)
2. 「创建企业自建应用」→ 开通「机器人」能力
3. 「权限管理」→ 搜索并开通 `im:resource`（上传图片）
4. 「版本管理与发布」→ 创建版本 → 申请发布
5. 在群里把这个机器人加进来
6. 「凭证与基础信息」→ 复制 App ID 和 App Secret

---

## 5. 配置 .env

```bash
cp .env.example .env
# 用编辑器打开 .env 填写以下内容
```

```env
# 必填
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/你的地址

# 可选（发图片用）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# LLM（当前用阿里百炼）
LLM_PROVIDER=openai
LLM_API_KEY=你的百炼API_KEY
LLM_MODEL=qwen3.6-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

## 6. 运行 main.py

```bash
# 指定 Excel 文件
python3 main.py --file data/便宜坊马连道_2026-05-26.xlsx

# 指定日期（自动在 data/ 找对应文件）
python3 main.py --date 2026-05-26
```

运行后会依次：
1. 解析 Excel，提取结构化字段
2. 调 LLM 生成诊断 JSON
3. matplotlib 出 4 张图存入 `output/`
4. 推送飞书互动卡片（KPI + 诊断 + 建议）
5. 若配置了 App 凭证，还会逐张上传并发送分析图

---

## 7. 替换日报数据

### 方式 A：手上只有截图（当前主要方式）

```
第1步：把截图放入 raw_images/
第2步：把图片发给 Claude，Claude 输出 JSON
第3步：运行 image_to_excel.py
第4步：运行 main.py
```

```bash
python3 image_to_excel.py --date 2026-05-28 --json '{
  "本日收入": 20617.78,
  "来客数": 133,
  "烤鸭_日累计": 38.5,
  "烤鸭_月累计": 1648,
  ...
}'
```

> **注意**：日报中重复出现的「日累计/月累计」需加大类前缀区分：
> `烤鸭_月累计`、`套餐_日累计`、`鱼类_月累计`、`位吃_月累计` 等

生成的 Excel 自动存入 `data/便宜坊马连道_YYYY-MM-DD.xlsx`。

### 方式 B：已有 Excel 文件

直接把文件放入 `data/`，运行 `main.py --file` 即可。

---

## 7.1 后台监听截图文件夹

默认监听：

```text
/Users/ming/Restaurant/daily-input/马连道
```

### 推荐：安装为 macOS 开机自动启动服务

首次安装：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
scripts/install_watcher_launchd.sh
```

安装脚本会自动创建截图输入目录。安装后，macOS 登录后会通过 launchd 自动启动监听服务。日常使用时，只需要把截图放入：

```text
/Users/ming/Restaurant/daily-input/马连道
```

查看状态：

```bash
scripts/status_watcher_launchd.sh
```

停止并卸载自动启动服务：

```bash
scripts/uninstall_watcher_launchd.sh
```

卸载脚本只停止服务并删除 plist，不会删除业务数据、日志、截图、Excel 或日报文件。

### 临时前台/后台运行

前台调试：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
python3 watch_daily_folder.py
```

临时后台运行：

```bash
cd /Users/ming/Restaurant/restaurant-ai-bot
nohup python3 watch_daily_folder.py >> logs/watch_daily_folder.log 2>&1 &
```

停止临时后台进程：

```bash
pgrep -fl watch_daily_folder.py
pkill -f watch_daily_folder.py
```

排查错误：

```bash
tail -50 logs/watch_daily_folder.log
tail -5 data/pipeline_log.csv
```

监听脚本会把已处理图片记录到 `data/watch_state.json`，避免同一张图片重复触发。

---

## 8. 周报

### 自动触发自然周周报

当前周报不依赖 crontab，也不固定周一 9 点。业务规则是：

- 周报周期固定为自然周：周一到周日。
- 触发点是周一处理上一天（周日）真实日报并成功推送日报之后。
- 周六日报完成不触发周报。
- 周一收到并完成上周日日报后，先推送日报，再检查并推送上一自然周周报。
- 周报发送前必须检查区间内业务日期是否连号。
- 如果周中缺一天或多天，默认 `STRICT_WEEKLY_DATE_CHECK=false` 时周报照常推送，但卡片开头会醒目标注缺失日期；设为 `true` 时缺日期则停止推送并提示缺失日期。
- 缺日期时不伪造、不补齐、不用前后日期替代。
- 同一个自然周周期只推送一次，通过 `data/weekly_state.json` 防重复。
- 周报统计以 `data/store_history.csv` 中真实存在的日报日期为准。

### 手动生成周报

```bash
# 标准用法：自动计算上周一～上周日
python3 weekly_report.py --last-week

# 验证统计范围和卡片结构（不推送飞书）
python3 weekly_report.py --last-week --dry-run

# 指定任意日期范围
python3 weekly_report.py --start 2026-05-20 --end 2026-05-26

# 最近 N 天
python3 weekly_report.py --days 14
```

### 日志文件位置

| 日志 | 路径 | 内容 |
|------|------|------|
| 周报运行日志 | `logs/weekly_report.log` | 每次运行的详细输出 |
| 日报监听日志 | `logs/watch_daily_folder.log` | 自动日报与周报触发链路的 stdout/stderr |

### 如何确认推送成功

```bash
# 查看最新日志
tail -20 logs/weekly_report.log

# 成功标志：
# [weekly] ✅ 周报已推送到飞书群
# [时间戳] ✅ 周报推送成功

# 失败时排查：
# 1. 检查飞书群是否收到消息
# 2. 确认 .env 中 FEISHU_WEBHOOK 配置正确
# 3. 确认 data/store_history.csv 有上周数据
python3 weekly_report.py --last-week --dry-run   # 先干跑验证
```

### 2026-05-31 技术更新记录

- 新增 `weekly_auto.py`：周一处理上一天周日日报完成后自动触发上一自然周周报。
- 修改 `run_daily_report.py`：日报完全成功后调用周报条件检查。
- 修改 `weekly_report.py`：支持缺失日期提示，统计仍基于真实存在的日报数据。
- 新增 `test_weekly_auto.py`：覆盖非周一不触发、周一处理非昨天不触发、周一处理上周日触发、缺一天仍推送、防重复、无数据不推送。
- 新增 `data/weekly_state.json`：记录已推送自然周周期，避免重复推送。
- 验证：`python3 -m unittest test_run_daily_report.py test_weekly_auto.py` 通过，共 15 个测试 OK。
- 不需要重启监听服务，因为 `watch_daily_folder.py` 没有改。

### 2026-06-01 日报/周报日期校验增强与真实流程验证

本次项目从“能识别日报并推送”升级为“能防止日期污染历史数据，并能在周一收到周日数据后自动触发上周周报”。

已完成：
- 日报 `business_date` 只来自图片表头日期。
- 系统日期、文件创建日期、监听日期不能覆盖业务日期。
- `processing_date` 只用于日志，不用于日报标题、Excel 文件名、`store_history.csv` 业务日期或 `pipeline_log.csv` 业务日期。
- 图片表头日期识别失败时流程中止，不 fallback 到今天。
- `--date` 与图片表头日期不一致时，以图片表头日期为准，并在 pipeline 记录 warning。
- 周报发送前检查自然周日期完整性；默认允许缺失日期发送，但卡片提示缺失日期；`STRICT_WEEKLY_DATE_CHECK=true` 时缺日期阻止发送。

真实流程验证：
- 图片表头日期：`2026-05-31`
- 日报标题：`便宜坊马连道 · 2026-05-31 经营日报`
- Excel 文件：`data/便宜坊马连道_2026-05-31.xlsx`，表头日期 `2026 年 5 月 31 日`
- 周报已触发并推送成功，统计区间 `2026-05-25` 到 `2026-05-31`
- 周报天数 `7`，缺失日期无，`date_check_status=complete`
- `pipeline_log.csv`：`business_date=2026-05-31`，`processing_date=2026-06-01`，`source_date_from_image=2026-05-31`，`date_validation_status=warning_processing_date_differs`
- git status：干净；最新状态提交 commit：`a3a4040`

---

## 9. 排障

| 现象 | 原因 | 解决 |
|------|------|------|
| `未找到字段: ['xxx']` | yaml 里字段名与实际表格不一致 | 修改 `field_map.yaml` |
| 图表中文显示方块 | 缺中文字体 | macOS 已用 Arial Unicode MS 修复；Linux 装 `fonts-noto-cjk` |
| 图片未发到飞书 | 未配置 App 凭证 | 在 `.env` 填 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` |
| 飞书 token 报错 | 缓存过期 | 删除 `output/.feishu_token.json` |
| LLM 返回不是 JSON | 模型输出偏离 prompt | 降低 temperature 或换模型 |

---

## 10. 后续开发计划

- [ ] 标准化输入：支持 `daily/` 文件夹批量处理多日图片
- [ ] 建立 `data_schema.json`：定义字段结构、类型、异常阈值
- [ ] 异常规则引擎：同比跌 >15%、折扣率 >40%、套餐挂零等自动告警
- [ ] 趋势分析：基于 `history.parquet` 做 7 日 / 30 日对比图
- [ ] 图片推送：配置自建 App `im:resource` 权限，发 4 张分析图
- [ ] 多店支持：适配御炉通明湖等不同格式门店
- [x] 周报自动触发：周一处理上一天周日日报完成后自动推送上一自然周周报
- [ ] 日报日期自动从截图标题中识别并传入 `run_daily_report.py`
- [x] 周报可视化看板：独立 skill 将已验证周报数据渲染为 ECharts 风格 HTML/PNG

---

## 周报可视化看板 Skill

`skills/weekly_dashboard/` 是周报数据可视化增强层，只读取已验证过的周报数据，不改变现有日报/周报推送逻辑，也不修改 `store_history.csv`、`pipeline_log.csv` 或任何业务日期。

运行方式：

```bash
python3 skills/weekly_dashboard/render_weekly_dashboard.py \
  --store "便宜坊马连道" \
  --start-date 2026-05-25 \
  --end-date 2026-05-31
```

输出：
- `output/weekly_dashboard_便宜坊马连道_2026-05-25_2026-05-31.html`
- `output/weekly_dashboard_便宜坊马连道_2026-05-25_2026-05-31.png`

看板使用深色科技感 ECharts 风格，包含营业额柱状图、客流折线图、营业额面积趋势、收入结构饼图、TOP 横向条形图、一周经营强弱极坐标图和核心 KPI 卡片。周报区间必须显式传入，不能用系统日期推断；如有缺失日期，看板会提示，且不会伪造数据。

默认只生成 HTML/PNG，不推送飞书。如需把看板图片发到日报/周报相同的飞书群，显式增加：

```bash
python3 skills/weekly_dashboard/render_weekly_dashboard.py \
  --store "便宜坊马连道" \
  --start-date 2026-05-25 \
  --end-date 2026-05-31 \
  --send-to-feishu
```

`--send-to-feishu` 会在 PNG 成功生成后复用项目现有飞书推送逻辑发送标题、说明和图片；PNG 不存在或图片上传配置不可用时会报错中止，不会打印 `.env`、webhook、token 或 app secret。

---

## 11. 智能体接入说明

> 本章面向 Claude / Codex / 其他 AI 智能体。人类开发者可跳过。

### 进入项目的第一件事（必须）

1. **先读文档，再动代码**
   - `PROJECT_MEMORY.md` — 项目状态、已完成功能、当前已知问题
   - `docs/AGENT_ONBOARDING.md` — 完整接入说明（禁止事项 / 流程 / 健康检查）

2. **确认当前功能状态**
   ```bash
   ls -la data/store_history.csv   # 核心历史数据必须存在
   ls -la .env                      # 凭证文件必须存在（不要打印内容）
   python3 weekly_report.py --last-week --dry-run   # 验证周报链路
   scripts/status_watcher_launchd.sh                # 查看日报监听服务
   ```

3. **不要一上来就重写项目**
   - `main.py` 已跑通日报全流程，改动前必须充分测试
   - `data/store_history.csv` 是核心数据资产，禁止覆盖或删除

### 敏感信息处理

- `.env` 包含飞书 Webhook、LLM API Key 等，**不要打印或输出其内容**
- 不要将 webhook 地址写入代码，统一从 `config.py` 读取

### 修改自动化任务前必须确认

当前周报自动化不依赖 crontab。如需修改或新增 crontab 定时任务，**必须先把方案输出给用户确认**，不要直接执行 `crontab -e`。

### 周期参数说明

| 参数 | 含义 | 注意 |
|------|------|------|
| `--last-week` | 上周一 ～ 上周日（固定完整周） | 推荐用法 |
| `--days 7` | 最近 7 个自然日（含今天） | 与上方**不等价** |
| `--start / --end` | 指定任意日期范围 | 用于补跑历史 |

详细说明见 `docs/AGENT_ONBOARDING.md`。
