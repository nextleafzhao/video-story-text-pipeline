"""Deliverable assembly helpers."""

from src.build import assemble


def test_parse_segment_txt(tmp_path):
    path = tmp_path / "01_intro_示例.txt"
    path.write_text(
        "【示例段落】\n"
        "对应视频：example_video.mp4\n"
        "时长：01:00\n"
        "====\n"
        "\n"
        "[00:01] 旅行者：你好，世界。\n"
        "[00:02] 画面文字：任务目标·前往某处\n",
        encoding="utf-8",
    )
    head, body = assemble.parse(str(path))
    assert head["title"] == "示例段落"
    assert head["video"] == "example_video.mp4"
    assert head["dur"] == "01:00"
    assert body == ["[00:01] 旅行者：你好，世界。", "[00:02] 画面文字：任务目标·前往某处"]


def test_load_finds_segment(tmp_path):
    (tmp_path / "01_intro_示例.txt").write_text("x", encoding="utf-8")
    found = assemble.load("01_intro", str(tmp_path))
    assert found is not None
    assert found.endswith("01_intro_示例.txt")