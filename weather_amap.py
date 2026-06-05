"""高德天气客户端 + 运营天气上下文（可选附加层）。

设计原则（与项目「绝不伪造数据」一致）：
- 高德免费版只有"实时实况 + 未来预报(今天~未来3天)"，没有历史天气。
- business_date 通常是"昨天"（截图次日处理）。采集当下查到的是"采集日"天气，
  绝不能当成 business_date 当天天气写入。
- 因此诚实拆成三块：
  1. live：采集时刻实况（明确带 observed_at 时间戳 + 对应城市）。
  2. forecast：高德预报里"采集日及未来几天"的预报（用于"明日建议"弱参考）。
  3. weather_for_business_date：只有 business_date == 采集日 时才用实况填充；
     否则诚实记 "暂无（高德免费版无历史天气）"。
- 任何异常 / 未配置 key / 无 requests → 全部记"暂无"，never raise，不阻断日报主流程。

主入口：build_weather_context(business_date, collection_date=None) -> dict
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import config

AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"

# 诚实的"无数据"占位，绝不编造
_NA = "暂无"


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _empty_context(business_date: str, collection_date: str, reason: str) -> dict:
    """统一的降级上下文（诚实标注原因，不伪造任何天气值）。"""
    return {
        "weather_status": "unavailable",
        "weather_unavailable_reason": reason,
        "weather_provider": config.WEATHER_PROVIDER,
        "weather_city": config.WEATHER_CITY_NAME,
        "business_date": business_date,
        "collection_date": collection_date,
        "collection_equals_business_date": business_date == collection_date,
        # 业务日期当天天气（只在采集日==业务日且取到实况时才有值）
        "weather_for_business_date": _NA,
        "business_date_weather_note": reason,
        # 采集时刻实况
        "live_observed_at": None,
        "live_weather": _NA,
        "live_temperature_c": _NA,
        "live_humidity": _NA,
        "live_wind": _NA,
        # 预报（采集日及未来）
        "forecast": [],
        "forecast_note": reason,
    }


def _fetch_amap(extensions: str) -> dict[str, Any] | None:
    """调用高德天气；失败返回 None（不抛异常）。extensions: base=实况, all=预报。"""
    if not config.WEATHER_API_KEY:
        return None
    try:
        import requests  # 局部导入，缺失也不阻断
    except ImportError:
        return None
    try:
        resp = requests.get(
            AMAP_WEATHER_URL,
            params={
                "key": config.WEATHER_API_KEY,
                "city": config.WEATHER_CITY_ADCODE,
                "extensions": extensions,
                "output": "JSON",
            },
            timeout=config.WEATHER_TIMEOUT,
        )
        data = resp.json()
    except Exception:
        return None
    # 高德成功响应 status == "1"
    if str(data.get("status")) != "1":
        return None
    return data


def build_weather_context(business_date, collection_date=None) -> dict:
    """构建运营天气上下文（诚实、可降级，绝不伪造，绝不抛异常）。

    business_date：日报业务日期（来自图片表头）。
    collection_date：采集天气的日期（默认取系统今天；仅用于天气采集，不参与业务日期）。
    """
    bd = _parse_date(business_date)
    bd_s = bd.isoformat()
    cd = _parse_date(collection_date) if collection_date is not None else date.today()
    cd_s = cd.isoformat()

    if not config.WEATHER_ENABLED:
        return _empty_context(bd_s, cd_s, "天气功能未启用(WEATHER_ENABLED=false)")
    if config.WEATHER_PROVIDER != "amap":
        return _empty_context(bd_s, cd_s, f"暂不支持的天气provider:{config.WEATHER_PROVIDER}")
    if not config.WEATHER_API_KEY:
        return _empty_context(bd_s, cd_s, "未配置WEATHER_API_KEY，天气暂无（不伪造）")

    ctx = _empty_context(bd_s, cd_s, "")
    ctx["weather_unavailable_reason"] = ""

    got_any = False

    # 1. 实况（采集时刻）
    live = _fetch_amap("base")
    if live and live.get("lives"):
        info = live["lives"][0]
        ctx["live_observed_at"] = _now_iso()
        ctx["live_weather"] = info.get("weather") or _NA
        ctx["live_temperature_c"] = info.get("temperature") or _NA
        ctx["live_humidity"] = info.get("humidity") or _NA
        wind_dir = info.get("winddirection") or ""
        wind_pow = info.get("windpower") or ""
        ctx["live_wind"] = (f"{wind_dir}风{wind_pow}级".strip() or _NA) if (wind_dir or wind_pow) else _NA
        if info.get("city"):
            ctx["weather_city"] = info.get("city")
        got_any = True

    # 2. 预报（采集日 + 未来3天）
    fc = _fetch_amap("all")
    if fc and fc.get("forecasts"):
        casts = fc["forecasts"][0].get("casts", []) or []
        norm = []
        for c in casts:
            norm.append({
                "date": c.get("date"),
                "week": c.get("week"),
                "day_weather": c.get("dayweather"),
                "night_weather": c.get("nightweather"),
                "day_temp_c": c.get("daytemp"),
                "night_temp_c": c.get("nighttemp"),
                "day_wind": (c.get("daywind") or "") + (c.get("daypower") or ""),
            })
        ctx["forecast"] = norm
        ctx["forecast_note"] = "高德预报(采集日及未来数天)，相对采集日；用于明日经营建议弱参考"
        got_any = True

    # 3. 业务日期当天天气：只有采集日==业务日 且 拿到实况 时才据实填充
    if ctx["collection_equals_business_date"] and ctx["live_weather"] != _NA:
        ctx["weather_for_business_date"] = (
            f"{ctx['live_weather']} {ctx['live_temperature_c']}℃ {ctx['live_wind']}".strip()
        )
        ctx["business_date_weather_note"] = "采集日==业务日，取采集时刻实况"
    else:
        # 业务日期是过去日期：高德免费版无历史天气，诚实留空
        ctx["weather_for_business_date"] = _NA
        if not ctx["collection_equals_business_date"]:
            ctx["business_date_weather_note"] = (
                "业务日期为过去日期，高德免费版无历史天气，故业务日当天天气暂无；"
                "仅提供采集时刻实况与预报作为弱参考。"
            )
        else:
            ctx["business_date_weather_note"] = "未取到实况，业务日当天天气暂无。"

    if got_any:
        ctx["weather_status"] = "ok"
    else:
        ctx["weather_status"] = "unavailable"
        ctx["weather_unavailable_reason"] = "高德天气接口未返回有效数据（key/网络/额度），天气暂无（不伪造）"

    return ctx


if __name__ == "__main__":
    import json
    import sys
    bdate = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(json.dumps(build_weather_context(bdate), ensure_ascii=False, indent=2))
