"""Tests for utils/chunking.py — pure function, no mocking needed."""
from amazon_ads.utils.chunking import chunk_list


def test_empty_list():
    assert chunk_list([], 10) == []


def test_smaller_than_chunk_size():
    assert chunk_list([1, 2, 3], 10) == [[1, 2, 3]]


def test_exact_chunk_size():
    assert chunk_list([1, 2, 3], 3) == [[1, 2, 3]]


def test_splits_evenly():
    assert chunk_list([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_splits_with_remainder():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_chunk_size_one():
    assert chunk_list([1, 2, 3], 1) == [[1], [2], [3]]


def test_default_chunk_size():
    items = list(range(50))
    result = chunk_list(items)
    assert len(result) == 1
    assert result[0] == items


def test_preserves_types():
    data = [{"id": i} for i in range(5)]
    result = chunk_list(data, 2)
    assert len(result) == 3
    assert result[0] == [{"id": 0}, {"id": 1}]
