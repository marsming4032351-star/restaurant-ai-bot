# 餐饮报表数据可视化自动化项目全景图（Mermaid）

> 生成时间：2026-06-01
> 基于仓库真实状态绘制，非规划图。

## 当前数据流全链路

```mermaid
flowchart TD
    A[📸 日报截图<br/>PNG/JPG/WEBP] -->|放入| B[&lt;项目根目录&gt;/daily-input/马连道]
    B -->|inotify-like polling| C[watch_daily_folder.py<br/>launchd 开机自动监听]
    C -->|hash 去重<br/>data/watch_state.json| D[run_daily_report.py<br/>一键日报入口]
    D -->|调 VLM 视觉模型| E[图片识别<br/>提取结构化 JSON<br/>含图片表头业务日期]
    E -->|日期识别失败则中止| F{图片表头<br/>日期识别}
    F -->|成功| G[image_to_excel.py<br/>JSON → 标准 Excel]
    F -->|失败| HALT[🚫 中止，不 fallback 系统日期]
    G --> H[data/便宜坊马连道_YYYY-MM-DD.xlsx]
    H --> I[main.py<br/>日报全流程]
    I --> J[parser.py<br/>关键字定位解析 Excel]
    I --> K[analyst.py<br/>调 Qwen LLM 生成诊断 JSON]
    I --> L[visualizer.py<br/>matplotlib 4 张分析图]
    I --> M[feishu_bot.py<br/>构造飞书互动卡片]
    J & K & L --> M
    M -->|FEISHU_WEBHOOK| N[飞书群 · 日报卡片推送]
    L --> O[output/kpi/categories/member/revenue_struct PNG]
    M -->|可选 FEISHU_APP_ID/SECRET| P[飞书群 · 图片上传推送<br/>⚠️ 当前未配置]
    I --> Q[history.py<br/>写入 data/store_history.csv]
    I --> R[output/report_MLD_YYYY-MM-DD.json]
    Q & R --> S[data/pipeline_state.json<br/>data/pipeline_log.csv 更新]
    S -->|git add/commit/push| T[GitHub private repo]

    subgraph 周报触发链路
        S -->|仅当日报业务日期=周日<br/>且运行日=周一| U[weekly_auto.py<br/>条件检查]
        U -->|检查 weekly_state.json 防重复| V[weekly_report.py<br/>读 store_history.csv 统计]
        V -->|缺失日期提示不伪造| W[飞书群 · 周报卡片推送]
        V --> X[skills/weekly_dashboard/<br/>render_weekly_dashboard.py]
        X --> Y[output/weekly_dashboard_*.html]
        X --> Z[output/weekly_dashboard_*.png]
        Z -->|--send-to-feishu 可选| AA[飞书群 · 看板图片推送]
    end

    subgraph 状态与文档
        T --> AB[data/weekly_state.json 防重复]
        T -.->|手动触发| AC[飞书文档同步<br/>⚠️ 当前无自动化脚本]
    end
```

## 产品模块状态全景图

```mermaid
graph LR
    subgraph 已完成 ✅
        A1[截图监听<br/>launchd]
        A2[VLM 图片识别<br/>日期校验]
        A3[Excel 生成]
        A4[日报 AI 诊断<br/>Qwen LLM]
        A5[飞书日报卡片]
        A6[历史数据沉淀<br/>store_history.csv]
        A7[周报自动触发<br/>weekly_auto]
        A8[周报卡片推送]
        A9[weekly_dashboard<br/>ECharts HTML/PNG]
        A10[Git 自动提交]
        A11[数据日期完整性校验]
    end

    subgraph 进行中 🔧
        B1[飞书图片推送<br/>需 App 凭证]
        B2[分析图推送飞书]
        B3[飞书文档自动同步<br/>当前手动]
    end

    subgraph 未来规划 📋
        C1[御炉通明湖<br/>多格式适配]
        C2[飞书多维表格同步]
        C3[异常规则引擎]
        C4[趋势分析图<br/>7日/30日]
        C5[月报/季报]
        C6[多门店支持]
        C7[Web Dashboard]
        C8[CaiHub 产品化]
        C9[小红书素材生成]
        C10[HyperFrames 视频周报]
    end
```

## 推荐未来架构

```mermaid
graph TB
    subgraph 数据输入层
        I1[截图/图片]
        I2[Excel/CSV]
        I3[手工录入]
        I4[POS API]
    end

    subgraph 数据处理层
        P1[VLM/OCR 识别]
        P2[日期业务校验]
        P3[字段标准化]
        P4[异常检测引擎]
        P5[数据质量评分]
    end

    subgraph 存储层
        S1[store_history.csv<br/>当前]
        S2[SQLite/PostgreSQL<br/>建议]
        S3[飞书多维表格<br/>规划]
        S4[对象存储图片]
    end

    subgraph 分析层
        A1[日报分析]
        A2[周报统计]
        A3[月报/季报]
        A4[趋势分析]
        A5[门店对比]
    end

    subgraph 触达层
        O1[飞书群卡片]
        O2[飞书文档]
        O3[飞书多维表格]
        O4[PNG/HTML 看板]
        O5[小红书素材]
    end

    subgraph 产品层
        PR1[CaiHub 数据后台]
        PR2[门店驾驶舱]
        PR3[老板周报助手]
        PR4[多门店看板]
    end

    数据输入层 --> 数据处理层 --> 存储层 --> 分析层 --> 触达层 --> 产品层
```
