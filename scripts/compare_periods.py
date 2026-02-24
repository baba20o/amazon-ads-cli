"""Compare previous archived data against the latest period."""
import json
from collections import defaultdict
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parent.parent / "data" / "archive" / "US"
REPORT_TYPES = ["spCampaigns", "spKeywords", "spSearchTerm", "spTargeting"]


def load_months(months):
    data = {}
    for rt in REPORT_TYPES:
        rows = []
        for m in months:
            p = ARCHIVE / m / f"{rt}.json"
            if p.exists():
                with open(p) as f:
                    rows.extend(json.load(f))
        data[rt] = rows
    return data


def metrics(campaigns):
    cost = sum(float(r.get("cost", 0)) for r in campaigns)
    sales = sum(float(r.get("sales1d", 0)) for r in campaigns)
    clicks = sum(int(r.get("clicks", 0)) for r in campaigns)
    purch = sum(int(r.get("purchases1d", 0)) for r in campaigns)
    impr = sum(int(r.get("impressions", 0)) for r in campaigns)
    acos = (cost / sales * 100) if sales else 0
    roas = sales / cost if cost else 0
    cpc = cost / clicks if clicks else 0
    conv = purch / clicks * 100 if clicks else 0
    cpa = cost / purch if purch else 0
    profit = sales * 0.6 - cost
    return {
        "cost": cost, "sales": sales, "clicks": clicks, "purch": purch,
        "impr": impr, "acos": acos, "roas": roas, "cpc": cpc,
        "conv": conv, "cpa": cpa, "profit": profit,
    }


def camp_daily(campaigns, days):
    camp = defaultdict(lambda: {"cost": 0, "sales": 0, "purchases": 0})
    for r in campaigns:
        name = r.get("campaignName", "Unknown")
        camp[name]["cost"] += float(r.get("cost", 0))
        camp[name]["sales"] += float(r.get("sales1d", 0))
        camp[name]["purchases"] += int(r.get("purchases1d", 0))
    for name in camp:
        for k in ["cost", "sales", "purchases"]:
            camp[name][k] /= days if days else 1
    return camp


def main():
    prev = load_months(["2025-11", "2025-12", "2026-01"])
    latest = load_months(["2026-02"])

    prev_m = metrics(prev["spCampaigns"])
    new_m = metrics(latest["spCampaigns"])

    prev_dates = len(set(r.get("date", "") for r in prev["spCampaigns"] if r.get("date")))
    new_dates = len(set(r.get("date", "") for r in latest["spCampaigns"] if r.get("date")))

    print("=" * 90)
    print("COMPARISON: Previous 3 Months vs Latest Feb 2026 Period")
    print("=" * 90)
    print(f"Previous: {prev_dates} days (Nov 2025 - Jan 2026)")
    print(f"Latest:   {new_dates} days (Feb 2026)")
    print()

    header = f"{'Metric':<25s} {'Previous (3mo)':>15s} {'Latest (Feb)':>15s} {'Prev/day':>12s} {'Latest/day':>12s} {'Change':>10s}"
    print(header)
    print("-" * 90)

    comparisons = [
        ("Cost", prev_m["cost"], new_m["cost"], "$"),
        ("Sales", prev_m["sales"], new_m["sales"], "$"),
        ("ACoS", prev_m["acos"], new_m["acos"], "%"),
        ("ROAS", prev_m["roas"], new_m["roas"], "x"),
        ("Purchases", prev_m["purch"], new_m["purch"], "#"),
        ("CPC", prev_m["cpc"], new_m["cpc"], "$"),
        ("Conv%", prev_m["conv"], new_m["conv"], "%"),
        ("CPA", prev_m["cpa"], new_m["cpa"], "$"),
        ("Profit (60%)", prev_m["profit"], new_m["profit"], "$"),
    ]

    for label, prev_v, new_v, unit in comparisons:
        prev_daily = prev_v / prev_dates if prev_dates else 0
        new_daily = new_v / new_dates if new_dates else 0

        if unit == "$":
            prev_s = f"${prev_v:,.2f}"
            new_s = f"${new_v:,.2f}"
            pd_s = f"${prev_daily:,.2f}"
            nd_s = f"${new_daily:,.2f}"
        elif unit == "%":
            prev_s = f"{prev_v:.1f}%"
            new_s = f"{new_v:.1f}%"
            pd_s = f"{prev_daily:.1f}%"
            nd_s = f"{new_daily:.1f}%"
        elif unit == "x":
            prev_s = f"{prev_v:.2f}x"
            new_s = f"{new_v:.2f}x"
            pd_s = f"{prev_daily:.2f}x"
            nd_s = f"{new_daily:.2f}x"
        else:
            prev_s = f"{prev_v:,.0f}"
            new_s = f"{new_v:,.0f}"
            pd_s = f"{prev_daily:,.1f}"
            nd_s = f"{new_daily:,.1f}"

        if prev_daily > 0:
            if unit == "%":
                change = new_v - prev_v
                change_s = f"{change:+.1f}pp"
            else:
                change = ((new_daily - prev_daily) / prev_daily) * 100
                change_s = f"{change:+.0f}%"
        else:
            change_s = "N/A"

        print(f"{label:<25s} {prev_s:>15s} {new_s:>15s} {pd_s:>12s} {nd_s:>12s} {change_s:>10s}")

    # Campaign changes
    prev_camp = camp_daily(prev["spCampaigns"], prev_dates)
    new_camp = camp_daily(latest["spCampaigns"], new_dates)
    all_names = set(prev_camp.keys()) | set(new_camp.keys())

    changes = []
    for name in all_names:
        p = prev_camp.get(name, {"cost": 0, "sales": 0, "purchases": 0})
        n = new_camp.get(name, {"cost": 0, "sales": 0, "purchases": 0})
        prev_profit = p["sales"] * 0.6 - p["cost"]
        new_profit = n["sales"] * 0.6 - n["cost"]
        delta = new_profit - prev_profit
        prev_acos = (p["cost"] / p["sales"] * 100) if p["sales"] > 0 else float("inf")
        new_acos = (n["cost"] / n["sales"] * 100) if n["sales"] > 0 else float("inf")

        if abs(delta) > 0.05 or p["cost"] > 0.1 or n["cost"] > 0.1:
            changes.append((name, p, n, delta, prev_acos, new_acos))

    print(f"\n\n{'='*90}")
    print("CAMPAIGN CHANGES: Previous Daily Avg vs Latest Daily Avg")
    print("=" * 90)

    print("\n--- BIGGEST IMPROVEMENTS (daily profit increase) ---")
    changes.sort(key=lambda x: x[3], reverse=True)
    for name, p, n, delta, pa, na in changes[:10]:
        pa_s = f"{pa:.0f}%" if pa < 9999 else "N/A"
        na_s = f"{na:.0f}%" if na < 9999 else "N/A"
        pp = p["sales"] * 0.6 - p["cost"]
        np_ = n["sales"] * 0.6 - n["cost"]
        print(f"  {name[:50]:<52s} ${pp:>+6.2f}/d -> ${np_:>+6.2f}/d  ({delta:>+.2f})  ACoS: {pa_s} -> {na_s}")

    print("\n--- BIGGEST DECLINES (daily profit decrease) ---")
    changes.sort(key=lambda x: x[3])
    for name, p, n, delta, pa, na in changes[:10]:
        pa_s = f"{pa:.0f}%" if pa < 9999 else "N/A"
        na_s = f"{na:.0f}%" if na < 9999 else "N/A"
        pp = p["sales"] * 0.6 - p["cost"]
        np_ = n["sales"] * 0.6 - n["cost"]
        print(f"  {name[:50]:<52s} ${pp:>+6.2f}/d -> ${np_:>+6.2f}/d  ({delta:>+.2f})  ACoS: {pa_s} -> {na_s}")

    # AUTO vs MANUAL trend
    print(f"\n\n{'='*90}")
    print("AUTO vs MANUAL: Previous vs Latest (daily rates)")
    print("=" * 90)

    for tag in ["AUTO", "MANUAL"]:
        if tag == "AUTO":
            p_names = [n for n in prev_camp if "AUTO" in n.upper()]
            n_names = [n for n in new_camp if "AUTO" in n.upper()]
        else:
            p_names = [n for n in prev_camp if "AUTO" not in n.upper()]
            n_names = [n for n in new_camp if "AUTO" not in n.upper()]

        p_cost = sum(prev_camp[n]["cost"] for n in p_names)
        p_sales = sum(prev_camp[n]["sales"] for n in p_names)
        n_cost = sum(new_camp[n]["cost"] for n in n_names)
        n_sales = sum(new_camp[n]["sales"] for n in n_names)

        p_acos = p_cost / p_sales * 100 if p_sales else 0
        n_acos = n_cost / n_sales * 100 if n_sales else 0
        p_profit = p_sales * 0.6 - p_cost
        n_profit = n_sales * 0.6 - n_cost

        print(f"\n  {tag}:")
        print(f"    ACoS:       {p_acos:.1f}% -> {n_acos:.1f}%  ({n_acos-p_acos:+.1f}pp)")
        print(f"    Profit/day: ${p_profit:.2f} -> ${n_profit:.2f}  (${n_profit-p_profit:+.2f})")
        print(f"    Cost/day:   ${p_cost:.2f} -> ${n_cost:.2f}")
        print(f"    Sales/day:  ${p_sales:.2f} -> ${n_sales:.2f}")


if __name__ == "__main__":
    main()
