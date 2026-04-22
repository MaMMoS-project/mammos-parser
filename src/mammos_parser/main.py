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
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "--verbose", "-v", help="show verbose output", action="store_true"
    )
    verbosity_group.add_argument(
        "--quiet", "-q", help="show only warnings and errors", action="store_true"
    )

    subparsers = parser.add_subparsers(dest="dataset", required=True)

    parser_uppsala = subparsers.add_parser("uppsala-data")

    parser_uppsala.add_argument(
        "mode",
        help="operation mode",
        choices=["validate-dataset", "generate-derived-files"],
    )
    parser_uppsala.add_argument(
        "path", help="base directory containing the dataset", type=Path
    )

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

    if args.mode == "validate-dataset":
        path = args.path
        if not uppsala.validate_dataset(path):
            sys.exit(1)
    elif args.mode == "generate-derived-files":
        path = args.path
        uppsala.generate_derived_files(path)
