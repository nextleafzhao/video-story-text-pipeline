"""Core merge helpers."""

from src.merge import merge as m


def test_norm_strips_punctuation():
    assert m.norm("你好，世界！") == "你好世界"


def test_tidy_strips_whitespace():
    assert m.tidy("  你好  ") == "你好"


def test_parse_band_separates_name_and_body():
    boxes = [
        [10, 10, 40, 120, "旅行者", 0.98],
        [50, 10, 90, 420, "你好，世界。", 0.95],
    ]
    parsed = m.parse_band(boxes, frozenset({"旅行者"}))
    assert parsed[0] == "旅行者"
    assert "你好" in parsed[1]


def test_match_wl_exact():
    assert m.match_wl("旅行者", frozenset({"旅行者"})) == "旅行者"