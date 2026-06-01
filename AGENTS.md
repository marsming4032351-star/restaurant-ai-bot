# AGENTS.md — 便宜坊马连道日报助手

> Codex CLI 进入本项目时自动读取本文件。读完即可开始工作，不需要用户再解释项目背景。

---

## 项目定位

便宜坊马连道餐厅经营数据自动化：日报截图 → 结构化数据 → 飞书日报/周报推送。

技术栈：Python 3，openpyxl，pandas，matplotlib，openai 兼容协议（阿里百炼 qwen3），飞书 webhook。

---

## 进入项目后必须立即执行

```bash
cat data/pipeline_state.json
tail -n 5 data/pipeline_log.csv
ls -la data/store_history.csv .env
```

这三步告诉你：当前应处理哪一天、上次是否已推送、下一步动作是什么。**不需要用户再解释。**

---

## 日报与周报自动化核心规则

- 每天把真实日报截图放入：`/Users/ming/Restaurant/daily-input/马连道`
- LaunchAgent 监听服务自动识别图片并执行 `run_daily_report.py`
- 自动生成日报 Excel / JSON / 飞书卡片
- 日报业务日期必须来自图片表头/真实营业数据
- 图片表头日期识别失败时必须中止，不允许 fallback 到系统日期
- 不允许为了凑周报或补齐日期而修改日报日期
- 不允许用系统运行日期、文件创建日期、当前日期覆盖真实数据日期
- 周一只是周报触发时机，不得覆盖日报业务日期
- 周报周期固定为自然周：周一到周日
- 不使用 crontab，不固定周一 9 点
- 周六日报完成不触发周报
- 周一处理上一天（周日）真实日报完成后，先推送日报，再检查并推送上一自然周周报
- 周报发送前必须执行日期连号检查；缺一天或多天时默认照常推送，但必须醒目标注缺失日期，不得伪造数据
- 同一个自然周周期只推送一次，通过 `data/weekly_state.json` 防重复
- 周报统计以 `data/store_history.csv` 中真实存在的日报日期为准

### 2026-06-01 真实流程验证结论

- 项目已从“能识别日报”升级为“能防止日期污染历史数据，并能在周一收到周日数据后自动触发上周周报”。
- 真实截图表头日期 `2026-05-31`，日报标题、Excel 文件名、`store_history.csv`、`pipeline_log.csv` 业务日期均保持 `2026-05-31`。
- 处理日期 `2026-06-01` 只记录为 `processing_date`；`date_validation_status=warning_processing_date_differs`。
- 周报已自动触发，区间 `2026-05-25` 到 `2026-05-31`，7 天完整，缺失日期无，`date_check_status=complete`。

---

## 用户发来日报截图时的完整流程

按以下顺序执行，一次性完成，不中途停下来问：

### 1. 推送前安全检查

```bash
grep "目标日期" data/pipeline_log.csv
```

若该行 `status=done` 且 `feishu_pushed=true`：**停止，告知用户，等待确认。**

### 2. 读图提取 JSON

从截图识别所有字段（左侧营业收入表 + 右侧销售日报表）。

重复字段加大类前缀：
- `烤鸭_日累计` / `烤鸭_月累计`
- `套餐_日累计` / `套餐_月累计`
- `鱼类_日累计` / `鱼类_月累计`

### 3. 生成 Excel

```bash
python3 image_to_excel.py --date YYYY-MM-DD --json '{...}'
```

### 4. 运行日报（推送飞书）

```bash
python3 main.py --file data/便宜坊马连道_YYYY-MM-DD.xlsx
```

### 5. 更新 pipeline_state.json（覆盖写）

```json
{
  "workflow_version": "1.0",
  "current_store_name": "便宜坊马连道",
  "current_target_date": "<下一天>",
  "last_completed_date": "<刚完成的日期>",
  "last_completed_status": "done",
  "last_feishu_pushed": true,
  "next_action": "idle_all_done",
  "updated_at": "<当前时间 ISO 8601>",
  "updated_by": "codex"
}
```

### 6. 更新 pipeline_log.csv（追加或修改目标行）

将目标日期行更新为：`status=done, feishu_pushed=true, pushed_at=<当前时间>, agent=codex`

**禁止 cat 全量文件。只用 grep 定位目标行，或追加新行。**

### 7. git commit & push

```bash
git add data/pipeline_state.json data/pipeline_log.csv
git commit -m "日报推送完成：YYYY-MM-DD 便宜坊马连道"
git push origin main
```

---

## 代码有任何修改，自动 git commit/push

修改任何 `.py`、`.yaml`、`.md`、`.sh`、`.json` 文件后，完成后立即：

```bash
git status
git add <具体文件名>     # 禁止 git add . 或 git add -A
git commit -m "说明改动内容"
git push origin main
```

---

## 关键文件

| 文件 | 用途 |
|------|------|
| `data/pipeline_state.json` | 当前状态，每次必读 |
| `data/pipeline_log.csv` | 历史流水，grep/tail 查询 |
| `data/store_history.csv` | 核心历史，只追加，不覆盖，不删除 |
| `data/weekly_state.json` | 自然周周报防重复状态 |
| `main.py` | 日报全流程入口 |
| `image_to_excel.py` | JSON → 标准 Excel |
| `weekly_auto.py` | 周一在上一天周日日报完成后自动触发上一自然周周报 |
| `weekly_report.py` | 周报统计、缺失日期提示和飞书推送 |
| `skills/weekly_dashboard/` | 周报可视化增强层，读取已验证周报数据生成 HTML/PNG 看板 |
| `.env` | 凭证（不打印，不提交） |
| `docs/WORKFLOWS.md` | 完整流程说明 |
| `docs/AGENT_ONBOARDING.md` | 禁止事项和接入规范 |

---

## 绝对禁止

- 打印或输出 `.env` 任何内容
- 覆盖或删除 `data/store_history.csv`
- 同一日期 `feishu_pushed=true` 时不经确认再次推送
- `git add .` 或 `git add -A`
- 未经用户确认写入 crontab
- cat 全量 `pipeline_log.csv`

---

## 常用命令

```bash
python3 main.py --file data/便宜坊马连道_YYYY-MM-DD.xlsx
python3 image_to_excel.py --date YYYY-MM-DD --json '{...}'
python3 weekly_report.py --last-week
python3 weekly_report.py --last-week --dry-run
python3 skills/weekly_dashboard/render_weekly_dashboard.py --store "便宜坊马连道" --start-date YYYY-MM-DD --end-date YYYY-MM-DD
python3 skills/weekly_dashboard/render_weekly_dashboard.py --store "便宜坊马连道" --start-date YYYY-MM-DD --end-date YYYY-MM-DD --send-to-feishu
python3 -m unittest test_run_daily_report.py test_weekly_auto.py
cat data/pipeline_state.json
grep "YYYY-MM-DD" data/pipeline_log.csv
tail -n 5 data/pipeline_log.csv
```

`--send-to-feishu` 是周报看板的独立可选图片推送开关，只在 PNG 成功生成后复用现有飞书逻辑发送标题、说明和看板图片；默认不推送，也不接入日报/周报主流程。

### 周报看板增强规则

- 周报看板新增 `weekly field enhancer`，优先读取 `output/report_*.json` 的日报结构化字段，再结合 `field_map.yaml` 和 `store_history.csv` 构建看板数据。
- 字段缺失时显示 `暂无` 或跳过模块，不报错，不伪造数据。
- 周一自动触发周报时也会尝试生成并推送增强版看板图片。
- 本地生成命令与飞书推送命令仍然使用 `skills/weekly_dashboard/render_weekly_dashboard.py` 和 `--send-to-feishu`。

### 周报看板飞书图片推送经验

- Codex 环境可能无法访问 Mac 本机代理 `127.0.0.1:7897`，带图片上传的飞书推送建议在 Mac 本机 Terminal 执行。
- 推送前 `.env` 必须配置 `FEISHU_WEBHOOK`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET`；不得打印或写入真实值。
- 如果 Python `requests` 无法解析 `open.feishu.cn`，但 `curl` 可以访问，通常是 Python 代理/DNS 路径问题。
- 本机 Terminal 执行前可设置：

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
```

成功命令示例：

```bash
python3 skills/weekly_dashboard/render_weekly_dashboard.py \
  --store "便宜坊马连道" \
  --start-date 2026-05-25 \
  --end-date 2026-05-31 \
  --send-to-feishu
```

不要记录任何真实 webhook、App Secret、token 或 `image_key`。
