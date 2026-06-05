# 餐饮报表数据可视化自动化项目 · 产品体检报告

> 生成时间：2026-06-01（2026-06-05 复核更新：补充天气/节气运营上下文能力，统一总分口径）
> 基于仓库真实状态，不含虚构内容。本地绝对路径已泛化为 `<项目根目录>`。

---

## 1. 项目一句话定位

**把餐饮门店每天收到的经营数据图片，自动转化为结构化日报、周报、可视化看板，并推送到飞书的 AI 数据自动化工作流。**

早期原型定位：CaiHub 餐饮经营数据闭环 Agent，面向便宜坊马连道门店，具备从截图到飞书推送的完整产品链路。

---

## 2. 当前项目全景图（文本版）

```
日报图片输入
  ↓ 放入 <项目根目录>/daily-input/马连道
监听文件夹 watch_daily_folder.py（launchd 开机自动运行）
  ↓ hash 去重
run_daily_report.py（一键日报入口）
  ↓ 调 VLM 视觉模型识别图片
图片识别 → 提取结构化 JSON（含图片表头业务日期）
  ↓ 日期识别失败则立即中止，不 fallback 系统日期
image_to_excel.py → 标准 Excel（data/便宜坊马连道_YYYY-MM-DD.xlsx）
  ↓
main.py（日报主链路）
  ├→ parser.py（关键字定位读取二维 Excel）
  ├→ analyst.py（调 Qwen LLM 生成诊断 JSON）
  ├→ visualizer.py（matplotlib 4 张分析图 → output/*.png）
  └→ feishu_bot.py（构造飞书互动卡片 → 推送飞书群）
  ↓
history.py → 追加 data/store_history.csv（核心历史库）
  ↓
output/report_MLD_YYYY-MM-DD.json（结构化存档）
  ↓
pipeline_state.json / pipeline_log.csv 更新
  ↓
git add / commit / push（自动提交状态文件）
  ↓
weekly_auto.py 条件检查：
  - 运行日是周一？
  - 日报真实业务日期是昨天（周日）？
  - weekly_state.json 未记录该自然周？
  ↓ 三条件全满足
weekly_report.py 统计 store_history.csv
  ↓ 缺失日期提示但不伪造数据
飞书群 · 周报卡片推送
  ↓
skills/weekly_dashboard/render_weekly_dashboard.py
  ↓ 读 report_*.json + field_map.yaml + store_history.csv
ECharts 风格 HTML/PNG 经营看板
  ↓ --send-to-feishu（可选）
飞书群 · 看板图片推送
  ↓
data/weekly_state.json 记录已推送周期（防重复）
  ↓
（手动）飞书文档同步 ← 当前无自动化脚本
  ↓
GitHub commit/push + PROJECT_MEMORY.md 更新
```

---

## 3. 当前已完成能力清单

| 能力名称 | 当前状态 | 对产品的价值 | 证据文件 |
|---------|---------|------------|---------|
| 图片日报识别 | ✅ 已完成 | 核心输入链路，将截图自动转为结构化数据 | run_daily_report.py, image_to_excel.py |
| 业务日期校验 | ✅ 已完成（2026-06-01 增强） | 防止系统日期污染历史数据，数据可信基础 | run_daily_report.py, PROJECT_MEMORY.md §10 |
| 日报 AI 诊断 | ✅ 已完成 | 把原始数据转化为经营建议，提升报告价值 | analyst.py, prompts/diagnose.txt |
| 日报可视化图表 | ✅ 本地生成（4张） | 直观展示 KPI、结构、会员、品类 | visualizer.py, output/*.png |
| 日报飞书卡片推送 | ✅ 已完成 | 老板和店长实时收到经营日报 | feishu_bot.py, pipeline_log.csv |
| 分析图飞书推送 | ⚠️ 未完成（需 App 凭证） | 图片留在本地 output/，未入飞书群 | PROJECT_MEMORY.md §6 |
| 文件夹自动监听 | ✅ 已完成（launchd） | 开机自动运行，无需手工触发 | watch_daily_folder.py, scripts/ |
| 周报自动触发 | ✅ 已完成（2026-05-31） | 周一处理完周日日报后无需手动操作 | weekly_auto.py, test_weekly_auto.py |
| 周报数据聚合 | ✅ 已完成 | 7天 KPI、异常汇总、LLM 建议 | weekly_report.py |
| 周报飞书卡片推送 | ✅ 已完成（真实验证） | 自然周经营总结推送飞书 | PROJECT_MEMORY.md §10 |
| 周报可视化看板 | ✅ 已完成（HTML/PNG） | ECharts 风格经营大屏，含多维指标 | skills/weekly_dashboard/ |
| 看板飞书图片推送 | ✅ 已完成（2026-06-01 验证） | 看板图片已成功推送飞书 | SKILL.md, README.md §看板飞书推送经验 |
| 历史数据沉淀 | ✅ 已完成 | store_history.csv 是核心数据资产 | history.py, data/store_history.csv |
| 防重复推送 | ✅ 已完成 | pipeline_log.csv + weekly_state.json 双重保护 | watch_daily_folder.py, weekly_auto.py |
| Git 自动提交 | ✅ 已完成 | 状态文件自动版本化，跨会话状态恢复 | run_daily_report.py §7 |
| 飞书文档同步 | ❌ 未自动化 | 文档更新需手动操作 | WORKFLOWS.md §发布与文档同步规则 |
| skill 化能力 | 🔧 部分完成 | weekly_dashboard 已是标准 skill，其他仍是 workflow | skills/weekly_dashboard/SKILL.md |
| 天气/节气运营上下文 | ✅ 已完成（2026-06-05） | 天气落库 + 节气确定性派生，进 AI 建议；缺数据诚实记“暂无”不伪造 | solar_terms.py, weather_amap.py, data/solar_terms_cn.json |

---

## 4. 当前 skill 与 workflow 盘点

### 已正式 skill 化

| Skill | 文件 | 状态 |
|-------|------|------|
| weekly_dashboard | skills/weekly_dashboard/ | ✅ 有 SKILL.md，标准参数，独立入口 |

### 当前只是 workflow（未 skill 化）

| Workflow | 核心文件 | 说明 |
|---------|---------|------|
| daily_report | main.py, run_daily_report.py | 日报全链路，最核心的 workflow |
| feishu_push | feishu_bot.py | 卡片构建与推送，可抽象为 skill |
| weekly_auto | weekly_auto.py | 周报触发条件判断 |
| feishu_doc_sync | 无专用脚本 | 手动，需自动化 |
| git_release | 内嵌在 run_daily_report.py | 状态提交，可独立 |
| project_memory_update | 手动 | 每次大改后手动更新 |
| image_ocr | image_to_excel.py + run_daily_report.py | VLM 识别逻辑，可抽象 |

### 未来建议拆分为 skill

| 建议 Skill | 核心能力 | 优先级 |
|-----------|---------|-------|
| skills/daily_report/ | 截图→Excel→飞书日报全链路 | P1 |
| skills/feishu_sync/ | 飞书文档自动写入 | P1 |
| skills/project_memory/ | PROJECT_MEMORY 自动更新 | P2 |
| skills/git_release/ | 安全提交状态文件 | P2 |
| skills/bi_dashboard/ | 通用数据大屏渲染 | P2 |
| skills/product_health_check/ | 项目健康状态检查 | P2 |

---

## 5. 产品体检报告

### 5.1 产品闭环完整度：3.8 / 5

**评分理由：** 日报→AI 诊断→飞书卡片→历史沉淀→周报→看板的核心闭环已经走通，且有真实运行验证（2026-05-24 至 2026-06-01 共 9 天数据）。飞书分析图 4 张未能自动入飞书（需 App 凭证），飞书文档同步无自动化脚本，是两个明显缺口。

**主要问题：**
- 分析图只在本地 output/，未推送飞书群
- 飞书文档更新全靠手动
- 看板图片推送需手动设置代理环境变量

**优化建议：** 完成飞书 App 自建配置，补充 `scripts/push-and-feishu-doc.sh` 脚本。

---

### 5.2 自动化程度：4.0 / 5

**评分理由：** launchd 开机自动监听文件夹、日报自动触发、周一周报自动触发、git 自动提交已全部实现。链路从截图落地到飞书卡片推送，人工操作只剩"把截图复制到输入目录"。

**主要问题：**
- 飞书图片上传偶发网络问题（Codex 环境代理访问问题）
- 飞书文档同步需手动触发
- 御炉通明湖门店日报格式不同，尚未接入自动化

**优化建议：** 新增 `scripts/push-and-feishu-doc.sh`，把图片推送和文档同步标准化为一条命令。

---

### 5.3 数据可信度：4.5 / 5

**评分理由：** 业务日期严格来自图片表头，不允许 fallback 到系统日期，已通过真实链路验证（processing_date vs business_date 分离）。缺失日期不伪造，只标注提示。数据写入有重复保护。

**主要问题：**
- VLM 识别偶发 JSON 格式异常（pipeline_log 中有两条 failed 记录）
- 部分字段偶尔空值（回收代金券等）

**优化建议：** VLM 识别加 retry 机制，增加 JSON schema 校验层。

---

### 5.4 飞书集成度：3.0 / 5

**评分理由：** 日报卡片推送稳定，周报卡片推送成功验证，看板图片推送已成功验证一次。但分析图 4 张仍未接入飞书，飞书文档同步无自动化。

**主要问题：**
- FEISHU_APP_ID/SECRET 未配置（图片上传）
- 飞书文档更新手动
- 飞书多维表格未同步

**优化建议：** 完成 App 自建配置，使用 lark-doc/lark-base skill 实现文档和多维表格自动同步。

---

### 5.5 可视化表达力：3.5 / 5

**评分理由：** weekly_dashboard 看板已有 7 种图表模块（营业额柱状图、客流折线、面积趋势、收入结构饼图、TOP 条形图、极坐标强弱图、KPI 卡片），ECharts 深色风格，视觉效果良好。日报 4 张 matplotlib 图风格较朴素。

**主要问题：**
- 日报图表风格与看板风格不统一
- 看板暂无环比对比、趋势预测
- 无动态交互（HTML 静态）

**优化建议：** 看板增加上周对比模块，考虑 HyperFrames 视频化周报。

---

### 5.6 可运营性：2.5 / 5

**评分理由：** 当前是单人单店的开发者工具形态。无 Web UI，配置依赖 .env 文件手动编辑，无法让非技术用户自助操作。

**主要问题：**
- 所有操作需要命令行
- 无状态监控界面
- 无告警通知机制（只有卡片里的警示级别）
- 无法多人协作

**优化建议：** 阶段性目标：先出一个简单的飞书多维表格管理界面，降低操作门槛。

---

### 5.7 多门店复制能力：1.5 / 5

**评分理由：** 当前代码和配置对便宜坊马连道有大量硬编码依赖（field_map.yaml 字段映射、输入目录路径、日报标题格式）。御炉通明湖日报格式完全不同，尚未适配。

**主要问题：**
- field_map.yaml 是针对单店的字段映射
- 输入目录路径硬编码
- 没有门店配置模板机制

**优化建议：** 把门店配置抽象为 `stores/<store_id>/config.yaml`，输入目录、字段映射、飞书 webhook 各自隔离。

---

### 5.8 未来 SaaS 化潜力：3.0 / 5

**评分理由：** CaiHub 目录已存在 FastAPI + 领域模型 + Alembic 迁移 + 多租户结构的后端原型，与 restaurant-ai-bot 是关联项目。如果两者打通，SaaS 化路径清晰。

**主要问题：**
- restaurant-ai-bot 是脚本工具，CaiHub 是 API 后台，当前未打通
- 无用户认证、无多租户权限
- 无付费模型设计

**优化建议：** 先用 restaurant-ai-bot 跑通多门店，再以 CaiHub API 包装成 SaaS 接口。

---

### 5.9 技术债风险：2.5 / 5（数字越小风险越高）

**主要技术债：**
1. 核心数据用 CSV（store_history.csv），规模扩大后性能和并发问题突出
2. 输入目录和门店名多处硬编码
3. 飞书推送重试机制缺失（网络异常直接 failed）
4. VLM 识别 JSON 格式异常无自动恢复
5. 测试覆盖 weekly_auto、daily_report、solar_terms（节气锚点）流程，visualizer/feishu_bot 仍无测试

**优化建议：** P0 补充飞书推送重试；P1 引入 SQLite 替代 CSV；P2 补充模块单测。

---

### 5.10 文档完整度：4.5 / 5

**评分理由：** README.md、PROJECT_MEMORY.md、AGENTS.md、CLAUDE.md、docs/WORKFLOWS.md、docs/AGENT_ONBOARDING.md 全部存在且内容详尽，完整覆盖接入规范、工作约定、禁止事项和历史决策记录。

**主要问题：**
- 缺少 API 文档（无 Swagger/OpenAPI）
- 缺少产品概览类文档（适合对外展示）

---

### 体检总分：3.3 / 5（加权平均 3.28）

| 维度 | 评分 |
|------|------|
| 产品闭环完整度 | 3.8 |
| 自动化程度 | 4.0 |
| 数据可信度 | 4.5 |
| 飞书集成度 | 3.0 |
| 可视化表达力 | 3.5 |
| 可运营性 | 2.5 |
| 多门店复制能力 | 1.5 |
| 未来 SaaS 化潜力 | 3.0 |
| 技术债风险（反向） | 2.5 |
| 文档完整度 | 4.5 |
| **加权平均** | **3.28** |

---

## 6. 当前项目的核心价值判断

这个项目现在不是普通脚本，而是一个**早期 AI 餐饮经营数据产品原型**。

### 对餐饮老板的价值
每天早晨收到一条飞书消息，一眼看清昨天的收入、客流、折扣率和 AI 诊断建议，不用打开 ERP，不用看密密麻麻的 Excel。每周一还能收到上一周的经营大屏。**节省老板每天 10-20 分钟的数据整理时间。**

### 对店长的价值
日报有明确的"健康/警示/异常"等级，配有明日建议，帮助店长快速决策当天的促销策略和运营重点。

### 对财务/运营的价值
历史数据自动沉淀在 store_history.csv（后续可迁入数据库），折扣率、同比等指标自动计算，减少手工整理报表的工作量。

### 对多门店管理的价值
目前只有一家门店，但架构上已经预留门店名参数，未来扩展到 3-5 家连锁门店后，可以做门店对比和统一周报汇总。

### 对 CaiHub 产品化的价值
这是 CaiHub 最真实的业务验证 demo：证明"截图→AI→飞书"的闭环可行。基于此可以设计 CaiHub 的 API 接口规范、数据模型和多租户架构。

### 对小红书传播和案例包装的价值
完整链路（输入截图→飞书收到经营大屏）是天然的内容素材。周报看板的 PNG 截图可以直接用于小红书"用 AI 做餐厅数字化"内容。

---

## 7. 当前最值得优化的地方

### P0：主流程稳定性（必须优先）

| 任务 | 当前问题 | 影响 |
|------|---------|------|
| VLM 识别 JSON 解析失败自动重试 | 偶发 ValueError: 找不到 JSON | 日报卡住需人工干预 |
| 飞书推送网络失败重试 | 直接 failed，无 retry | APIConnectionError 会导致当天无日报 |
| 飞书图片上传配置完善 | 4 张分析图未推飞书 | 日报卡片信息不完整 |
| 日期识别失败告警通知 | 只中止，无通知 | 用户不知道流程停了 |

### P1：提升产品价值

| 任务 | 收益 |
|------|------|
| 周报看板加环比对比（上周 vs 本周） | 经营趋势直观可见 |
| 异常规则引擎（同比跌>15%、折扣>40% 告警） | 自动预警，减少手工判断 |
| 飞书多维表格同步日报数据 | 形成可查询的经营数据库 |
| 老板可读的经营建议（大白话版） | 提升卡片对老板的可读性 |
| scripts/push-and-feishu-doc.sh | 把 git push 和文档同步标准化 |

### P2：未来产品化

| 任务 | 说明 |
|------|------|
| 多门店支持（御炉通明湖适配） | 门店配置模板化 |
| 月报/季报 | 更长周期经营洞察 |
| SQLite 替代 CSV | 数据规模增长后的基础设施 |
| Web Dashboard | 非技术用户可用的管理界面 |
| CaiHub API 对接 | 打通 restaurant-ai-bot 与 CaiHub 后台 |
| 小红书自动素材生成 | 把周报看板包装为内容素材 |
| HyperFrames 视频化周报 | 把看板做成动态视频 |

---

## 8. 未来规划路线图

### 阶段 1：当前最小可用闭环（2026 年 6 月）

**目标：** 稳定完成日报识别、日报推送、周报生成、周报看板推送，且 4 张分析图进入飞书。

**关键功能：**
- 完成飞书 App 自建，配置 `FEISHU_APP_ID/SECRET`
- VLM 识别 retry（最多 3 次）
- 飞书推送 retry（最多 2 次）
- `scripts/push-and-feishu-doc.sh` 自动化文档同步

**技术改造：**
- run_daily_report.py 加 retry 逻辑
- feishu_bot.py 加网络异常重试

**预期产出：** 完整闭环无需人工干预，分析图入飞书

**风险：** 飞书 App 审核需要时间

---

### 阶段 2：经营分析增强（2026 年 7 月）

**目标：** 让周报不仅展示数据，还能解释经营问题。

**关键功能：**
- 周报看板加环比对比
- 异常规则引擎（阈值告警）
- 基于 data_schema.json 的告警级别自动判断
- 趋势分析图（7 日收入曲线）

**技术改造：**
- weekly_dashboard 加环比数据模块
- analyst.py 加规则引擎层

**预期产出：** 周报从"展示数据"升级为"解释问题"

---

### 阶段 3：飞书数据底座（2026 年 8 月）

**目标：** 日报数据同步飞书多维表格，形成长期经营数据库。

**关键功能：**
- 日报写入飞书多维表格
- 从飞书多维表格查询历史数据
- 飞书文档自动同步（替代手动）

**技术改造：**
- 新增 feishu_bitable.py（飞书多维表格 API）
- history.py 支持多数据源写入

**预期产出：** 老板可在飞书中直接查看所有历史数据

---

### 阶段 4：多门店复制（2026 年 Q3）

**目标：** 支持便宜坊多个门店，独立数据、独立周报、门店对比。

**关键功能：**
- 门店配置模板（`stores/<store_id>/config.yaml`）
- 多门店统一周报汇总
- 门店排名和对比看板
- 御炉通明湖格式适配

**技术改造：**
- field_map.yaml 改为门店级配置
- store_history.csv 加 store_id 索引，或改为 SQLite

**预期产出：** 支持 3-5 家门店，老板看整体

---

### 阶段 5：CaiHub 产品化（2026 年 Q4）

**目标：** 从自动化脚本升级为餐饮经营数据产品。

**关键功能：**
- CaiHub FastAPI 后台承接数据
- 用户认证 + 多租户
- 门店自助配置
- 模板市场（不同餐厅格式模板）
- 智能分析 API

**技术改造：**
- restaurant-ai-bot 改为 CaiHub 的数据采集模块
- SQLite/PostgreSQL 替代 CSV
- React/Next.js 前端

**预期产出：** 可对外展示的 AI 餐饮数据产品原型

---

## 9. 推荐的产品架构

### 数据输入层
- 图片日报（当前主要方式）
- Excel/CSV（已支持）
- 手工录入（待建 Web 表单）
- POS/收银系统 API（未来）

### 数据处理层
- OCR/VLM 识别（已完成，需加 retry）
- 日期业务校验（已完成，严格模式）
- 字段标准化（field_map.yaml，已完成）
- 异常检测（data_schema.json 已有阈值定义，引擎待建）
- 数据质量评分（未建）

### 数据存储层
- store_history.csv（当前，适合 < 1000 条）
- SQLite（建议阶段 3 迁入，适合多门店）
- 飞书多维表格（规划阶段 3）
- 对象存储（图片归档，未来）

### 分析层
- 日报（已完成）
- 周报（已完成）
- 月报/季报（P2）
- 趋势分析（P1）
- 异常分析（P1）
- 门店对比（P2）

### 触达层
- 飞书群卡片（已完成）
- 飞书图片（日报 4 图待配置，看板已验证）
- 飞书文档（手动，待自动化）
- 飞书多维表格（规划）
- HTML/PNG 看板（已完成）
- 小红书素材（P2）
- 视频化周报（P2）

### 产品层
- CaiHub 数据后台（已有骨架）
- 门店经营驾驶舱（规划）
- 老板周报助手（规划）
- 多门店运营看板（规划）

---

## 10. 下一步 10 个具体优化任务

### Task 1：VLM 识别 JSON 解析 retry
**为什么做：** pipeline_log 中有两条 `ValueError: 图片识别返回中找不到 JSON`，导致日报中断。
**涉及文件：** `run_daily_report.py`（VLM 调用段落）
**验收标准：** 识别失败最多重试 3 次，重试日志写入 pipeline_log
**风险：** retry 会增加 LLM 费用，需设最大重试次数上限

### Task 2：飞书推送网络异常 retry
**为什么做：** pipeline_log 中有 `APIConnectionError`，飞书推送直接失败无重试。
**涉及文件：** `feishu_bot.py`（requests.post 调用段落）
**验收标准：** 网络失败自动等待 5s 重试，最多 2 次；失败后记录详细错误
**风险：** 重试期间可能重复推送，需检查幂等性

### Task 3：完善飞书 App 自建并推分析图
**为什么做：** 4 张分析图只在本地，飞书卡片信息不完整。
**涉及文件：** `.env`（配置 FEISHU_APP_ID/SECRET），`feishu_bot.py`
**验收标准：** 日报成功后，4 张分析图自动上传并在飞书群显示
**风险：** App 审核需要一定时间

### Task 4：`scripts/push-and-feishu-doc.sh` 自动文档同步
**为什么做：** 每次代码更新后，文档同步全靠手动，容易遗漏。
**涉及文件：** `scripts/push-and-feishu-doc.sh`（新建），`<临时目录>/restaurant-ai-bot-feishu-sync.md`
**验收标准：** 一条命令完成 git push + 飞书文档追加更新
**风险：** 需要 lark-cli 权限配置

### Task 5：异常规则引擎基础版
**为什么做：** data_schema.json 已定义告警阈值，但引擎未建，异常只靠 LLM 判断。
**涉及文件：** `analyst.py`，`data/data_schema.json`
**验收标准：** 折扣率 >40%、同比跌 >15% 时卡片标注红色告警，无需 LLM
**风险：** 阈值需要根据门店实际情况调整

### Task 6：周报看板加上周环比
**为什么做：** 当前看板只展示本周数据，无法判断趋势。
**涉及文件：** `skills/weekly_dashboard/render_weekly_dashboard.py`
**验收标准：** 看板新增"本周 vs 上周"营业额、客流对比柱状图
**风险：** 需要 store_history.csv 有完整的上上周数据

### Task 7：御炉通明湖门店格式适配
**为什么做：** 便宜坊只有一家店，测试图 0527.png 是御炉通明湖，格式完全不同。
**涉及文件：** `field_map.yaml`（新增门店分支），`parser.py`
**验收标准：** 御炉通明湖日报 Excel 能正确解析，字段不串行
**风险：** 需要御炉通明湖真实日报样本

### Task 8：SQLite 替代 store_history.csv
**为什么做：** CSV 在多门店、高频写入场景下性能差，无法支持并发和复杂查询。
**涉及文件：** `history.py`，`weekly_report.py`，`weekly_dashboard/render_weekly_dashboard.py`
**验收标准：** CSV 数据迁入 SQLite，所有读写操作无 API 变化，原有测试继续通过
**风险：** 数据迁移需要充分测试，避免历史数据丢失

### Task 9：飞书多维表格日报数据同步
**为什么做：** 老板希望在飞书中直接查看和筛选历史数据，不依赖命令行。
**涉及文件：** 新建 `feishu_bitable.py`，`run_daily_report.py`（新增写入步骤）
**验收标准：** 每次日报成功后，数据自动同步到指定飞书多维表格
**风险：** 需要配置飞书 App 多维表格权限

### Task 10：日报识别失败飞书告警通知
**为什么做：** 当前识别失败只中止，不通知用户，用户不知道当天日报没跑成功。
**涉及文件：** `run_daily_report.py`（失败处理段落），`feishu_bot.py`
**验收标准：** 识别或推送失败后，向飞书群发送"⚠️ 日报处理失败"简短告警卡片
**风险：** 告警本身也可能失败（网络问题），需要独立于主链路

---

## 11. 最终结论

### 当前阶段评估

这个项目已完成**"数据采集-处理-推送"的完整 MVP 验证**。截至 2026-06-01：
- 9 天真实日报数据（2026-05-24 到 2026-06-01）完整沉淀
- 一个完整自然周（2026-05-25 到 2026-05-31）的周报和看板成功推送
- 日期业务完整性校验已验证通过

### 现在最应该做什么

1. **P0：补 retry 和飞书图片推送**，让主流程真正无人值守
2. **P1：周报看板加环比，日报加更多上下文洞察**，让报告从"展示数字"升级为"辅助决策"
3. **P1：飞书文档自动同步脚本化**，降低维护成本

### 哪些事情不要急

- SQLite 改造（CSV 够用到多门店阶段）
- Web UI（飞书卡片就是 UI）
- 月报（先把周报做得足够好）
- CaiHub 打通（先跑通多门店再产品化）

### 如何包装成对外展示的 AI 餐饮数据自动化案例

**核心叙事：**
"我帮餐厅老板搭了一套 AI 数据自动化系统：每天拍一张日报截图，自动识别数据、生成分析、推送飞书。每周一自动汇总上周经营报告和可视化大屏。真实数据，零人工整理。"

**展示素材：**
1. 飞书日报卡片截图（红黄绿健康等级 + AI 建议）
2. weekly_dashboard ECharts 看板截图（深色科技风）
3. store_history.csv 数据量（从 0 到持续积累）
4. 架构图（截图→VLM→飞书闭环）
5. git commit 记录（9 天持续运行证明）

**小红书内容角度：**
- "我用 AI 帮餐厅老板省了每天 20 分钟整理报表"
- "截图→飞书经营报告，全程 AI 自动，代码开源"
- "餐饮数字化不需要 10 万 ERP，Claude + Python + 飞书就够了"
