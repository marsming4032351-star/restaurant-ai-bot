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
| `main.py` | 日报全流程入口 |
| `image_to_excel.py` | JSON → 标准 Excel |
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
cat data/pipeline_state.json
grep "YYYY-MM-DD" data/pipeline_log.csv
tail -n 5 data/pipeline_log.csv
```
