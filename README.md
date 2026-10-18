# amazon-ads

CLI tool for managing Amazon Advertising campaigns across multiple marketplaces. Built for automation and AI agent integration.

Covers the full Sponsored Products lifecycle — campaigns, ad groups, keywords, product ads, targeting, negative keywords, reporting, bid optimization, cross-region sync, product onboarding, and AI-powered keyword generation.

## Quick Start

```bash
# Install
pip install -e .

# (Optional) Install AI keyword generation support
pip install -e ".[ai]"

# Configure credentials
cp .env.example .env
# Edit .env with your Amazon Ads OAuth credentials

# Verify setup
amazon-ads auth login --region US
amazon-ads profiles list
```

## Configuration

### Credentials (`.env`)

```
AMAZON_ADS_CLIENT_ID=amzn1.application-oa2-client.xxxxx
AMAZON_ADS_CLIENT_SECRET=xxxxx
AMAZON_ADS_REFRESH_TOKEN=Atzr|xxxxx
AMAZON_ADS_REFRESH_TOKEN_EU=Atzr|xxxxx
```

### Region Profiles (`config/profiles.yaml`)

Pre-configured for 8 marketplaces across 3 auth regions:

| Region | Marketplace | Auth Region | API Endpoint |
|--------|------------|-------------|--------------|
| US     | United States | NA | `advertising-api.amazon.com` |
| CA     | Canada | NA | `advertising-api.amazon.com` |
| GB     | United Kingdom | EU | `advertising-api-eu.amazon.com` |
| DE     | Germany | EU | `advertising-api-eu.amazon.com` |
| FR     | France | EU | `advertising-api-eu.amazon.com` |
| ES     | Spain | EU | `advertising-api-eu.amazon.com` |
| IT     | Italy | EU | `advertising-api-eu.amazon.com` |
| AU     | Australia | FE | `advertising-api-fe.amazon.com` |

## Commands

```
amazon-ads [--verbose] <command> <subcommand> [options]
```

Every mutating command supports `--dry-run`. All commands support `--output table|json|csv`.

### Auth

```bash
amazon-ads auth login --region US          # Get fresh access token
amazon-ads auth status                     # Check token expiry
amazon-ads auth refresh --region US        # Force token refresh
```

### Profiles & Accounts

```bash
amazon-ads profiles list --region US
amazon-ads profiles accounts --region US
```

### Campaigns

```bash
amazon-ads campaigns list --region US --state ENABLED
amazon-ads campaigns create --region US --name "My Campaign" --targeting-type MANUAL --budget 50
amazon-ads campaigns update --region US --campaign-id 123 --state PAUSED
amazon-ads campaigns delete --region US --campaign-id 123 --dry-run
```

### Ad Groups

```bash
amazon-ads ad-groups list --region US --campaign-id 123
amazon-ads ad-groups create --region US --campaign-id 123 --name "My Ad Group" --default-bid 0.45
amazon-ads ad-groups update --region US --ad-group-id 456 --default-bid 0.60
amazon-ads ad-groups delete --region US --ad-group-id 456
```

### Keywords

```bash
# List & filter
amazon-ads keywords list --region US --campaign-id 123 --state ENABLED

# Single keyword
amazon-ads keywords create --region US -c 123 -a 456 --keyword-text "my keyword" --match-type EXACT --bid 0.30

# Bulk from file
amazon-ads keywords create --region US --from-file keywords.json

# Bulk from stdin (pipeable)
cat keywords.json | amazon-ads keywords create --region US --from-stdin

# Update & delete
amazon-ads keywords update --region US --keyword-id 789 --bid 0.50 --state PAUSED
amazon-ads keywords delete --region US --keyword-id 789
```

### AI Keyword Generation

Generate keywords using Claude or GPT, then pipe directly into creation:

```bash
# Generate with Anthropic (default)
amazon-ads keywords generate --title "My Book" --region US

# Generate with OpenAI
amazon-ads keywords generate --title "My Book" --provider openai --model gpt-4o

# Generate in local language for a region
amazon-ads keywords generate --title "My Book" --region DE

# Custom model
amazon-ads keywords generate --title "My Book" --provider anthropic --model claude-sonnet-4-20250514

# Full pipeline: generate -> create
amazon-ads keywords generate --title "My Book" -c CAMP123 -a AG456 --bid 0.30 \
  | amazon-ads keywords create --from-stdin --region US

# Preview prompt without calling the LLM
amazon-ads keywords generate --title "My Book" --region DE --dry-run

# Custom prompt
amazon-ads keywords generate --title "My Book" --prompt-file my-prompt.txt
```

API keys resolve from `--api-key` flag or environment variables (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`).

### Negative Keywords

```bash
# Ad group level
amazon-ads negatives list --region US --ad-group-id 456
amazon-ads negatives create --region US -c 123 -a 456 --keyword-text "bad keyword" --match-type NEGATIVE_EXACT
amazon-ads negatives delete --region US --keyword-id 789

# Campaign level
amazon-ads negatives list-campaign --region US --campaign-id 123
amazon-ads negatives create-campaign --region US --campaign-id 123 --keyword-text "bad keyword"
amazon-ads negatives delete-campaign --region US --keyword-id 789
```

### Product Targeting

```bash
# Positive targets (ASIN or category)
amazon-ads targets list --region US --campaign-id 123
amazon-ads targets create --region US -c 123 -a 456 --asin B0ABC123 --bid 0.50
amazon-ads targets update --region US --target-id 789 --bid 0.60
amazon-ads targets delete --region US --target-id 789

# Negative targets
amazon-ads targets list-negative --region US --campaign-id 123
amazon-ads targets create-negative --region US -c 123 -a 456 --asin B0BAD999
amazon-ads targets delete-negative --region US --target-id 789
```

### Product Ads

```bash
amazon-ads product-ads list --region US --campaign-id 123
amazon-ads product-ads create --region US -c 123 -a 456 --asin B0ABC123
```

### Bids

```bash
# Backup current enabled keyword bids (writes {REGION}-{YYYY-MM-DD}.json and .csv to ./backups, or --dir)
amazon-ads bids backup --region ALL

# Set every enabled keyword to one bid (optionally limit with --campaign-id)
amazon-ads bids update --region US --target-bid 0.50 --dry-run

# Restore from backup (one region per file)
amazon-ads bids restore --region US --file backups/US-2024-01-15.json --dry-run

# Audit auto-targeting bid overrides vs. ad group default bid (read-only)
amazon-ads bids audit --region ALL

# Reset those overrides to the ad group default bid
amazon-ads bids audit --region US --fix --dry-run
amazon-ads bids audit --region US --fix
```

Backups are named by region and date only, so running `bids backup` again on the same day overwrites that day's file for the region.

### Reports

```bash
# Create a report (async)
amazon-ads reports create --region US --report-type spCampaigns \
  --start-date 2025-01-01 --end-date 2025-01-31 --wait

# With filters
amazon-ads reports create --region US --report-type spCampaigns \
  --campaign-id 111,222,333 --start-date 2025-01-01 --end-date 2025-01-31

# Custom columns
amazon-ads reports create --region US --report-type spCampaigns \
  --columns campaignId,cost,clicks --start-date 2025-01-01 --end-date 2025-01-31

# Check report status
amazon-ads reports status --region US --report-id abc123

# Wait for an existing report, then print its rows
amazon-ads reports status --region US --report-id abc123 --wait

# Tune waiting (defaults: --poll-interval 30, --max-wait 1800 seconds)
amazon-ads reports create --region US --report-type spCampaigns \
  --start-date 2025-01-01 --end-date 2025-01-31 --wait --poll-interval 60 --max-wait 3600

# Performance summary with ACoS
amazon-ads reports summary --region ALL --timeframe monthly
```

`--wait` (on `create` and `status`) and `reports summary` poll until the report is `COMPLETED`. They exit non-zero if the report ends in `FAILURE`/`CANCELLED` or is still not ready after `--max-wait` seconds; `summary` applies `--max-wait` to each region's report, and with `--region ALL` one failed or timed-out region stops the command without printing the regions already summarized. A timeout does not cancel the Amazon report — `create` prints the report ID to stderr, so you can check it later with `reports status`.

Report types: `spCampaigns`, `spKeywords`, `spSearchTerm`, `spTargeting`, `spAdvertisedProduct`

**API limits:** Max 31-day date range per report. Data retention is ~3 months. For longer periods, use `reports submit` with monthly chunks.

### Report Queue (Fire-and-Forget)

Submit reports asynchronously, track them in a persistent queue, and download when ready. No more waiting 5+ minutes per report.

```bash
# Submit all 4 report types for a region (returns immediately)
amazon-ads reports submit --region US \
  --start-date 2025-12-01 --end-date 2025-12-31

# Submit all types across all 8 regions (32 reports)
amazon-ads reports submit --region ALL \
  --start-date 2025-12-01 --end-date 2025-12-31

# Submit just one report type
amazon-ads reports submit --region US --report-type spKeywords \
  --start-date 2025-12-01 --end-date 2025-12-31

# View the queue
amazon-ads reports queue
amazon-ads reports queue --status DOWNLOADED --region US

# Poll all pending reports (auto-downloads completed ones)
amazon-ads reports poll
amazon-ads reports poll --region US
amazon-ads reports poll --no-download    # just update status

# Download a specific report
amazon-ads reports download --report-id abc123 --region US

# Clean up old queue entries
amazon-ads reports clean --days 7
amazon-ads reports clean --all
```

Downloaded reports are saved to `data/reports/` as JSON files, named `{region}-{type}-{startDate}-{shortId}.json`.

Queue state is persisted in `data/report_queue.json`. Status lifecycle: `SUBMITTED` -> `PROCESSING` -> `COMPLETED` -> `DOWNLOADED`. `data/` is relative to the current working directory; set `AMAZON_ADS_QUEUE_DIR` to use another location (`scripts/analyze_3mo.py` still reads `./data/reports/`).

`reports poll` only revisits entries that are still `SUBMITTED` or `PROCESSING`. A report recorded as `COMPLETED` by `poll --no-download` is not picked up by a later `poll`; fetch it with `reports download`. `reports clean` removes queue entries by submission age (default `--days 30`) regardless of status; it does not delete files in `data/reports/`.

### Optimization

```bash
# Preview overbid keywords (current bid above suggested bid + --offset, default 0.02)
amazon-ads optimize run --region US --dry-run

# Apply the reductions (without --apply, run only previews)
amazon-ads optimize run --region US --apply

# Compare current bids vs. suggested
amazon-ads optimize compare --region US --campaign-id 123
```

### Cross-Region Sync

```bash
# Export campaign structure to JSON
amazon-ads sync export --region US --save us-campaigns.json

# Replicate structure to other regions (ALL = every region except --source, default US)
amazon-ads sync replicate --source US --from-file us-campaigns.json --target ALL --dry-run

# Copy enabled keywords by exact campaign/ad group name (copies get --bid, default 0.30, not the source bids)
amazon-ads sync keywords --source US --target DE --campaign "My Campaign" --dry-run
```

`sync keywords --dry-run` only echoes the source and target regions; it does not list the keywords that would be copied.

### Product Onboarding

Create AUTO + MANUAL campaign pairs across regions in one command:

```bash
amazon-ads onboard product \
  --title "My Product" \
  --asin B0ABC123 --asin B0DEF456 \
  --region ALL \
  --budget 100 \
  --keywords-file keywords.json \
  --dry-run
```

### Schema Introspection

```bash
# Dump full CLI schema as JSON (for agent integration)
amazon-ads schema dump
```

## Analysis Scripts

The `scripts/` directory contains analysis scripts for working with downloaded report data:

| Script | Purpose |
|--------|---------|
| `scripts/analyze_reports.py` | Analyze a single period's report data (weekly/monthly) |
| `scripts/analyze_3mo.py` | Combine and analyze multi-month report data |

These scripts read from `data/reports/` and output performance breakdowns including:
- Overall metrics (cost, sales, ACoS, CPC, conversion rate)
- Monthly trends
- Campaign-level performance rankings
- AUTO vs MANUAL campaign comparison
- Targeting type breakdown (BROAD, EXACT, PHRASE, etc.)
- Money-burning campaigns (high spend, low/no sales)
- Top and worst performing keywords and search terms

### Example: 3-Month US Analysis

```bash
# 1. Submit monthly report chunks (API limit: 31 days per report)
amazon-ads reports submit --region US --start-date 2025-11-18 --end-date 2025-12-18
amazon-ads reports submit --region US --start-date 2025-12-19 --end-date 2026-01-18
amazon-ads reports submit --region US --start-date 2026-01-19 --end-date 2026-02-18

# 2. Poll until all are downloaded
amazon-ads reports poll

# 3. Run the analysis
python scripts/analyze_3mo.py
```

## Architecture

```
src/amazon_ads/
  main.py              # Typer app entry point
  config.py            # Settings + region profiles (Pydantic)
  auth.py              # OAuth2 token management
  client.py            # HTTP client with retry + response cache
  models/              # Pydantic request/response models
  services/            # Business logic (one per domain)
    reporting.py       # Report creation, polling, download
    report_queue.py    # Persistent report queue manager
  commands/            # CLI commands (one per command group)
  utils/
    output.py          # Table/JSON/CSV formatters
    pagination.py      # nextToken pagination helper
    chunking.py        # 1000-item batch splitting
    backup.py          # Bid backup/restore
    cache.py           # Region-scoped API response cache
    errors.py          # Structured error handling

scripts/               # Analysis scripts for report data
data/reports/          # Downloaded report JSON files (gitignored)
```

### Design Principles

- **stderr/stdout separation** — Human-readable messages go to stderr, structured data goes to stdout. Commands are safely pipeable.
- **Composable** — JSON output from one command can be piped as input to another via `--from-stdin`.
- **Dry-run everything** — Every mutating command supports `--dry-run` to preview changes.
- **Bulk-first** — All CRUD commands accept `--from-file` and `--from-stdin` for batch operations with automatic 1000-item chunking.
- **Multi-region** — Most commands accept `--region ALL` to operate across all 8 marketplaces.
- **Retry with backoff** — Automatic retry on 401 (token refresh), 429 (rate limit), and 5xx (server error).
- **Response caching** — GET requests are cached per-region with automatic invalidation on mutations.
- **Fire-and-forget reports** — Submit reports asynchronously, track in a persistent queue, download later.
- **Agent-friendly** — Structured JSON error output, schema introspection endpoint, consistent exit codes.

## Dependencies

| Package | Purpose |
|---------|---------|
| typer | CLI framework |
| rich | Terminal formatting |
| httpx | HTTP client |
| pydantic | Data validation |
| python-dotenv | .env loading |
| pyyaml | Config parsing |

Optional (`pip install -e ".[ai]"`):

| Package | Purpose |
|---------|---------|
| anthropic | Claude API for keyword generation |
| openai | OpenAI API for keyword generation |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (272 tests)
pytest

# Run specific test files
pytest tests/test_report_queue.py tests/test_cmd_reports.py -v

# Run with verbose logging
amazon-ads --verbose campaigns list --region US
```
