"""离线测试:只跑解析层和可视化层(不依赖 LLM/飞书凭证)。"""
import json
from pathlib import Path
import parser as P
import visualizer

xlsx = Path("data") / "便宜坊马连道_2026-05-27.xlsx"

print("=" * 60)
print("🔍 第 1 步:解析 Excel")
print("=" * 60)
daily = P.load_daily(xlsx)
P.append_history(daily)
daily = P.enrich_with_history(daily)

print("\n" + "=" * 60)
print("📊 第 2 步:抽取的关键字段")
print("=" * 60)
print(f"\n[meta]")
for k, v in daily["meta"].items():
    print(f"  {k}: {v}")

print(f"\n[revenue] 重点字段")
for k in ["revenue_today", "revenue_month_to_date", "revenue_same_period_last_year",
          "revenue_yoy_delta", "dine_in_revenue", "online_takeaway_revenue",
          "revenue_today_before_discount"]:
    v = daily["revenue"].get(k, "<缺失>")
    print(f"  {k}: {v}")

print(f"\n[member_consumption]")
for k, v in daily["member_consumption"].items():
    print(f"  {k}: {v}")

print(f"\n[traffic]")
for k, v in daily["traffic"].items():
    print(f"  {k}: {v}")

print(f"\n[derived] 派生指标")
for k, v in daily["derived"].items():
    print(f"  {k}: {v}")

print(f"\n[dishes_by_category] 各品类销量")
for cat, fields in daily["dishes_by_category"].items():
    total = sum(v for k, v in fields.items()
                if isinstance(v, (int, float)) and "ratio" not in k)
    print(f"  {cat}: 总销量 {total}")
    for k, v in fields.items():
        if v:
            print(f"    - {k}: {v}")

print("\n" + "=" * 60)
print("🎨 第 3 步:出图")
print("=" * 60)
charts = visualizer.make_all_charts(daily)
for c in charts:
    print(f"  ✓ {c.name}  ({c.stat().st_size / 1024:.1f} KB)")

out_json = Path("output") / "parsed_dump.json"
out_json.write_text(json.dumps(daily, ensure_ascii=False, indent=2, default=str))
print(f"\n💾 完整解析结果已写入 {out_json}")
