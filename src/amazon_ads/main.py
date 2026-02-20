"""Amazon Ads CLI — entry point.

Agent-friendly CLI for managing Amazon Advertising campaigns
across multiple marketplaces.
"""

from __future__ import annotations

import logging

import typer

from amazon_ads.commands.auth_cmd import app as auth_app
from amazon_ads.commands.profiles_cmd import app as profiles_app
from amazon_ads.commands.campaigns_cmd import app as campaigns_app
from amazon_ads.commands.ad_groups_cmd import app as ad_groups_app
from amazon_ads.commands.keywords_cmd import app as keywords_app
from amazon_ads.commands.product_ads_cmd import app as product_ads_app
from amazon_ads.commands.bids_cmd import app as bids_app
from amazon_ads.commands.reports_cmd import app as reports_app
from amazon_ads.commands.optimize_cmd import app as optimize_app
from amazon_ads.commands.sync_cmd import app as sync_app
from amazon_ads.commands.negatives_cmd import app as negatives_app
from amazon_ads.commands.onboard_cmd import app as onboard_app
from amazon_ads.commands.targeting_cmd import app as targeting_app
from amazon_ads.commands.schema_cmd import app as schema_app

app = typer.Typer(
    name="amazon-ads",
    help="CLI tool for managing Amazon Advertising campaigns across multiple marketplaces.",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(auth_app, name="auth")
app.add_typer(profiles_app, name="profiles")
app.add_typer(campaigns_app, name="campaigns")
app.add_typer(ad_groups_app, name="ad-groups")
app.add_typer(keywords_app, name="keywords")
app.add_typer(product_ads_app, name="product-ads")
app.add_typer(bids_app, name="bids")
app.add_typer(reports_app, name="reports")
app.add_typer(optimize_app, name="optimize")
app.add_typer(sync_app, name="sync")
app.add_typer(negatives_app, name="negatives")
app.add_typer(onboard_app, name="onboard")
app.add_typer(targeting_app, name="targets")
app.add_typer(schema_app, name="schema")


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Amazon Ads CLI — manage campaigns, keywords, bids, and reports."""
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


if __name__ == "__main__":
    app()
