"""第 4 层:飞书推送。

消息格式:互动卡片(interactive card)
  - header  : 红/黄/绿，对应异常/警示/健康
  - KPI 行  : 4 列 —— 本日收入 / 来客数 / 客单价 / 月累同比
  - 诊断 2×2: 同比趋势 + 客流客单 / 收入结构 + 折扣健康度
  - 品类洞察 : 全宽
  - 建议列表
  - 图片     : 有 App 凭证才上传发送，否则静默跳过

.env 最小配置(纯文字+卡片):
    FEISHU_WEBHOOK=https://...

.env 完整配置(卡片 + 图片):
    FEISHU_WEBHOOK=https://...
    FEISHU_APP_ID=cli_xxxx
    FEISHU_APP_SECRET=xxxx
"""
from __future__ import annotations
import json
import time
import requests
from pathlib import Path
from typing import Optional
import config

WEBHOOK   = config.FEISHU_WEBHOOK
KEYWORD   = "日报"
OPEN_BASE = "https://open.feishu.cn/open-apis"
TOKEN_CACHE = config.OUTPUT_DIR / ".feishu_token.json"

# ── webhook 基础检查 ─────────────────────────────────────
def _check_webhook() -> None:
    if not WEBHOOK:
        raise RuntimeError("未配置 FEISHU_WEBHOOK，请在 .env 添加。")

# ── App 凭证 → tenant_access_token ──────────────────────
def _has_app_creds() -> bool:
    return bool(config.FEISHU_APP_ID and config.FEISHU_APP_SECRET)

def _get_token() -> str:
    if TOKEN_CACHE.exists():
        cache = json.loads(TOKEN_CACHE.read_text())
        if cache.get("expires_at", 0) > time.time() + 60:
            return cache["token"]
    resp = requests.post(
        f"{OPEN_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 token 失败: {data}")
    token = data["tenant_access_token"]
    TOKEN_CACHE.write_text(json.dumps({
        "token": token,
        "expires_at": time.time() + data.get("expire", 7200),
    }))
    return token

# ── 图片上传 → image_key ─────────────────────────────────
def _upload_image(image_path: Path) -> str:
    token = _get_token()
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{OPEN_BASE}/im/v1/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"image_type": "message"},
            files={"image": f},
            timeout=20,
        )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"上传图片失败 ({image_path.name}): {data}")
    return data["data"]["image_key"]

# ── 发纯文本(兜底) ────────────────────────────────────────
def send_text(text: str, ensure_keyword: bool = True) -> dict:
    _check_webhook()
    if ensure_keyword and KEYWORD not in text:
        text = f"[日报] {text}"
    resp = requests.post(
        WEBHOOK,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书推送失败: {data}")
    return data

# ── 构造互动卡片 ──────────────────────────────────────────
def _col(weight: int, *md_lines: str) -> dict:
    """快捷构造单列，md_lines 用 \n 连接成一个 lark_md div。"""
    return {
        "tag": "column",
        "width": "weighted",
        "weight": weight,
        "vertical_align": "center",
        "elements": [{
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(md_lines)},
        }],
    }

def _build_card(report: dict, meta: dict, daily: Optional[dict]) -> dict:
    health = report.get("health_level", "未知")
    header_color = {"健康": "green", "警示": "orange", "异常": "red"}.get(health, "grey")
    health_emoji  = {"健康": "🟢",   "警示": "🟡",     "异常": "🔴"}.get(health, "⚪")

    store = meta.get("store_name", meta.get("store_id", ""))
    date  = meta.get("date", "")
    diag  = report.get("diagnosis", {})
    sugs  = report.get("suggestions", [])

    elements = []

    # ── KPI 4 列（有 daily 才渲染） ──
    if daily:
        rev = daily.get("revenue", {})
        trf = daily.get("traffic", {})
        der = daily.get("derived", {})
        yoy_pct   = (der.get("yoy_pct") or 0) * 100
        yoy_delta = rev.get("revenue_yoy_delta", 0)
        yoy_arrow = "▲" if yoy_pct >= 0 else "▼"
        yoy_color = "green" if yoy_pct >= 0 else "red"

        elements.append({
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "grey",
            "columns": [
                _col(1,
                     "**本日收入**",
                     f"¥{rev.get('revenue_today', 0):,.0f}"),
                _col(1,
                     "**来客数**",
                     f"{trf.get('customer_count', 0):.0f} 人"),
                _col(1,
                     "**客单价**",
                     f"¥{trf.get('avg_check', 0):.2f}"),
                _col(1,
                     "**月累同比**",
                     f"<font color='{yoy_color}'>{yoy_arrow} {yoy_pct:+.1f}%</font>",
                     f"<font color='{yoy_color}'>差额 ¥{yoy_delta:,.0f}</font>"),
            ],
        })
        elements.append({"tag": "hr"})

    # ── 一句话总结 ──
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md",
                 "content": f"{health_emoji} **{health}级** · {report.get('headline', '—')}"},
    })
    elements.append({"tag": "hr"})

    # ── 诊断 2×2 ──
    def _diag_col(emoji: str, title: str, key: str) -> dict:
        return _col(1, f"**{emoji} {title}**", diag.get(key, "数据不足"))

    elements.append({
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "default",
        "columns": [
            _diag_col("📊", "同比趋势",    "yoy_trend"),
            _diag_col("🚶", "客流 vs 客单价", "traffic_vs_check"),
        ],
    })
    elements.append({
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "default",
        "columns": [
            _diag_col("🏪", "收入结构",   "revenue_structure"),
            _diag_col("💳", "折扣健康度", "discount_health"),
        ],
    })

    # ── 品类洞察（全宽） ──
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md",
                 "content": f"**🍽️ 品类洞察**\n{diag.get('category_insight', '数据不足')}"},
    })
    elements.append({"tag": "hr"})

    # ── 建议 ──
    sug_lines = ["**💡 明日建议**"]
    for i, s in enumerate(sugs, 1):
        sug_lines.append(f"{i}. {s}")
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "\n".join(sug_lines)},
    })

    # ── 明日重点关注（note 灰底） ──
    if report.get("watch_tomorrow"):
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text",
                          "content": f"🔎 明日重点关注：{report['watch_tomorrow']}"}],
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{store} · {date} 经营日报"},
            "template": header_color,
        },
        "elements": elements,
    }


# ── 发互动卡片 ────────────────────────────────────────────
def _send_card_payload(card: dict) -> dict:
    _check_webhook()
    resp = requests.post(
        WEBHOOK,
        json={"msg_type": "interactive", "card": card},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书卡片推送失败: {data}")
    return data

def _send_image_key(image_key: str) -> None:
    requests.post(
        WEBHOOK,
        json={"msg_type": "image", "content": {"image_key": image_key}},
        timeout=10,
    )


# ── 主入口 ────────────────────────────────────────────────
def send_card(report: dict, meta: dict,
              image_paths: Optional[list] = None,
              daily: Optional[dict] = None) -> dict:
    """发互动卡片 + 可选图片。"""
    card = _build_card(report, meta, daily)
    result = _send_card_payload(card)

    # 图片：需要 App 凭证
    if image_paths and _has_app_creds():
        for p in image_paths:
            try:
                key = _upload_image(Path(p))
                _send_image_key(key)
                print(f"[feishu] 图片已发送: {Path(p).name}")
            except Exception as e:
                print(f"[feishu] 图片发送失败 ({Path(p).name}): {e}")
    elif image_paths:
        print(f"[feishu] 未配置 App 凭证，{len(image_paths)} 张图已存 output/，跳过上传")

    return result


# ── 兜底 ─────────────────────────────────────────────────
def send_text_fallback(text: str) -> Optional[dict]:
    try:
        return send_text(text)
    except Exception as e:
        print(f"[feishu] 兜底推送失败: {e}")
        return None
