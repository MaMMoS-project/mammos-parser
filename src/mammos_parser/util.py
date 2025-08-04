"""Utilities for checking presence of files."""

from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import Self

logger = getLogger(__name__)


@dataclass
class Collected:
    """Files and folders collected relative to root_dir.

    Only required and optional files/directories are added to the class. Unexpected
    files/directories found during file collection set required_elements_found=False.
    """

    root_dir: Path
    tree_ok: bool
    collected_files: set[str]
    collected_dirs: set[str]

    def __bool__(self):
        """Instance is true if all required files/dirs were found."""
        return self.tree_ok

    def __add__(self, other: Self):
        """Combine two Collected instances."""
        if self.root_dir != other.root_dir:
            raise ValueError("Different root directories.")
        return self.__class__(
            self.root_dir,
            self.tree_ok and other.tree_ok,
            self.collected_files | other.collected_files,
            self.collected_dirs | other.collected_dirs,
        )


def check_directory(
    root_dir: Path,
    dir_name: str | Path,
    *,
    required_files: set[str] | None = None,
    optional_files: set[str] | None = None,
    required_files_from_choices: list[set[str]] | None = None,
    required_file_pairs: list[tuple[str, str]] | None = None,
    required_subdirs: set[str] | None = None,
    optional_subdirs: set[str] | None = None,
) -> Collected:
    """Check content of directory.

    Args:
        root_dir: Path to dataset root, must be absolute.
        dir_name: Directory to be parsed, relative to `root_dir`.
        required_files: List of required files in `dir_name`.
        optional_files: List of optional files in `dir_name`.
        required_files_from_choices: Each element in the list defines a set of files
            out of which exactly one must exist.
        required_file_pairs: Each element in the list defines two prefixes for which
            files with a common suffix must exist. Example: for the element
            ``("a-", "b-")`` paires like ``a-0`` AND ``b-0`` or ``a-in.txt`` AND
            ``b-in.txt`` must exist.
        required_subdirs: List of subdirectories (only one level) that must exist in
            `dir_name`.
        optional_subdirs: List of optional sudbirectories that must exist in `dir_name`.

    Returns:
        An object that contains all found expected files and directories and indicates
        with its boolean status if any errors have occured (missing files/directories,
        additional files/directories).
    """
    required_files = required_files or set()
    optional_files = optional_files or set()
    required_files_from_choices = required_files_from_choices or []
    required_file_pairs = required_file_pairs or []
    required_subdirs = required_subdirs or set()
    optional_subdirs = optional_subdirs or set()
    dir_name = Path(dir_name)

    if not root_dir.is_absolute():
        raise ValueError(f"root_dir='{root_dir}' must be absolute.")

    logger.info("Processing directory '%s'", root_dir / dir_name)
    dir_elems = list((root_dir / dir_name).iterdir())
    found_files = set(f.name for f in dir_elems if f.is_file())
    found_dirs = set(d.name for d in dir_elems if d.is_dir())

    logger.debug("Directory contains files: %s", found_files)
    logger.debug("Directory contains subdirectories: %s", found_dirs)

    # variables for return object
    collected_valid_files = set()
    collected_valid_dirs = set()
    dir_ok = True

    # === files ===

    # required files
    req_found = required_files & found_files
    for elem in sorted(req_found):
        logger.debug("Found required file '%s'", elem)

    collected_valid_files.update(req_found)

    for elem in sorted(required_files - found_files):
        logger.error("Did not find required file '%s'", elem)
        dir_ok = False

    found_files -= required_files

    # optional files
    opt_found = optional_files & found_files
    for elem in sorted(opt_found):
        logger.debug("Found optional file '%s'", elem)

    collected_valid_files.update(opt_found)

    for elem in sorted(optional_files - found_files):
        logger.debug("Did not find optional file '%s'", elem)

    found_files -= opt_found

    # file from choices
    for choices in required_files_from_choices:
        found_choices = choices & found_files
        if not found_choices:
            logger.error("Did not find one of %s", sorted(choices))
            dir_ok = False
        elif len(found_choices) > 1:
            logger.error(
                "Found %s, only one of %s is allowed",
                sorted(found_choices),
                sorted(choices),
            )
            dir_ok = False
        else:
            logger.debug(
                "Found '%s' from choices %s", list(found_choices)[0], sorted(choices)
            )
            collected_valid_files.update(found_choices)
        found_files -= found_choices

    # file pairs
    for prefix_a, prefix_b in required_file_pairs:
        candidates_a = set(
            f.removeprefix(prefix_a) for f in found_files if f.startswith(prefix_a)
        )
        candidates_b = set(
            f.removeprefix(prefix_b) for f in found_files if f.startswith(prefix_b)
        )

        existing_pairs = candidates_a & candidates_b
        for pair in sorted(existing_pairs):
            logger.debug(
                "Found file pair '%s%s', '%s%s'", prefix_a, pair, prefix_b, pair
            )
            collected_valid_files.update({prefix_a + pair, prefix_b + pair})

        if not existing_pairs:
            dir_ok = False

        missing_b = candidates_a - candidates_b
        for elem in sorted(missing_b):
            dir_ok = False
            logger.error("Found '%s%s' but not '%s%s'", prefix_a, elem, prefix_b, elem)

        missing_a = sorted(candidates_b - candidates_a)
        for elem in missing_a:
            dir_ok = False
            logger.error("Found '%s%s' but not '%s%s'", prefix_b, elem, prefix_a, elem)

        found_files -= set(prefix_a + f for f in candidates_a)
        found_files -= set(prefix_b + f for f in candidates_b)

    # erroneous additional files
    for elem in sorted(found_files):
        logger.warning("Found unexpected file '%s'", elem)
        dir_ok = False

    # === directories ===

    # required directories
    req_dirs_found = required_subdirs & found_dirs
    for elem in sorted(req_dirs_found):
        logger.debug("Found required subdirectory '%s'", elem)

    collected_valid_dirs.update(req_dirs_found)

    for elem in sorted(required_subdirs - found_dirs):
        logger.error("Did not find required subdirectory '%s'", elem)
        dir_ok = False

    found_dirs -= req_dirs_found

    # optional directories
    opt_dirs_found = optional_subdirs & found_dirs
    for elem in sorted(opt_dirs_found):
        logger.debug("Found optional subdirectory %s", elem)

    found_dirs -= opt_dirs_found
    collected_valid_dirs.update(opt_dirs_found)

    # erroneous additional dirs
    for elem in sorted(found_dirs):
        logger.warning("Found unexpected dir '%s'", elem)
        dir_ok = False

    return Collected(
        root_dir=root_dir,
        tree_ok=dir_ok,
        collected_files=set((dir_name / f).as_posix() for f in collected_valid_files),
        collected_dirs=set((dir_name / d).as_posix() for d in collected_valid_dirs),
    )
