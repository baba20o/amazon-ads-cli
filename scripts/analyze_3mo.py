"""Analyze 3-month US report data (Nov 18 2025 - Feb 18 2026)."""
import json
import glob
from pathlib import Path
from collections import defaultdict


def load_all(pattern):
    """Load and combine all JSON files matching a glob pattern."""
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path) as f:
            rows.extend(json.load(f))
    return rows


def main():
    data_dir = "data/reports"

    campaigns = load_all(f"{data_dir}/US-spCampaigns-*.json")
    keywords = load_all(f"{data_dir}/US-spKeywords-*.json")
    searchterms = load_all(f"{data_dir}/US-spSearchTerm-*.json")
    targeting = load_all(f"{data_dir}/US-spTargeting-*.json")

    print("=" * 70)
    print("US 3-MONTH ANALYSIS (Nov 18, 2025 - Feb 18, 2026)")
    print("=" * 70)
    print(f"Data: {len(campaigns)} campaign rows, {len(keywords)} keyword rows,")
    print(f"      {len(searchterms)} search term rows, {len(targeting)} targeting rows")

    # ── Overall metrics ───────────────────────────────────────────────
    total_cost = sum(float(r.get("cost", 0)) for r in campaigns)
    total_sales = sum(float(r.get("sales1d", 0)) for r in campaigns)
    total_impressions = sum(int(r.get("impressions", 0)) for r in campaigns)
    total_clicks = sum(int(r.get("clicks", 0)) for r in campaigns)
    total_purchases = sum(int(r.get("purchases1d", 0)) for r in campaigns)
    acos = (total_cost / total_sales * 100) if total_sales > 0 else 0

    print(f"\n--- OVERALL ---")
    print(f"Total cost:       ${total_cost:,.2f}")
    print(f"Total sales:      ${total_sales:,.2f}")
    print(f"ACoS:             {acos:.1f}%")
    print(f"Impressions:      {total_impressions:,}")
    print(f"Clicks:           {total_clicks:,}")
    print(f"Purchases:        {total_purchases:,}")
    if total_clicks:
        print(f"CPC:              ${total_cost/total_clicks:.2f}")
        print(f"Conv Rate:        {total_purchases/total_clicks*100:.1f}%")
    if total_purchases:
        print(f"Cost per Acq:     ${total_cost/total_purchases:.2f}")

    # ── Monthly trends ────────────────────────────────────────────────
    print(f"\n--- MONTHLY TRENDS ---")
    monthly = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0})
    for r in campaigns:
        d = r.get("date", "")
        month = d[:7] if d else "unknown"
        monthly[month]["cost"] += float(r.get("cost", 0))
        monthly[month]["sales"] += float(r.get("sales1d", 0))
        monthly[month]["clicks"] += int(r.get("clicks", 0))
        monthly[month]["impressions"] += int(r.get("impressions", 0))
        monthly[month]["purchases"] += int(r.get("purchases1d", 0))

    for month in sorted(monthly.keys()):
        d = monthly[month]
        acos_val = (d["cost"] / d["sales"] * 100) if d["sales"] > 0 else 0
        print(f"  {month}: cost=${d['cost']:>8.2f}  sales=${d['sales']:>8.2f}  ACoS={acos_val:>5.1f}%  clicks={d['clicks']:>5d}  purchases={d['purchases']:>3d}")

    # ── Campaign performance (aggregated across months) ───────────────
    print(f"\n--- TOP 15 CAMPAIGNS BY SPEND (3 months) ---")
    camp_data = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0})
    for r in campaigns:
        name = r.get("campaignName", "Unknown")
        camp_data[name]["cost"] += float(r.get("cost", 0))
        camp_data[name]["sales"] += float(r.get("sales1d", 0))
        camp_data[name]["clicks"] += int(r.get("clicks", 0))
        camp_data[name]["impressions"] += int(r.get("impressions", 0))
        camp_data[name]["purchases"] += int(r.get("purchases1d", 0))

    top = sorted(camp_data.items(), key=lambda x: x[1]["cost"], reverse=True)[:15]
    for name, d in top:
        if d["sales"] > 0:
            acos_str = f'{d["cost"]/d["sales"]*100:.0f}%'
        else:
            acos_str = "N/A"
        short = name[:50]
        print(f'  {short:<52s} ${d["cost"]:>8.2f}  sales=${d["sales"]:>8.2f}  ACoS={acos_str:>5s}  purch={d["purchases"]}')

    # ── AUTO vs MANUAL ────────────────────────────────────────────────
    print(f"\n--- AUTO vs MANUAL CAMPAIGNS ---")
    auto = {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0, "count": 0}
    manual = {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0, "count": 0}
    for name, d in camp_data.items():
        bucket = auto if "AUTOMATIC" in name.upper() or "AUTO" in name.upper() else manual
        for k in ["cost", "sales", "clicks", "impressions", "purchases"]:
            bucket[k] += d[k]
        bucket["count"] += 1

    for label, d in [("AUTO", auto), ("MANUAL", manual)]:
        acos_val = (d["cost"] / d["sales"] * 100) if d["sales"] > 0 else 0
        cpc = d["cost"] / d["clicks"] if d["clicks"] else 0
        conv = d["purchases"] / d["clicks"] * 100 if d["clicks"] else 0
        print(f"  {label:<8s} ({d['count']:>3d} campaigns): cost=${d['cost']:>8.2f}  sales=${d['sales']:>8.2f}  ACoS={acos_val:>5.1f}%  CPC=${cpc:.2f}  conv={conv:.1f}%")

    # ── Targeting type breakdown ──────────────────────────────────────
    print(f"\n--- TARGETING TYPE PERFORMANCE ---")
    type_data = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "rows": 0})
    for r in targeting:
        kt = r.get("keywordType", "UNKNOWN")
        type_data[kt]["cost"] += float(r.get("cost", 0))
        type_data[kt]["sales"] += float(r.get("sales1d", 0))
        type_data[kt]["clicks"] += int(r.get("clicks", 0))
        type_data[kt]["impressions"] += int(r.get("impressions", 0))
        type_data[kt]["rows"] += 1

    for kt in sorted(type_data.keys(), key=lambda k: type_data[k]["cost"], reverse=True):
        d = type_data[kt]
        if d["sales"] > 0:
            acos_str = f'{d["cost"]/d["sales"]*100:.0f}%'
        else:
            acos_str = "N/A"
        cpc = d["cost"] / d["clicks"] if d["clicks"] else 0
        print(f'  {kt:<40s} cost=${d["cost"]:>8.2f}  sales=${d["sales"]:>8.2f}  ACoS={acos_str:>5s}  CPC=${cpc:.2f}')

    # ── Money burners (campaigns spending > $20 with ACoS > 100% or no sales)
    print(f"\n--- MONEY BURNERS (>$20 spent, ACoS>100% or no sales) ---")
    burners = [(n, d) for n, d in camp_data.items() if d["cost"] > 20 and (d["sales"] == 0 or d["cost"]/max(d["sales"], 0.01) > 1)]
    burners.sort(key=lambda x: x[1]["cost"], reverse=True)
    total_wasted = 0
    for name, d in burners[:15]:
        if d["sales"] > 0:
            acos_str = f'{d["cost"]/d["sales"]*100:.0f}%'
            waste = d["cost"] - d["sales"]
        else:
            acos_str = "NO SALES"
            waste = d["cost"]
        total_wasted += waste
        short = name[:50]
        print(f'  {short:<52s} ${d["cost"]:>8.2f}  sales=${d["sales"]:>8.2f}  {acos_str}')
    print(f"\n  Total wasted on money burners: ${total_wasted:,.2f}")

    # ── Top keywords by sales ─────────────────────────────────────────
    print(f"\n--- TOP 15 KEYWORDS BY SALES ---")
    kw_data = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0})
    for r in keywords:
        kw = r.get("keyword", "") or r.get("keywordText", "Unknown")
        kw_data[kw]["cost"] += float(r.get("cost", 0))
        kw_data[kw]["sales"] += float(r.get("sales1d", 0))
        kw_data[kw]["clicks"] += int(r.get("clicks", 0))
        kw_data[kw]["impressions"] += int(r.get("impressions", 0))

    top_kw = sorted(kw_data.items(), key=lambda x: x[1]["sales"], reverse=True)[:15]
    for kw, d in top_kw:
        acos_val = (d["cost"] / d["sales"] * 100) if d["sales"] > 0 else float("inf")
        short = kw[:40]
        print(f'  {short:<42s} sales=${d["sales"]:>8.2f}  cost=${d["cost"]:>7.2f}  ACoS={acos_val:.0f}%  clicks={d["clicks"]}')

    # ── Worst keywords (high cost, no sales) ──────────────────────────
    print(f"\n--- WORST KEYWORDS (>$10 spent, no sales) ---")
    waste_kw = [(kw, d) for kw, d in kw_data.items() if d["cost"] > 10 and d["sales"] == 0]
    waste_kw.sort(key=lambda x: x[1]["cost"], reverse=True)
    for kw, d in waste_kw[:10]:
        short = kw[:42]
        print(f'  {short:<44s} cost=${d["cost"]:>7.2f}  clicks={d["clicks"]:>4d}  impr={d["impressions"]:>7d}')

    # ── Top search terms by sales ─────────────────────────────────────
    print(f"\n--- TOP 15 SEARCH TERMS BY SALES ---")
    st_data = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0})
    for r in searchterms:
        term = r.get("searchTerm", "Unknown")
        st_data[term]["cost"] += float(r.get("cost", 0))
        st_data[term]["sales"] += float(r.get("sales1d", 0))
        st_data[term]["clicks"] += int(r.get("clicks", 0))

    top_st = sorted(st_data.items(), key=lambda x: x[1]["sales"], reverse=True)[:15]
    for term, d in top_st:
        acos_val = (d["cost"] / d["sales"] * 100) if d["sales"] > 0 else float("inf")
        short = term[:42]
        print(f'  {short:<44s} sales=${d["sales"]:>8.2f}  cost=${d["cost"]:>7.2f}  ACoS={acos_val:.0f}%')

    # ── Wasted search terms ───────────────────────────────────────────
    print(f"\n--- WASTED SEARCH TERMS (>$5 spent, no sales) ---")
    waste_st = [(t, d) for t, d in st_data.items() if d["cost"] > 5 and d["sales"] == 0]
    waste_st.sort(key=lambda x: x[1]["cost"], reverse=True)
    total_wasted_st = sum(d["cost"] for _, d in waste_st)
    for term, d in waste_st[:15]:
        short = term[:44]
        print(f'  {short:<46s} cost=${d["cost"]:>7.2f}  clicks={d["clicks"]:>3d}')
    print(f"\n  Total wasted on zero-sale search terms (>$5): ${total_wasted_st:,.2f}")

    print(f"\n" + "=" * 70)
    print("DATA FILES:")
    for pattern, label in [
        (f"{data_dir}/US-spCampaigns-*.json", "Campaigns"),
        (f"{data_dir}/US-spKeywords-*.json", "Keywords"),
        (f"{data_dir}/US-spSearchTerm-*.json", "Search Terms"),
        (f"{data_dir}/US-spTargeting-*.json", "Targeting"),
    ]:
        files = sorted(glob.glob(pattern))
        total = sum(len(json.load(open(f))) for f in files)
        print(f"  {label:<15s} {len(files)} files, {total:,} total rows")
    print("=" * 70)


if __name__ == "__main__":
    main()
