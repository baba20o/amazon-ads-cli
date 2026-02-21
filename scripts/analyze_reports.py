"""Analyze the 4 US reports and print a summary."""
import json
import sys

def main():
    # Load all 4 reports
    with open("reports/us_campaigns.json") as f:
        campaigns = json.load(f)
    with open("reports/us_keywords.json") as f:
        keywords = json.load(f)
    with open("reports/us_searchterms.json") as f:
        searchterms = json.load(f)
    with open("reports/us_targeting.json") as f:
        targeting = json.load(f)

    print("=" * 70)
    print("US REPORT SUMMARY (Feb 13-19, 2026)")
    print("=" * 70)

    # ── Campaign summary ──────────────────────────────────────────────
    print(f"\n--- CAMPAIGNS ({len(campaigns)} rows) ---")
    total_cost = sum(float(r.get("cost", 0)) for r in campaigns)
    total_sales = sum(float(r.get("sales1d", 0)) for r in campaigns)
    total_impressions = sum(int(r.get("impressions", 0)) for r in campaigns)
    total_clicks = sum(int(r.get("clicks", 0)) for r in campaigns)
    total_purchases = sum(int(r.get("purchases1d", 0)) for r in campaigns)
    acos = (total_cost / total_sales * 100) if total_sales > 0 else 0
    unique_campaigns = len(set(r.get("campaignId") for r in campaigns))
    print(f"Unique campaigns: {unique_campaigns}")
    print(f"Total cost:       ${total_cost:,.2f}")
    print(f"Total sales:      ${total_sales:,.2f}")
    print(f"Total impressions: {total_impressions:,}")
    print(f"Total clicks:     {total_clicks:,}")
    print(f"Total purchases:  {total_purchases:,}")
    print(f"ACoS:             {acos:.1f}%")
    if total_impressions:
        print(f"CTR:              {(total_clicks/total_impressions*100):.2f}%")
    if total_clicks:
        print(f"CPC:              ${(total_cost/total_clicks):.2f}")
        print(f"Conv Rate:        {(total_purchases/total_clicks*100):.1f}%")

    # Top 10 campaigns by spend
    print(f"\n--- TOP 10 CAMPAIGNS BY SPEND ---")
    camp_spend = {}
    for r in campaigns:
        cid = r.get("campaignName", "Unknown")
        if cid not in camp_spend:
            camp_spend[cid] = {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0}
        camp_spend[cid]["cost"] += float(r.get("cost", 0))
        camp_spend[cid]["sales"] += float(r.get("sales1d", 0))
        camp_spend[cid]["clicks"] += int(r.get("clicks", 0))
        camp_spend[cid]["impressions"] += int(r.get("impressions", 0))
        camp_spend[cid]["purchases"] += int(r.get("purchases1d", 0))

    top = sorted(camp_spend.items(), key=lambda x: x[1]["cost"], reverse=True)[:10]
    for name, d in top:
        if d["sales"] > 0:
            acos_str = f'{(d["cost"]/d["sales"]*100):.0f}%'
        else:
            acos_str = "N/A"
        short = name[:50]
        print(f'  {short:<52s} ${d["cost"]:>8.2f}  sales=${d["sales"]:>8.2f}  ACoS={acos_str:>5s}  purchases={d["purchases"]}')

    # Money burners (high spend, no/low sales)
    print(f"\n--- MONEY BURNERS (spend >$5, ACoS >100% or no sales) ---")
    burners = [(n, d) for n, d in camp_spend.items() if d["cost"] > 5 and (d["sales"] == 0 or d["cost"]/d["sales"] > 1)]
    burners.sort(key=lambda x: x[1]["cost"], reverse=True)
    for name, d in burners[:10]:
        if d["sales"] > 0:
            acos_str = f'{(d["cost"]/d["sales"]*100):.0f}%'
        else:
            acos_str = "NO SALES"
        short = name[:50]
        print(f'  {short:<52s} ${d["cost"]:>8.2f}  sales=${d["sales"]:>8.2f}  {acos_str}')

    # ── Keywords summary ──────────────────────────────────────────────
    print(f"\n--- KEYWORDS ({len(keywords)} rows) ---")
    kw_cost = sum(float(r.get("cost", 0)) for r in keywords)
    kw_sales = sum(float(r.get("sales1d", 0)) for r in keywords)
    kw_clicks = sum(int(r.get("clicks", 0)) for r in keywords)
    unique_kw = len(set(r.get("keywordId") for r in keywords))
    print(f"Unique keywords:  {unique_kw}")
    print(f"Total cost:       ${kw_cost:,.2f}")
    print(f"Total sales:      ${kw_sales:,.2f}")
    if kw_sales > 0:
        print(f"ACoS:             {(kw_cost/kw_sales*100):.1f}%")

    # Top performing keywords
    print(f"\n--- TOP 10 KEYWORDS BY SALES ---")
    kw_perf = {}
    for r in keywords:
        kid = r.get("keyword", "") or r.get("keywordText", "Unknown")
        if kid not in kw_perf:
            kw_perf[kid] = {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0}
        kw_perf[kid]["cost"] += float(r.get("cost", 0))
        kw_perf[kid]["sales"] += float(r.get("sales1d", 0))
        kw_perf[kid]["clicks"] += int(r.get("clicks", 0))
        kw_perf[kid]["impressions"] += int(r.get("impressions", 0))

    top_kw = sorted(kw_perf.items(), key=lambda x: x[1]["sales"], reverse=True)[:10]
    for kw, d in top_kw:
        acos_val = (d["cost"]/d["sales"]*100) if d["sales"] > 0 else float("inf")
        short = kw[:40]
        print(f'  {short:<42s} sales=${d["sales"]:>8.2f}  cost=${d["cost"]:>7.2f}  ACoS={acos_val:.0f}%  clicks={d["clicks"]}')

    # Worst performing keywords (high cost, no sales)
    print(f"\n--- WORST KEYWORDS (spend >$3, no sales) ---")
    waste_kw = [(kw, d) for kw, d in kw_perf.items() if d["cost"] > 3 and d["sales"] == 0]
    waste_kw.sort(key=lambda x: x[1]["cost"], reverse=True)
    for kw, d in waste_kw[:10]:
        short = kw[:42]
        print(f'  {short:<44s} cost=${d["cost"]:>7.2f}  clicks={d["clicks"]:>4d}  impressions={d["impressions"]:>6d}')

    # ── Search terms ──────────────────────────────────────────────────
    print(f"\n--- SEARCH TERMS ({len(searchterms)} rows) ---")
    st_cost = sum(float(r.get("cost", 0)) for r in searchterms)
    st_sales = sum(float(r.get("sales1d", 0)) for r in searchterms)
    unique_st = len(set(r.get("searchTerm") for r in searchterms))
    print(f"Unique terms:     {unique_st}")
    print(f"Total cost:       ${st_cost:,.2f}")
    print(f"Total sales:      ${st_sales:,.2f}")
    if st_sales > 0:
        print(f"ACoS:             {(st_cost/st_sales*100):.1f}%")

    # Top search terms by sales
    print(f"\n--- TOP 10 SEARCH TERMS BY SALES ---")
    st_perf = {}
    for r in searchterms:
        term = r.get("searchTerm", "Unknown")
        if term not in st_perf:
            st_perf[term] = {"cost": 0, "sales": 0, "clicks": 0}
        st_perf[term]["cost"] += float(r.get("cost", 0))
        st_perf[term]["sales"] += float(r.get("sales1d", 0))
        st_perf[term]["clicks"] += int(r.get("clicks", 0))

    top_st = sorted(st_perf.items(), key=lambda x: x[1]["sales"], reverse=True)[:10]
    for term, d in top_st:
        acos_val = (d["cost"]/d["sales"]*100) if d["sales"] > 0 else float("inf")
        short = term[:42]
        print(f'  {short:<44s} sales=${d["sales"]:>8.2f}  cost=${d["cost"]:>7.2f}  ACoS={acos_val:.0f}%')

    # Wasted search terms
    print(f"\n--- WASTED SEARCH TERMS (spend >$2, no sales) ---")
    waste_st = [(t, d) for t, d in st_perf.items() if d["cost"] > 2 and d["sales"] == 0]
    waste_st.sort(key=lambda x: x[1]["cost"], reverse=True)
    for term, d in waste_st[:10]:
        short = term[:44]
        print(f'  {short:<46s} cost=${d["cost"]:>7.2f}  clicks={d["clicks"]:>3d}')

    # ── Targeting ─────────────────────────────────────────────────────
    print(f"\n--- TARGETING ({len(targeting)} rows) ---")
    tg_cost = sum(float(r.get("cost", 0)) for r in targeting)
    tg_sales = sum(float(r.get("sales1d", 0)) for r in targeting)
    unique_tg = len(set(r.get("keywordId") for r in targeting))
    print(f"Unique targets:   {unique_tg}")
    print(f"Total cost:       ${tg_cost:,.2f}")
    print(f"Total sales:      ${tg_sales:,.2f}")
    if tg_sales > 0:
        print(f"ACoS:             {(tg_cost/tg_sales*100):.1f}%")

    # Targeting by type
    print(f"\n--- TARGETING BY TYPE ---")
    type_perf = {}
    for r in targeting:
        kt = r.get("keywordType", "Unknown")
        if kt not in type_perf:
            type_perf[kt] = {"cost": 0, "sales": 0, "clicks": 0, "count": 0}
        type_perf[kt]["cost"] += float(r.get("cost", 0))
        type_perf[kt]["sales"] += float(r.get("sales1d", 0))
        type_perf[kt]["clicks"] += int(r.get("clicks", 0))
        type_perf[kt]["count"] += 1

    for kt, d in sorted(type_perf.items(), key=lambda x: x[1]["cost"], reverse=True):
        if d["sales"] > 0:
            acos_str = f'{(d["cost"]/d["sales"]*100):.0f}%'
        else:
            acos_str = "N/A"
        print(f'  {kt:<30s} cost=${d["cost"]:>8.2f}  sales=${d["sales"]:>8.2f}  ACoS={acos_str:>5s}  rows={d["count"]}')

    # Top targeting by sales
    print(f"\n--- TOP 10 TARGETS BY SALES ---")
    tg_perf = {}
    for r in targeting:
        expr = r.get("targeting", "") or "Unknown"
        if expr not in tg_perf:
            tg_perf[expr] = {"cost": 0, "sales": 0, "clicks": 0, "type": r.get("keywordType", "")}
        tg_perf[expr]["cost"] += float(r.get("cost", 0))
        tg_perf[expr]["sales"] += float(r.get("sales1d", 0))
        tg_perf[expr]["clicks"] += int(r.get("clicks", 0))

    top_tg = sorted(tg_perf.items(), key=lambda x: x[1]["sales"], reverse=True)[:10]
    for expr, d in top_tg:
        acos_val = (d["cost"]/d["sales"]*100) if d["sales"] > 0 else float("inf")
        short = expr[:42]
        print(f'  {short:<44s} sales=${d["sales"]:>8.2f}  cost=${d["cost"]:>7.2f}  ACoS={acos_val:.0f}%  type={d["type"]}')

    print(f"\n" + "=" * 70)
    print("REPORT FILES SAVED:")
    print(f"  reports/us_campaigns.json    - {len(campaigns)} rows")
    print(f"  reports/us_keywords.json     - {len(keywords)} rows")
    print(f"  reports/us_searchterms.json  - {len(searchterms)} rows")
    print(f"  reports/us_targeting.json    - {len(targeting)} rows")
    print("=" * 70)


if __name__ == "__main__":
    main()
