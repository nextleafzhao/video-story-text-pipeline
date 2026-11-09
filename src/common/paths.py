"""Single source of truth for repository paths.

Every module must use ``ROOT``/``WORK`` from here instead of relying on the
current working directory.  This is what keeps the pipeline runnable from any
directory, by humans and agents alike.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK = os.path.join(ROOT, "work")
CONFIG = os.path.join(ROOT, "config")
PROFILES = os.path.join(ROOT, "profiles")
EXAMPLES = os.path.join(ROOT, "examples")
DOCS = os.path.join(ROOT, "docs")


def work(*parts):
    """Absolute path under ``work/``."""
    return os.path.join(WORK, *parts)


def ensure_work(*parts):
    """Create and return an absolute path under ``work/``."""
    path = work(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def config_path(name):
    """Absolute path of a real config file, e.g. ``config/pipeline.json``."""
    return os.path.join(CONFIG, name + ".json")


def config_example(name):
    """Absolute path of the template, e.g. ``config/pipeline.json.example``."""
    return config_path(name) + ".example"


def profile_path(name):
    """Absolute path under ``profiles/``."""
    return os.path.join(PROFILES, name)


def rel(path):
    """Path relative to the repository root, for readable reports."""
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path