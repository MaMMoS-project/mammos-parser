"""Utilities for checking presence of files."""

import re
from pathlib import Path


def find_in_file(filename: str | Path, expression) -> str:
    """Find subexpression in file, returns the first capture group."""
    matches = re.findall(expression, Path(filename).read_text())
    if not matches:
        raise RuntimeError(f"Could not find {expression} in {filename}.")
    return matches[-1]
