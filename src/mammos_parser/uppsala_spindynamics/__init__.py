"""Read Uppsala atomistic spin dynamics datasets."""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import mammos_entity as me

# import mammos_units as u
from rich.logging import RichHandler

logger = logging.getLogger(__name__)


# TODO pydantic dataclass with validation?
@dataclass
class UppAsdDataset:
    """Spindynamics dataset."""

    A_0: me.Entity
    """Exchange stiffness constant at T = 0 K."""

    A_300: me.Entity
    """Exchange stiffness constant at T = 300 K."""

    K_300: me.Entity
    """TODO at T = 300 K."""

    Js_0: me.Entity
    """TODO constant at T = 0 K."""

    Js_300: me.Entity
    """TODO at T = 300 K."""


def check_structure(dataset_path: str | Path) -> bool:
    """Check if dataset has the required structure and files.

    Raises:
       ...Error: directory xyz missing.
       ...Error: file abc missing, etc.
    """
    logger.warning("No checks for structure are performed!!!")
    return True


def read_dataset(dataset_path: str | Path) -> UppAsdDataset:
    """Read dataset from disk.

    Raises:
        ...Error: Any of the required data is missing or in wrong format.
    """
    logger.warning("No data is read!!!")
    return UppAsdDataset(...)


def validate_dataset() -> None:
    """Command line entrypoint to validate dataset."""
    logging.basicConfig(level="NOTSET", format="%(message)s", handlers=[RichHandler()])
    dataset_path = Path(sys.argv[1])  # TODO: use argparse
    logger.info("Checking dataset '%s'", dataset_path)
    if not dataset_path.exists():
        logger.critical("Directory '%s' does not exist.", dataset_path)
        sys.exit(1)
    if not check_structure(dataset_path):
        sys.exit(1)
    try:
        read_dataset(dataset_path)
    except Exception:  # TODO: be more specific!!!
        sys.exit(1)
