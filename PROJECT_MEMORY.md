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
- 定时自动化（cron 周报）

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
├── image_to_excel.py     # 辅助：Claude 读图后的 JSON → 标准 Excel
├── config.py             # 凭证 & 路径（从 .env 读）
├── field_map.yaml        # 字段映射：中文表头 → 标准字段名
├── prompts/diagnose.txt  # 日报 AI 诊断 prompt（连锁餐饮 5 步分析法）
├── scripts/
│   └── run_weekly.sh     # cron 执行脚本：每周一 9:00 生成上周周报
├── data/
│   ├── store_history.csv # ★ 核心历史数据（不要手动删改）
│   ├── data_schema.json  # 字段定义 + 告警阈值
│   ├── sample_data.json  # 3 天测试数据
│   └── 便宜坊马连道_YYYY-MM-DD.xlsx  # 日报 Excel（按日期命名）
├── output/               # 生成的 4 张分析图 + report JSON（可重新生成）
├── logs/                 # 运行日志（不要删除）
├── raw_images/           # 日报截图原图
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
- [x] `watch_daily_folder.py`：监听 `/Users/ming/Desktop/临时/马连道` 新截图并自动触发一键日报
- [x] 每次运行后自动追加数据到 `data/store_history.csv`
- [x] 历史数据重复检测（同天同店提示 y/n，cron 模式自动跳过）

### 周报
- [x] `weekly_report.py` 完成：读 CSV → 统计 → AI 分析 → 飞书互动卡片
- [x] 支持 `--last-week` 参数：固定统计「上周一～上周日」
- [x] 支持 `--dry-run`：只打印卡片 JSON，不推送
- [x] `scripts/run_weekly.sh` 已创建，有可执行权限

### 自动化
- [x] crontab 配置已生成（**待确认是否写入系统，见下方**）

### 数据文件
- [x] `data/data_schema.json`：字段定义 + 告警阈值
- [x] `data/sample_data.json`：3 天真实测试数据（0524/0525/0526）
- [x] `data/store_history.csv`：当前有 3 行历史数据（2026-05-24/25/26）

---

## 5. 自动化配置状态

### crontab（每周一 9:00 生成上周周报）

```cron
0 9 * * 1 /Users/ming/Restaurant/restaurant-ai-bot/scripts/run_weekly.sh >> /Users/ming/Restaurant/restaurant-ai-bot/logs/cron_weekly.log 2>&1
```

**⚠️ 当前状态：待确认是否已写入系统。**

检查命令：
```bash
crontab -l
```

写入命令（如未写入）：
```bash
crontab -e   # 粘贴上方那行，保存退出
```

---

## 6. 当前已知问题

| 问题 | 状态 |
|------|------|
| 数据来源仍为手动整理（Claude 读图 → JSON → Excel） | 待解决 |
| 4 张分析图未发到飞书（需配置 App 凭证） | 待解决 |
| 0527.png（御炉通明湖）格式完全不同，尚未适配 | 待解决 |
| 部分字段偶尔为空（回收100元代金券数量等）parser 报 warning | 低优先级 |
| CSV 历史数据目前只有 3 天，周报分析样本不足 | 持续积累中 |

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

## 8. 下一步任务（优先级排序）

1. **持续积累日报数据**：每天跑 `main.py`，让 CSV 有足够的历史
2. **确认 crontab 是否已写入**：`crontab -l` 检查
3. **标准化输入**：支持从 `daily/` 文件夹批量处理多日截图
4. **异常规则引擎**：基于 `data_schema.json` 里的阈值，自动判断告警级别
5. **趋势分析图**：周报加上 7 日收入曲线图
6. **飞书图片推送**：配置自建 App `im:resource` 权限
7. **多店支持**：适配御炉通明湖店（不同字段格式）
8. **日报定时任务**：每天 8:00 cron 自动跑昨日日报

---

## 9. 工作约定

- **日报运行**：`python3 main.py --file data/便宜坊马连道_YYYY-MM-DD.xlsx`
- **周报运行**：`python3 weekly_report.py --last-week`
- **验证（不推送）**：`python3 weekly_report.py --last-week --dry-run`
- **读图流程**：截图 → 发给 Claude → Claude 输出 JSON → `image_to_excel.py --date YYYY-MM-DD --json '...'`
- **一键截图日报**：截图默认放 `/Users/ming/Desktop/临时/马连道`，运行 `python3 run_daily_report.py --store 便宜坊马连道 --date YYYY-MM-DD`
- **监听截图文件夹**：`nohup python3 watch_daily_folder.py >> logs/watch_daily_folder.log 2>&1 &`
- **安装开机自动监听**：`scripts/install_watcher_launchd.sh`
- **查看/卸载监听服务**：`scripts/status_watcher_launchd.sh` / `scripts/uninstall_watcher_launchd.sh`
- **重复字段前缀**：`烤鸭_月累计`、`套餐_日累计`、`鱼类_月累计` 等
- **备份**：`.backup_v2/` 是 v2 版本快照，不要删除
- **敏感信息**：`.env` 内容不要打印或提交到 git
