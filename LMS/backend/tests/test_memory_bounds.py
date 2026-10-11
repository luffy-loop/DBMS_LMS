import os
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

from material_service import _bounded_join, extract_content


def test_bounded_join_stops_consuming_generator_at_limit():
    seen = []

    def values():
        for value in ("abc", "def", "ghi"):
            seen.append(value)
            yield value

    assert _bounded_join(values(), limit=5) == "abc\nd"
    assert seen == ["abc", "def"]


def test_bounded_join_never_exceeds_limit():
    result = _bounded_join(["x" * 20, "y" * 20], limit=25)
    assert len(result) <= 25
    assert result.startswith("x" * 20)


def test_csv_extraction_is_bounded():
    from material_service import MAX_EXTRACTED_CHARS

    data = ("a,b\n" + "long,value\n" * 10000).encode()
    result, _ = extract_content(data, ".csv")
    assert len(result) <= MAX_EXTRACTED_CHARS
    assert result.startswith("a,b")


def test_vector_search_cache_limits_are_explicit():
    source = Path(__file__).parents[1].joinpath("vector_store.py").read_text(encoding="utf-8")
    assert "@lru_cache(maxsize=8)" in source
    assert "SEARCH_CACHE_MAX_ENTRIES = 64" in source
    assert "SEARCH_CACHE_MAX_QUERY_CHARS = 300" in source
    assert "if len(_cache) > SEARCH_CACHE_MAX_ENTRIES:" in source
