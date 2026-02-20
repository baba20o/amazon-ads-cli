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
amazon-ads negatives create --region US -c 123 -a 456 --keyword-text "bad keyword" --match-type EXACT
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
# Backup current keyword bids
amazon-ads bids backup --region ALL

# Bulk update bids
amazon-ads bids update --region US --bid-value 0.50 --state ENABLED --dry-run

# Restore from backup
amazon-ads bids restore --region US --file backups/US_keywords_2024-01-15.json --dry-run
```

### Reports

```bash
# Create a report (async)
amazon-ads reports create --region US --report-type spCampaigns --start-date 2024-01-01 --end-date 2024-01-31 --wait

# Check report status
amazon-ads reports status --region US --report-id abc123

# Performance summary with ACoS
amazon-ads reports summary --region ALL --timeframe monthly
```

Report types: `spCampaigns`, `spKeywords`, `spSearchTerm`, `spTargeting`, `spAdvertisedProduct`

### Optimization

```bash
# Get bid recommendations and auto-reduce overbids
amazon-ads optimize run --region US --dry-run

# Compare current bids vs. suggested
amazon-ads optimize compare --region US --campaign-id 123
```

### Cross-Region Sync

```bash
# Export campaign structure to JSON
amazon-ads sync export --region US --save us-campaigns.json

# Replicate structure to other regions
amazon-ads sync replicate --from-file us-campaigns.json --region ALL --dry-run

# Sync keywords by campaign name across regions
amazon-ads sync keywords --source US --target DE --campaign-name "My Campaign" --dry-run
```

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

## Architecture

```
src/amazon_ads/
  main.py              # Typer app entry point
  config.py            # Settings + region profiles (Pydantic)
  auth.py              # OAuth2 token management
  client.py            # HTTP client with retry (401/429/5xx)
  models/              # Pydantic request/response models
  services/            # Business logic (one per domain)
  commands/            # CLI commands (one per command group)
  utils/
    output.py          # Table/JSON/CSV formatters
    pagination.py      # nextToken pagination helper
    chunking.py        # 1000-item batch splitting
    backup.py          # Bid backup/restore
    errors.py          # Structured error handling
```

### Design Principles

- **stderr/stdout separation** — Human-readable messages go to stderr, structured data goes to stdout. Commands are safely pipeable.
- **Composable** — JSON output from one command can be piped as input to another via `--from-stdin`.
- **Dry-run everything** — Every mutating command supports `--dry-run` to preview changes.
- **Bulk-first** — All CRUD commands accept `--from-file` and `--from-stdin` for batch operations with automatic 1000-item chunking.
- **Multi-region** — Most commands accept `--region ALL` to operate across all 8 marketplaces.
- **Retry with backoff** — Automatic retry on 401 (token refresh), 429 (rate limit), and 5xx (server error).
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

# Run tests
pytest

# Run with verbose logging
amazon-ads --verbose campaigns list --region US
```
