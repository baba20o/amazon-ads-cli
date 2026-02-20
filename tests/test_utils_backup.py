"""Tests for utils/backup.py — file I/O with tmp_path."""
import json

import pytest

from amazon_ads.utils.backup import backup_keywords, load_backup


# ── backup_keywords ──────────────────────────────────────────────────

def test_backup_creates_files(tmp_path):
    keywords = [{"keywordId": "k1", "bid": 0.50, "keywordText": "test"}]
    result = backup_keywords(keywords, "US", backup_dir=str(tmp_path))

    assert "csv" in result
    assert "json" in result
    assert (tmp_path / result["json"].split("\\")[-1]).exists() or (tmp_path / result["json"].split("/")[-1]).exists()


def test_backup_json_content(tmp_path):
    keywords = [{"keywordId": "k1", "bid": 0.50}]
    result = backup_keywords(keywords, "US", backup_dir=str(tmp_path))

    with open(result["json"]) as f:
        data = json.load(f)
    assert data == keywords


def test_backup_csv_content(tmp_path):
    keywords = [{"keywordId": "k1", "bid": "0.50"}]
    result = backup_keywords(keywords, "US", backup_dir=str(tmp_path))

    loaded = load_backup(result["csv"])
    assert loaded[0]["keywordId"] == "k1"


def test_backup_empty_keywords(tmp_path):
    result = backup_keywords([], "US", backup_dir=str(tmp_path))
    with open(result["json"]) as f:
        assert json.load(f) == []


def test_backup_creates_directory(tmp_path):
    subdir = tmp_path / "nested" / "dir"
    backup_keywords([{"keywordId": "k1"}], "US", backup_dir=str(subdir))
    assert subdir.exists()


# ── load_backup ──────────────────────────────────────────────────────

def test_load_json(tmp_path):
    path = tmp_path / "test.json"
    data = [{"keywordId": "k1", "bid": 0.50}]
    path.write_text(json.dumps(data))

    loaded = load_backup(str(path))
    assert loaded == data


def test_load_csv(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text("keywordId,bid\nk1,0.50\nk2,0.75\n")

    loaded = load_backup(str(path))
    assert len(loaded) == 2
    assert loaded[0]["keywordId"] == "k1"


def test_load_missing_file():
    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        load_backup("/nonexistent/path.json")


def test_load_unsupported_extension(tmp_path):
    path = tmp_path / "data.xml"
    path.write_text("<data/>")

    with pytest.raises(ValueError, match="Unsupported file type"):
        load_backup(str(path))
