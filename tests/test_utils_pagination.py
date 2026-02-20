"""Tests for utils/pagination.py — uses a callable mock for fetch_fn."""
from amazon_ads.utils.pagination import paginate


def test_single_page():
    def fetch(body):
        return {"items": [{"id": 1}, {"id": 2}]}

    assert paginate(fetch, {}, "items") == [{"id": 1}, {"id": 2}]


def test_multiple_pages():
    call_count = 0

    def fetch(body):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"items": [{"id": 1}], "nextToken": "page2"}
        return {"items": [{"id": 2}]}

    assert paginate(fetch, {}, "items") == [{"id": 1}, {"id": 2}]


def test_three_pages():
    pages = [
        {"items": [{"id": 1}], "nextToken": "t2"},
        {"items": [{"id": 2}], "nextToken": "t3"},
        {"items": [{"id": 3}]},
    ]
    page_iter = iter(pages)
    assert len(paginate(lambda b: next(page_iter), {}, "items")) == 3


def test_empty_results():
    assert paginate(lambda b: {"items": []}, {}, "items") == []


def test_missing_results_key():
    assert paginate(lambda b: {"other": "data"}, {}, "items") == []


def test_sets_next_token_in_body():
    body = {"maxResults": 100}
    calls = []

    def fetch(b):
        calls.append(dict(b))
        if len(calls) == 1:
            return {"items": [1], "nextToken": "tok"}
        return {"items": [2]}

    paginate(fetch, body, "items")
    assert calls[1]["nextToken"] == "tok"
