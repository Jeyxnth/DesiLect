import pytest

from app.cache import store


@pytest.fixture(autouse=True)
def private_lesson_cache(tmp_path, monkeypatch):
    """Each test gets an empty reuse-cache index (step 12: real lessons made by the drills and the benchmark for
    "Photosynthesis" etc. were answering the API tests' requests from outputs/cache/lessons)."""
    monkeypatch.setattr(store, "_lesson_index", lambda key: tmp_path / "lesson-cache" / f"{key}.json")
