"""配置中心。所有凭证从 .env 读,不要硬编码进代码。"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------- 路径 ----------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
PROMPT_DIR = BASE_DIR / "prompts"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------- 飞书 ----------
# 必填：自定义机器人 webhook（发文字用）
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
# 可选：自建 App 凭证（发图片用）；不填则只发文字
FEISHU_APP_ID     = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# ---------- LLM ----------
# 默认走 Anthropic Claude;切 OpenAI/通义/DeepSeek 在 analyst.py 改一下即可
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")   # anthropic | openai
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")           # 留空=官方端点;阿里百炼填 dashscope 地址

# ---------- 业务参数 ----------
# 标准字段映射(如果门店表头不一致,在这里做兼容)
FIELD_ALIASES = {
    "营业额": "revenue", "营收": "revenue", "销售额": "revenue",
    "订单数": "order_count", "订单量": "order_count", "单量": "order_count",
    "毛利": "gross_profit", "毛利额": "gross_profit",
    "客流": "customer_count", "客流量": "customer_count", "人数": "customer_count",
    "日期": "date", "门店": "store_id", "门店编号": "store_id",
    "菜品": "dish_name", "菜名": "dish_name", "销量": "qty", "数量": "qty",
}

# 周报日期校验：默认允许缺日期发送，但必须在周报中醒目标注缺失日期。
STRICT_WEEKLY_DATE_CHECK = os.getenv("STRICT_WEEKLY_DATE_CHECK", "false").lower() in {"1", "true", "yes", "y"}
