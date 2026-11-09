"""Configuration loading and validation."""

from src.common import config
from src.checks import validate_config


def test_configs_parse():
    for name in ("pipeline", "segments", "game_profile", "assemble"):
        data, path = config.load(name, required=(name != "game_profile"))
        assert isinstance(data, dict), name
        assert path


def test_configs_validate_without_issues():
    issues = []
    validate_config.check_pipeline(issues)
    by_key = validate_config.check_segments(issues)
    validate_config.check_game_profile(issues)
    validate_config.check_assemble(issues, by_key)
    assert issues == []


def test_segments_have_unique_keys():
    keys = [row[0] for row in config.videos()]
    assert keys
    assert len(keys) == len(set(keys))