"""Tests for utils/output.py — JSON/CSV/table output routing."""
import io
import json
import sys
from types import SimpleNamespace

import pytest

from amazon_ads.utils.output import OutputFormat, print_json, print_csv, print_output


# ── print_json ───────────────────────────────────────────────────────

def test_print_json_list(capsys):
    print_json([{"id": "1"}, {"id": "2"}])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2


def test_print_json_dict(capsys):
    print_json({"key": "value"})
    out = capsys.readouterr().out
    assert json.loads(out) == {"key": "value"}


def test_print_json_empty(capsys):
    print_json([])
    out = capsys.readouterr().out
    assert json.loads(out) == []


# ── print_csv ────────────────────────────────────────────────────────
# print_csv wraps sys.stdout.buffer in TextIOWrapper.  When that wrapper
# gets GC'd it closes the buffer, corrupting pytest's capture.  We swap
# sys.stdout for a custom object with a non-closeable buffer.

class _SafeBuffer(io.BytesIO):
    """BytesIO that ignores close() so TextIOWrapper can't break it."""
    def close(self):
        pass


def _capture_csv(func, *args, **kwargs):
    """Run a CSV-writing function and capture its output."""
    buf = _SafeBuffer()
    fake = SimpleNamespace(buffer=buf, write=lambda s: None, flush=lambda: None)
    old = sys.stdout
    sys.stdout = fake
    try:
        func(*args, **kwargs)
        return buf.getvalue().decode("utf-8")
    finally:
        sys.stdout = old


def test_print_csv_basic():
    out = _capture_csv(print_csv, [{"name": "a", "val": "1"}, {"name": "b", "val": "2"}])
    lines = [l.strip() for l in out.strip().splitlines()]
    assert lines[0] == "name,val"
    assert len(lines) == 3


def test_print_csv_selected_columns():
    out = _capture_csv(print_csv, [{"name": "a", "val": "1", "extra": "x"}], columns=["name", "val"])
    assert "extra" not in out


def test_print_csv_empty():
    out = _capture_csv(print_csv, [])
    assert out == ""


def test_print_csv_dict_input():
    """Single dict should be wrapped as list."""
    out = _capture_csv(print_csv, {"name": "a", "val": "1"})
    lines = out.strip().split("\n")
    assert len(lines) == 2  # header + 1 row


# ── print_output routing ────────────────────────────────────────────

def test_output_routes_to_json(capsys):
    print_output([{"x": 1}], fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    assert json.loads(out) == [{"x": 1}]
