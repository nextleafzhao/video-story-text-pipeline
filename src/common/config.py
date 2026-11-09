"""Load and validate the four JSON configuration files.

A real ``*.json`` file wins; otherwise the matching ``*.example`` is used so a
fresh clone can run without copying files first.  Callers that need a real
file (deliverables) pass ``required=True``.
"""

import json
import os

from .paths import config_example, config_path


class ConfigError(RuntimeError):
    """Raised when a required configuration is missing or malformed."""


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON ({exc})") from exc


def load(name, required=False):
    """Return ``(data, path)`` for a config name such as ``"pipeline"``."""
    actual = config_path(name)
    if os.path.exists(actual):
        return _read(actual), actual
    example = config_example(name)
    if os.path.exists(example):
        return _read(example), example
    if required:
        raise ConfigError(
            f"{actual} is missing; copy {example} and edit it before running"
        )
    return {}, None


def pipeline():
    return load("pipeline", required=True)[0]


def segments():
    return load("segments", required=True)[0]


def game_profile():
    return load("game_profile", required=False)[0]


def assemble():
    return load("assemble", required=True)[0]


def videos():
    """Return ``(key, title, file, duration, wiki)`` tuples from segments."""
    rows = []
    for item in segments().get("videos", []):
        rows.append(
            (
                item.get("key", ""),
                item.get("title", ""),
                item.get("file", ""),
                item.get("duration", ""),
                item.get("wiki", ""),
            )
        )
    return rows


def video(key):
    for row in videos():
        if row[0] == key:
            return row
    return None