"""Monthly report pull, archive, and analysis.

Pull the latest month of Amazon Ads report data, archive it locally, and
generate a comprehensive insights document from all archived data.

Usage:
    # Pull latest month for US and analyze
    python scripts/monthly_pull.py

    # Pull a specific date range
    python scripts/monthly_pull.py --start-date 2025-11-18 --end-date 2025-12-18

    # Pull for all regions
    python scripts/monthly_pull.py --region ALL

    # Re-analyze existing archive without pulling new data
    python scripts/monthly_pull.py --analyze-only

    # Seed the archive from existing data/reports/ files
    python scripts/monthly_pull.py --seed
"""
from __future__ import annotations

import argparse
import json
import glob
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARCHIVE_DIR = DATA_DIR / "archive"
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = DATA_DIR / "reports"

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]
REPORT_TYPES = ["spCampaigns", "spKeywords", "spSearchTerm", "spTargeting"]


# ═══════════════════════════════════════════════════════════════════════
#  STEP 1 — PULL
# ═══════════════════════════════════════════════════════════════════════

def compute_date_range() -> tuple[str, str]:
    """Compute the most recent complete ~30-day window."""
    today = datetime.now()
    end = today - timedelta(days=1)
    start = end - timedelta(days=30)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def month_label(start_date: str) -> str:
    """Convert a start date to a YYYY-MM label for archiving."""
    return start_date[:7]


def is_archived(region: str, start_date: str) -> bool:
    """Check if data for this region/month is already archived."""
    label = month_label(start_date)
    month_dir = ARCHIVE_DIR / region / label
    if not month_dir.exists():
        return False
    existing = {f.stem for f in month_dir.glob("*.json")}
    return all(rt in existing for rt in REPORT_TYPES)


def pull_reports(region: str, start_date: str, end_date: str) -> list[Path]:
    """Submit reports, poll until done, return downloaded file paths."""
    # Import here to avoid import errors when just analyzing
    sys.path.insert(0, str(ROOT / "src"))
    from amazon_ads.config import get_config
    from amazon_ads.auth import AuthManager
    from amazon_ads.client import AmazonAdsClient
    from amazon_ads.services.reporting import ReportingService

    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth)
    service = ReportingService(client)

    report_ids = {}
    for rtype in REPORT_TYPES:
        print(f"  Submitting {rtype} for {region} ({start_date} to {end_date})...")
        try:
            rid = service.create_report(
                region=region,
                start_date=start_date,
                end_date=end_date,
                report_type=rtype,
            )
            report_ids[rtype] = rid
            print(f"    -> {rid[:12]}...")
        except RuntimeError as e:
            print(f"    ERROR: {e}")

    if not report_ids:
        client.close()
        return []

    # Poll until all complete (max 15 minutes)
    downloaded = {}
    deadline = time.time() + 900
    print(f"\n  Polling {len(report_ids)} reports...")

    while report_ids and time.time() < deadline:
        time.sleep(30)
        for rtype, rid in list(report_ids.items()):
            try:
                status = service.get_report_status(region, rid)
                state = status.get("status", "UNKNOWN")
                if state == "COMPLETED":
                    url = status.get("url")
                    if url:
                        rows = service._download_and_decompress(url)
                        downloaded[rtype] = rows
                        print(f"    {rtype}: {len(rows)} rows downloaded")
                        del report_ids[rtype]
                elif state in ("FAILURE", "CANCELLED"):
                    print(f"    {rtype}: {state}")
                    del report_ids[rtype]
                else:
                    print(f"    {rtype}: {state}...")
            except RuntimeError as e:
                print(f"    {rtype}: error - {e}")

    client.close()

    if report_ids:
        print(f"  WARNING: {len(report_ids)} reports did not complete in time")

    # Save to archive
    label = month_label(start_date)
    month_dir = ARCHIVE_DIR / region / label
    month_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for rtype, rows in downloaded.items():
        path = month_dir / f"{rtype}.json"
        with open(path, "w") as f:
            json.dump(rows, f, indent=2, default=str)
        paths.append(path)
        print(f"    Archived: {path.relative_to(ROOT)}")

    return paths


def seed_archive():
    """Copy existing data/reports/ files into the archive structure."""
    if not REPORTS_DIR.exists():
        print("No data/reports/ directory found. Nothing to seed.")
        return

    count = 0
    for path in sorted(REPORTS_DIR.glob("*.json")):
        # Parse filename: US-spCampaigns-2025-11-18-a740509e.json
        parts = path.stem.split("-")
        if len(parts) < 5:
            continue
        region = parts[0]
        rtype = parts[1]
        # Date is parts[2]-parts[3]-parts[4]
        start_date = f"{parts[2]}-{parts[3]}-{parts[4]}"
        label = start_date[:7]

        month_dir = ARCHIVE_DIR / region / label
        month_dir.mkdir(parents=True, exist_ok=True)
        dest = month_dir / f"{rtype}.json"

        if dest.exists():
            print(f"  Skip (exists): {dest.relative_to(ROOT)}")
            continue

        shutil.copy2(path, dest)
        count += 1
        print(f"  Archived: {path.name} -> {dest.relative_to(ROOT)}")

    print(f"\nSeeded {count} files into archive.")


# ═══════════════════════════════════════════════════════════════════════
#  STEP 2 — ANALYZE
# ═══════════════════════════════════════════════════════════════════════

def load_archive(region: str) -> dict[str, list]:
    """Load all archived data for a region. Returns {report_type: [rows]}."""
    data = {rt: [] for rt in REPORT_TYPES}
    region_dir = ARCHIVE_DIR / region
    if not region_dir.exists():
        return data

    for month_dir in sorted(region_dir.iterdir()):
        if not month_dir.is_dir():
            continue
        for rt in REPORT_TYPES:
            path = month_dir / f"{rt}.json"
            if path.exists():
                with open(path) as f:
                    rows = json.load(f)
                data[rt].extend(rows)

    return data


def analyze_and_write(region: str):
    """Run full analysis on archived data and write insights markdown."""
    data = load_archive(region)
    campaigns = data["spCampaigns"]
    keywords = data["spKeywords"]
    searchterms = data["spSearchTerm"]
    targeting = data["spTargeting"]

    if not campaigns:
        print(f"  No archived data for {region}. Skipping analysis.")
        return

    # Determine date range from data
    dates = sorted(set(r.get("date", "") for r in campaigns if r.get("date")))
    first_date = dates[0] if dates else "?"
    last_date = dates[-1] if dates else "?"
    num_months = len(set(d[:7] for d in dates))

    lines = []

    def w(text=""):
        lines.append(text)

    # ── Header ────────────────────────────────────────────────────────
    w(f"# {region} Amazon Ads — Performance Insights")
    w()
    w(f"**Period:** {first_date} to {last_date} ({num_months} months)")
    w(f"**Generated:** {datetime.now().strftime('%B %d, %Y')}")
    w(f"**Data:** {len(campaigns):,} campaign rows, {len(keywords):,} keyword rows, "
      f"{len(searchterms):,} search term rows, {len(targeting):,} targeting rows")
    w()
    w("---")
    w()

    # ── Overall metrics ───────────────────────────────────────────────
    total_cost = sum(float(r.get("cost", 0)) for r in campaigns)
    total_sales = sum(float(r.get("sales1d", 0)) for r in campaigns)
    total_clicks = sum(int(r.get("clicks", 0)) for r in campaigns)
    total_impr = sum(int(r.get("impressions", 0)) for r in campaigns)
    total_purch = sum(int(r.get("purchases1d", 0)) for r in campaigns)
    acos = (total_cost / total_sales * 100) if total_sales else 0
    roas = total_sales / total_cost if total_cost else 0
    cpc = total_cost / total_clicks if total_clicks else 0
    conv = total_purch / total_clicks * 100 if total_clicks else 0
    ctr = total_clicks / total_impr * 100 if total_impr else 0
    cpa = total_cost / total_purch if total_purch else 0
    profit = total_sales * 0.6 - total_cost

    w("## Executive Summary")
    w()
    w("| Metric | Value |")
    w("|--------|-------|")
    w(f"| Total Spend | ${total_cost:,.2f} |")
    w(f"| Total Sales | ${total_sales:,.2f} |")
    w(f"| ACoS | {acos:.1f}% |")
    w(f"| ROAS | {roas:.1f}x |")
    w(f"| Purchases | {total_purch:,} |")
    w(f"| Avg CPC | ${cpc:.2f} |")
    w(f"| Conversion Rate | {conv:.1f}% |")
    w(f"| CTR | {ctr:.2f}% |")
    w(f"| Cost per Acquisition | ${cpa:.2f} |")
    w(f"| Est. Profit (60% margin) | ${profit:,.2f} |")
    w()
    w("---")
    w()

    # ── Monthly trends ────────────────────────────────────────────────
    w("## Monthly Trends")
    w()
    monthly = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0})
    for r in campaigns:
        m = r.get("date", "")[:7]
        if not m:
            continue
        monthly[m]["cost"] += float(r.get("cost", 0))
        monthly[m]["sales"] += float(r.get("sales1d", 0))
        monthly[m]["clicks"] += int(r.get("clicks", 0))
        monthly[m]["impressions"] += int(r.get("impressions", 0))
        monthly[m]["purchases"] += int(r.get("purchases1d", 0))

    w("| Month | Cost | Sales | ACoS | Clicks | Purchases | Conv% | CPC |")
    w("|-------|------|-------|------|--------|-----------|-------|-----|")
    for m in sorted(monthly.keys()):
        d = monthly[m]
        m_acos = (d["cost"] / d["sales"] * 100) if d["sales"] else 0
        m_conv = (d["purchases"] / d["clicks"] * 100) if d["clicks"] else 0
        m_cpc = d["cost"] / d["clicks"] if d["clicks"] else 0
        w(f"| {m} | ${d['cost']:,.2f} | ${d['sales']:,.2f} | {m_acos:.0f}% | "
          f"{d['clicks']:,} | {d['purchases']} | {m_conv:.1f}% | ${m_cpc:.2f} |")
    w()
    w("---")
    w()

    # ── Campaign performance ──────────────────────────────────────────
    camp = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "impressions": 0, "purchases": 0})
    for r in campaigns:
        name = r.get("campaignName", "Unknown")
        camp[name]["cost"] += float(r.get("cost", 0))
        camp[name]["sales"] += float(r.get("sales1d", 0))
        camp[name]["clicks"] += int(r.get("clicks", 0))
        camp[name]["impressions"] += int(r.get("impressions", 0))
        camp[name]["purchases"] += int(r.get("purchases1d", 0))

    # Top campaigns
    w("## Top Performing Campaigns")
    w()
    w("| Campaign | Cost | Sales | ACoS | Est. Profit | Purch |")
    w("|----------|------|-------|------|-------------|-------|")
    top_camps = sorted(camp.items(), key=lambda x: x[1]["sales"] * 0.6 - x[1]["cost"], reverse=True)
    for name, d in top_camps[:10]:
        c_acos = (d["cost"] / d["sales"] * 100) if d["sales"] else float("inf")
        c_profit = d["sales"] * 0.6 - d["cost"]
        acos_s = f"{c_acos:.0f}%" if c_acos < 9999 else "N/A"
        w(f"| {name[:55]} | ${d['cost']:,.2f} | ${d['sales']:,.2f} | {acos_s} | ${c_profit:,.2f} | {d['purchases']} |")
    w()

    # Money losers
    w("## Money-Losing Campaigns")
    w()
    losers = [(n, d) for n, d in camp.items() if d["sales"] * 0.6 - d["cost"] < -5]
    losers.sort(key=lambda x: x[1]["sales"] * 0.6 - x[1]["cost"])
    if losers:
        w("| Campaign | Cost | Sales | ACoS | Est. Loss |")
        w("|----------|------|-------|------|-----------|")
        for name, d in losers[:10]:
            c_acos = (d["cost"] / d["sales"] * 100) if d["sales"] else float("inf")
            c_loss = d["sales"] * 0.6 - d["cost"]
            acos_s = f"{c_acos:.0f}%" if c_acos < 9999 else "No sales"
            w(f"| {name[:55]} | ${d['cost']:,.2f} | ${d['sales']:,.2f} | {acos_s} | ${c_loss:,.2f} |")
    else:
        w("No campaigns losing more than $5.")
    w()
    w("---")
    w()

    # ── AUTO vs MANUAL ────────────────────────────────────────────────
    w("## AUTO vs MANUAL Performance")
    w()
    buckets = {"AUTO": defaultdict(float), "MANUAL": defaultdict(float)}
    bucket_count = {"AUTO": 0, "MANUAL": 0}
    for name, d in camp.items():
        label = "AUTO" if "AUTO" in name.upper() else "MANUAL"
        for k in ["cost", "sales", "clicks", "impressions", "purchases"]:
            buckets[label][k] += d[k]
        bucket_count[label] += 1

    w("| Metric | AUTO | MANUAL |")
    w("|--------|------|--------|")
    for label in ["AUTO", "MANUAL"]:
        pass  # build rows below

    a, m = buckets["AUTO"], buckets["MANUAL"]
    rows_am = [
        ("Campaigns", f"{bucket_count['AUTO']}", f"{bucket_count['MANUAL']}"),
        ("Cost", f"${a['cost']:,.2f}", f"${m['cost']:,.2f}"),
        ("Sales", f"${a['sales']:,.2f}", f"${m['sales']:,.2f}"),
        ("ACoS", f"{a['cost']/a['sales']*100:.1f}%" if a["sales"] else "N/A",
         f"{m['cost']/m['sales']*100:.1f}%" if m["sales"] else "N/A"),
        ("CPC", f"${a['cost']/a['clicks']:.2f}" if a["clicks"] else "N/A",
         f"${m['cost']/m['clicks']:.2f}" if m["clicks"] else "N/A"),
        ("Conv%", f"{a['purchases']/a['clicks']*100:.1f}%" if a["clicks"] else "N/A",
         f"{m['purchases']/m['clicks']*100:.1f}%" if m["clicks"] else "N/A"),
        ("Est. Profit", f"${a['sales']*0.6-a['cost']:,.2f}", f"${m['sales']*0.6-m['cost']:,.2f}"),
    ]
    # Rewrite table properly
    lines_to_remove = 3  # remove the empty table header we wrote
    lines = lines[:-3]
    w("| Metric | AUTO | MANUAL |")
    w("|--------|------|--------|")
    for metric, av, mv in rows_am:
        w(f"| {metric} | {av} | {mv} |")
    w()
    w("---")
    w()

    # ── Targeting type ────────────────────────────────────────────────
    w("## Targeting Type Performance")
    w()
    by_type = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "purchases": 0})
    for r in targeting:
        kt = r.get("keywordType", "UNKNOWN")
        by_type[kt]["cost"] += float(r.get("cost", 0))
        by_type[kt]["sales"] += float(r.get("sales1d", 0))
        by_type[kt]["clicks"] += int(r.get("clicks", 0))
        by_type[kt]["purchases"] += int(r.get("purchases1d", 0))

    if by_type:
        w("| Type | Cost | Sales | ACoS | Conv% | Est. Profit |")
        w("|------|------|-------|------|-------|-------------|")
        for kt in sorted(by_type.keys(), key=lambda k: by_type[k]["cost"], reverse=True):
            d = by_type[kt]
            t_acos = (d["cost"] / d["sales"] * 100) if d["sales"] else float("inf")
            t_conv = (d["purchases"] / d["clicks"] * 100) if d["clicks"] else 0
            t_profit = d["sales"] * 0.6 - d["cost"]
            acos_s = f"{t_acos:.0f}%" if t_acos < 9999 else "N/A"
            w(f"| {kt} | ${d['cost']:,.2f} | ${d['sales']:,.2f} | {acos_s} | {t_conv:.1f}% | ${t_profit:,.2f} |")
    w()
    w("---")
    w()

    # ── Keywords ──────────────────────────────────────────────────────
    kw = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "purchases": 0})
    for r in keywords:
        text = r.get("keywordText", "") or r.get("keyword", "") or "Unknown"
        kw[text]["cost"] += float(r.get("cost", 0))
        kw[text]["sales"] += float(r.get("sales1d", 0))
        kw[text]["clicks"] += int(r.get("clicks", 0))
        kw[text]["purchases"] += int(r.get("purchases1d", 0))

    # Golden keywords
    w("## Golden Keywords (>5 purchases, ACoS < 40%)")
    w()
    golden = [(k, d) for k, d in kw.items()
              if d["purchases"] > 5 and d["sales"] > 0 and (d["cost"] / d["sales"] * 100) < 40]
    golden.sort(key=lambda x: x[1]["sales"], reverse=True)
    if golden:
        w("| Keyword | Sales | ACoS | Purchases | Conv% |")
        w("|---------|-------|------|-----------|-------|")
        for text, d in golden[:15]:
            k_acos = d["cost"] / d["sales"] * 100
            k_conv = d["purchases"] / d["clicks"] * 100 if d["clicks"] else 0
            w(f"| {text[:45]} | ${d['sales']:,.2f} | {k_acos:.0f}% | {d['purchases']} | {k_conv:.1f}% |")
    else:
        w("No keywords meeting criteria (>5 purchases, <40% ACoS).")
    w()

    # Worst keywords
    w("## Worst Keywords (>$5 spent, zero sales)")
    w()
    waste_kw = [(k, d) for k, d in kw.items() if d["cost"] > 5 and d["sales"] == 0]
    waste_kw.sort(key=lambda x: x[1]["cost"], reverse=True)
    waste_kw_total = sum(d["cost"] for _, d in waste_kw)
    if waste_kw:
        w(f"**{len(waste_kw)} keywords** wasting **${waste_kw_total:,.2f}**")
        w()
        w("| Keyword | Cost | Clicks |")
        w("|---------|------|--------|")
        for text, d in waste_kw[:15]:
            w(f"| {text[:45]} | ${d['cost']:,.2f} | {d['clicks']} |")
    else:
        w("No keywords with >$5 spend and zero sales.")
    w()
    w("---")
    w()

    # ── Search terms ──────────────────────────────────────────────────
    st = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "purchases": 0})
    for r in searchterms:
        term = r.get("searchTerm", "Unknown")
        st[term]["cost"] += float(r.get("cost", 0))
        st[term]["sales"] += float(r.get("sales1d", 0))
        st[term]["clicks"] += int(r.get("clicks", 0))
        st[term]["purchases"] += int(r.get("purchases1d", 0))

    # Promote to exact
    w("## Search Terms to Promote to EXACT Keywords")
    w()
    promote = [(t, d) for t, d in st.items()
               if d["purchases"] >= 3 and d["sales"] > 0 and (d["cost"] / d["sales"] * 100) < 50]
    promote.sort(key=lambda x: x[1]["sales"], reverse=True)
    if promote:
        w("| Search Term | Sales | ACoS | Purchases | Conv% |")
        w("|-------------|-------|------|-----------|-------|")
        for term, d in promote[:15]:
            s_acos = d["cost"] / d["sales"] * 100
            s_conv = d["purchases"] / d["clicks"] * 100 if d["clicks"] else 0
            w(f"| {term[:45]} | ${d['sales']:,.2f} | {s_acos:.0f}% | {d['purchases']} | {s_conv:.1f}% |")
    else:
        w("No search terms meeting criteria (3+ purchases, <50% ACoS).")
    w()

    # Negative candidates
    w("## Search Terms to Negate (>$5 spent, zero sales)")
    w()
    negatives = [(t, d) for t, d in st.items() if d["cost"] > 5 and d["sales"] == 0]
    negatives.sort(key=lambda x: x[1]["cost"], reverse=True)
    neg_total = sum(d["cost"] for _, d in negatives)
    if negatives:
        w(f"**{len(negatives)} terms** wasting **${neg_total:,.2f}**")
        w()
        w("| Search Term | Cost | Clicks |")
        w("|-------------|------|--------|")
        for term, d in negatives[:15]:
            w(f"| {term[:45]} | ${d['cost']:,.2f} | {d['clicks']} |")
    else:
        w("No search terms with >$5 spend and zero sales.")
    w()
    w("---")
    w()

    # ── Day of week ───────────────────────────────────────────────────
    w("## Day of Week Performance")
    w()
    dow = defaultdict(lambda: {"cost": 0, "sales": 0, "clicks": 0, "purchases": 0})
    for r in campaigns:
        date_str = r.get("date", "")
        if not date_str:
            continue
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
            dow[day]["cost"] += float(r.get("cost", 0))
            dow[day]["sales"] += float(r.get("sales1d", 0))
            dow[day]["clicks"] += int(r.get("clicks", 0))
            dow[day]["purchases"] += int(r.get("purchases1d", 0))
        except ValueError:
            pass

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    w("| Day | Cost | Sales | ACoS | Purchases | Conv% |")
    w("|-----|------|-------|------|-----------|-------|")
    for day in day_order:
        d = dow[day]
        if d["cost"] == 0:
            continue
        d_acos = (d["cost"] / d["sales"] * 100) if d["sales"] else 0
        d_conv = (d["purchases"] / d["clicks"] * 100) if d["clicks"] else 0
        w(f"| {day} | ${d['cost']:,.2f} | ${d['sales']:,.2f} | {d_acos:.0f}% | {d['purchases']} | {d_conv:.1f}% |")
    w()
    w("---")
    w()

    # ── Actionable recommendations ────────────────────────────────────
    w("## Actionable Recommendations")
    w()
    w("### Immediate")
    w()

    rec_num = 1
    # Money-losing campaigns
    for name, d in losers[:5]:
        c_loss = d["sales"] * 0.6 - d["cost"]
        if d["sales"] == 0:
            w(f"{rec_num}. **Pause {name[:50]}** — ${d['cost']:,.2f} spent, zero sales (save ~${abs(c_loss):,.2f}/period)")
        else:
            c_acos = d["cost"] / d["sales"] * 100
            w(f"{rec_num}. **Pause or fix {name[:50]}** — {c_acos:.0f}% ACoS, losing ~${abs(c_loss):,.2f}/period")
        rec_num += 1

    # Negative keywords
    if negatives:
        w(f"{rec_num}. **Add {min(len(negatives), 15)} negative keywords** from zero-sale search terms — save ~${neg_total:,.2f}/period")
        rec_num += 1

    # Worst keywords
    if waste_kw:
        w(f"{rec_num}. **Pause {min(len(waste_kw), 15)} zero-sale keywords** — save ~${waste_kw_total:,.2f}/period")
        rec_num += 1

    w()
    w("### Optimization")
    w()

    if golden:
        kw_names = ", ".join(t[:20] for t, _ in golden[:5])
        w(f"{rec_num}. **Increase bids on golden keywords** ({kw_names}) — proven converters with low ACoS")
        rec_num += 1

    if promote:
        st_names = ", ".join(t[:20] for t, _ in promote[:5])
        w(f"{rec_num}. **Promote top search terms to EXACT match** ({st_names}) — lock in lower CPCs on best converters")
        rec_num += 1

    auto_profit = a["sales"] * 0.6 - a["cost"]
    manual_profit = m["sales"] * 0.6 - m["cost"]
    if manual_profit > auto_profit * 1.5:
        w(f"{rec_num}. **Shift budget from AUTO to MANUAL** — MANUAL profit ${manual_profit:,.2f} vs AUTO ${auto_profit:,.2f}")
        rec_num += 1

    w()
    w("---")
    w()
    w(f"*Generated automatically by `scripts/monthly_pull.py` from {num_months} months of archived data.*")

    # Write to file
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DOCS_DIR / f"{region}-insights.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Wrote {output_path.relative_to(ROOT)}")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Monthly Amazon Ads report pull & analysis")
    parser.add_argument("--region", default="US", help="Region code or ALL (default: US)")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--analyze-only", action="store_true", help="Skip pulling, just re-analyze")
    parser.add_argument("--seed", action="store_true", help="Seed archive from existing data/reports/ files")
    args = parser.parse_args()

    regions = ALL_REGIONS if args.region.upper() == "ALL" else [args.region.upper()]

    # Seed mode
    if args.seed:
        print("Seeding archive from existing data/reports/ files...")
        seed_archive()
        print()
        for region in regions:
            print(f"Analyzing {region}...")
            analyze_and_write(region)
        return

    # Determine date range
    if args.start_date and args.end_date:
        start_date, end_date = args.start_date, args.end_date
    else:
        start_date, end_date = compute_date_range()

    # Pull
    if not args.analyze_only:
        for region in regions:
            print(f"\n{'='*60}")
            print(f"PULLING: {region} ({start_date} to {end_date})")
            print(f"{'='*60}")

            if is_archived(region, start_date):
                print(f"  Already archived for {region}/{month_label(start_date)}. Skipping pull.")
            else:
                pull_reports(region, start_date, end_date)

    # Analyze
    for region in regions:
        print(f"\n{'='*60}")
        print(f"ANALYZING: {region}")
        print(f"{'='*60}")
        analyze_and_write(region)

    print(f"\nDone! Check docs/ for insights documents.")


if __name__ == "__main__":
    main()
