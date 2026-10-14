from config import _load_or_create_local_secret


def test_local_secret_is_stable_across_app_restarts(tmp_path):
    first = _load_or_create_local_secret(tmp_path)
    second = _load_or_create_local_secret(tmp_path)

    assert first == second
    assert len(first) == 64
    assert (tmp_path / ".flask_secret").read_text(encoding="utf-8") == first
