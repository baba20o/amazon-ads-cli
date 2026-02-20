"""AI keyword generation using Anthropic or OpenAI Python SDKs.

Requires the optional `ai` dependency group:
    pip install -e ".[ai]"

Supports any model from either provider — just pass --provider, --model, and --api-key.
"""

from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_DEFAULT_PROMPT = """\
I'm looking for unique, specific and aligned keywords related to the title \
for my book '{title}' for Amazon advertising.

These keywords should be in the local language for the country {region}.

These keywords are characterized by their specificity and clear alignment with \
searcher intent. They tend to drive more qualified traffic, resulting in better \
engagement and conversion rates due to their direct relevance to the searcher's needs.

The keywords should encompass both single-word and multi-word phrases, directly \
related to the main theme of the book and its wider context. Begin with the most \
impactful single-word keywords, then proceed to multi-word phrases, ensuring \
there's a clear distinction and relevance.

For multi-word keywords, it's imperative to separate each word with a single space. \
Avoid merging words together. For instance, 'ArtificialIntelligence' must be \
correctly presented as 'Artificial Intelligence'. This rule applies uniformly \
across all multi-word keywords to ensure clarity and search optimization.

Ensure the long-chain keywords are related to the main topic of the book title \
or similar.

Here's an example to guide you:
- Correct: 'Creative Writing', 'Story Telling'
- Incorrect: 'CreativeWriting', 'StoryTelling'

All keywords must be distinct, relevant, and optimized for search purposes.

ALL keywords should be lowercase.

Please generate an extensive list of keywords following these guidelines. \
Emphasize the separation of words in multi-word phrases to align with search \
optimization practices.

Return them in JSON format ONLY with the key 'keywords', no context or \
commentary just the JSON only.
"""

# ---------------------------------------------------------------------------
# Provider implementations (official SDKs, lazy-imported)
# ---------------------------------------------------------------------------

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
}


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    """Call Anthropic via the official ``anthropic`` SDK."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "The 'anthropic' package is required for this provider. "
            "Install it with: pip install -e \".[ai]\" or pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_openai(prompt: str, api_key: str, model: str) -> str:
    """Call OpenAI via the official ``openai`` SDK."""
    try:
        import openai
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for this provider. "
            "Install it with: pip install -e \".[ai]\" or pip install openai"
        )

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_json(text: str) -> Any:
    """Extract JSON from LLM response text.

    Handles both raw JSON and markdown-fenced code blocks.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Last resort: find first { ... } or [ ... ]
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Could not extract JSON from LLM response:\n{text[:500]}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}

MATCH_TYPES = ("BROAD", "PHRASE", "EXACT")


def generate_keywords(
    *,
    title: str,
    region: str = "US",
    provider: str = "anthropic",
    api_key: str,
    model: str | None = None,
    custom_prompt: str | None = None,
    expand_match_types: bool = True,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    bid: float | None = None,
) -> list[dict[str, Any]]:
    """Generate keywords via an LLM and return structured JSON.

    Parameters
    ----------
    title : str
        Product / book title for keyword ideation.
    region : str
        Target marketplace region (used for language localisation).
    provider : str
        LLM provider — ``"anthropic"`` or ``"openai"``.
    api_key : str
        Provider API key.
    model : str | None
        Model name. Falls back to a sensible default per provider.
    custom_prompt : str | None
        Override the built-in prompt entirely. Must instruct the model
        to return ``{"keywords": ["..."]}`` JSON.
    expand_match_types : bool
        If True, each keyword is tripled into BROAD / PHRASE / EXACT entries.
    campaign_id, ad_group_id : str | None
        If provided, attached to each keyword record so the output can be
        piped directly into ``keywords create --from-stdin``.
    bid : float | None
        Keyword bid to attach to each record.

    Returns
    -------
    list[dict]
        Keyword records ready for JSON serialisation.
    """
    provider = provider.lower()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Choose: {', '.join(_PROVIDERS)}")

    model = model or _DEFAULT_MODELS[provider]
    prompt = custom_prompt or _DEFAULT_PROMPT.format(title=title, region=region)

    call_fn = _PROVIDERS[provider]
    raw_text = call_fn(prompt, api_key, model)

    parsed = _extract_json(raw_text)
    # Accept {"keywords": [...]} or a bare list
    if isinstance(parsed, dict):
        keywords: list[str] = parsed.get("keywords", [])
    elif isinstance(parsed, list):
        keywords = parsed
    else:
        raise ValueError(f"Unexpected JSON shape: {type(parsed)}")

    # Build output records
    results: list[dict[str, Any]] = []
    match_types = list(MATCH_TYPES) if expand_match_types else ["BROAD"]

    for kw in keywords:
        kw_text = str(kw).strip()
        if not kw_text:
            continue
        for mt in match_types:
            record: dict[str, Any] = {
                "keywordText": kw_text,
                "matchType": mt,
                "state": "ENABLED",
            }
            if campaign_id:
                record["campaignId"] = campaign_id
            if ad_group_id:
                record["adGroupId"] = ad_group_id
            if bid is not None:
                record["bid"] = bid
            results.append(record)

    return results
