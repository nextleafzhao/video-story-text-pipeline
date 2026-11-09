"""End-to-end smoke test using the bundled fake OCR data."""

import os
import shutil

from src.build import build_txt
from src.common import paths


def test_build_from_example_ocr():
    source = os.path.join(paths.EXAMPLES, "ocr", "01_intro.jsonl")
    target = paths.work("ocr", "01_intro.jsonl")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copyfile(source, target)

    written = build_txt.main(["01_intro"])
    assert written, "build did not produce a txt file"
    output = written[0]
    assert os.path.exists(output)
    text = open(output, encoding="utf-8").read()
    assert "【" in text
    assert "对应视频：" in text