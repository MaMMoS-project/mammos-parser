"""Command-line entrypoint for dataset validation."""

import argparse
import logging
import sys
from pathlib import Path

from rich.logging import RichHandler

from . import uppsala

logger = logging.getLogger(__name__)


def main():
    """Command-line entry point to validate datasets."""
    parser = argparse.ArgumentParser(
        prog="mammos-parser", description="Validate mammos datasets."
    )
    parser.add_argument(
        "--verbose", "-v", help="show verbose output", action="store_true"
    )
    parser.add_argument(
        "--quiet", "-q", help="show only wanings and errors", action="store_true"
    )

    parser.add_argument("mode", help="operation mode", choices=["validate-uppsala"])
    parser.add_argument("path", help="base directory containing the dataset", type=Path)

    args = parser.parse_args()

    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(show_time=False, show_path=False)],
    )

    if args.mode == "validate-uppsala":
        path = args.path
        if not uppsala.collect_dataset(path):
            sys.exit(1)
