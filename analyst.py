"""第 2 层:AI 主动分析 Agent。

把 parser 输出的结构化数据 + 诊断 prompt 喂给 LLM,
要求 LLM 输出固定 JSON,后面的飞书卡片就可以稳定渲染。
"""
from __future__ import annotations
import datetime
import json
import re
from pathlib import Path
import config


class _DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return str(obj)
        return super().default(obj)


def _load_prompt() -> str:
    return (config.PROMPT_DIR / "diagnose.txt").read_text(encoding="utf-8")


def _extract_json(text: str) -> dict:
    """从 LLM 返回里提 JSON(兼容 markdown 包裹和带前后注释)。"""
    # 优先抓 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # 否则抓第一个 {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"LLM 返回里找不到 JSON:\n{text[:500]}")


def _call_anthropic(system: str, user: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    resp = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI
    kwargs = {"api_key": config.LLM_API_KEY}
    if config.LLM_BASE_URL:
        kwargs["base_url"] = config.LLM_BASE_URL
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content


def diagnose(daily: dict) -> dict:
    """主入口:跑一次完整诊断,返回结构化 JSON。

    daily 形如 parser.enrich_with_history 的输出。
    """
    system = _load_prompt()
    user = "请基于以下经营数据生成日报 JSON:\n```json\n" + json.dumps(daily, cls=_DateEncoder, ensure_ascii=False, indent=2) + "\n```"

    if config.LLM_PROVIDER == "anthropic":
        raw = _call_anthropic(system, user)
    elif config.LLM_PROVIDER == "openai":
        raw = _call_openai(system, user)
    else:
        raise ValueError(f"未知 LLM_PROVIDER: {config.LLM_PROVIDER}")

    result = _extract_json(raw)
    # 兜底:必备字段缺失时填默认
    result.setdefault("health_level", "未知")
    result.setdefault("headline", "")
    result.setdefault("diagnosis", {})
    result.setdefault("suggestions", [])
    result.setdefault("watch_tomorrow", "")
    return result
