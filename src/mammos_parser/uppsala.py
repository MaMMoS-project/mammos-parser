"""Read dataset from Uppsala.

The following directory structure is expected for both ab-initio (rspt) and spindynamics (uppasd)::

  chemical_composition/
    rspt/
      common_rspt_input/
        - atomdens
        - kmap
        - spts
        - symcof
        - symt.inp
      gs_x/
        - data
        - hist OR out_MF  # output
        - out_last  # output
      gs_y/
        - ...
      gs_z/
        - ...
      Jij/
        - data
        - green.inp-*
        - out-*  # output
    uppasd/
      MC/
        - jfile
        - momfile
        - posfile
        - inpsd.dat
        - M(T)  # output
    intrinsic_properties.yaml  # postprocessed summary

"""

from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)


def check_structure_uppasd(base_path: Path) -> bool:
    """Check structure of uppasd dataset."""
    path = base_path / "uppasd"
    if not path.is_dir():
        logger.critical("Directory '%s' does not exist.", path)
        return False

    logger.info("Directory containing uppasd data exists: '%s'", path)

    return _check_all_files_present(
        path, ["jfile", "momfile", "posfile", "inpsd.dat", "M(T)"]
    )


def check_structure_rspt(base_path: Path) -> bool:
    """Check structure of rspt dataset."""
    base_path = base_path / "rspt"
    all_files_present = True
    if not base_path.is_dir():
        logger.critical("Directory '%s' does not exist.", base_path)
        return False

    logger.info("Directory containing rspt data exists: '%s'", base_path)

    path = base_path / "common_rspt_input"
    if not path.is_dir():
        logger.error(
            "Directory containing common rspt input does not exist: '%s'", path
        )
        all_files_present = False
    else:
        logger.debug("Directory containing common rspt input exists: '%s'", path)
        all_files_present = (
            _check_all_files_present(
                path, ["atomdens", "kmap", "spts", "symconf", "symt.inp"]
            )
            and all_files_present
        )

    direction_count = 0
    for direction in "xyz":
        path = base_path / f"gs_{direction}"
        if not path.is_dir():
            logger.debug(
                "Directory containing gs data for '%s' does not exist: '%s'",
                direction,
                path,
            )
            continue
        logger.debug(
            "Directory containing gs data for '%s' exists: '%s'", direction, path
        )
        direction_count += 1
        all_files_present = (
            _check_all_files_present(path, ["data"]) and all_files_present
        )
    if direction_count < 2:
        dirnames = [f"gs_{i}" for i in "xyz"]
        logger.error(
            "At least two of the directories %s must exist in '%s'.",
            dirnames,
            base_path,
        )

    path = base_path / "Jij"
    if not path.is_dir():
        logger.error("Directory containing Jij data does not exist: '%s'", path)
        all_files_present = False
    else:
        logger.debug("Directory containing Jij data exists: '%s'", path)
        all_files_present = (
            _check_all_files_present(path, ["data"]) and all_files_present
        )
        all_files_present = (
            _check_file_pairs(path, prefix_a="out-", prefix_b="green.inp-")
            and all_files_present
        )

    return all_files_present


def _check_file_pairs(path: Path, prefix_a: str, prefix_b: str) -> bool:
    """Check that files exist in pairs with prefix_a and prefix_b and common suffix."""
    all_files_exist = True

    set_a = {a.name.removeprefix(prefix_a) for a in path.glob(f"{prefix_a}*")}
    set_b = {b.name.removeprefix(prefix_b) for b in path.glob(f"{prefix_b}*")}

    for suffix in sorted(set_a & set_b):
        logger.debug(
            "File pair '%s%s', '%s%s' exists in %s",
            prefix_a,
            suffix,
            prefix_b,
            suffix,
            path,
        )
    for suffix in sorted(set_a - set_b):
        logger.error(
            "File '%s%s' exists but file '%s%s' is missing.",
            prefix_a,
            suffix,
            prefix_b,
            suffix,
        )
        all_files_exist = False

    for suffix in sorted(set_b - set_a):
        logger.eror(
            "File '%s%s' exists but file '%s%s' is missing.",
            prefix_b,
            suffix,
            prefix_a,
            suffix,
        )
        all_files_exist = False

    return all_files_exist


def _check_all_files_present(
    path: Path,
    required_files: list[str],
    required_from_selection: list[list[str]] | None = None,
) -> bool:
    """Return True if all required files exist, otherwise False.

    - All files present in `required_files` must exist.
    - For each set of files in `required_from_selection` exactly one file must exist.
    """
    all_files_present = True
    for filename in required_files:
        if not (path / filename):
            logger.error("File '%s' does not exist.", path / filename)
            all_files_present = False
        else:
            logger.debug("File '%s' exists.", path / filename)

    required_from_selection = required_from_selection or []
    for options in required_from_selection:
        option_exists = 0
        for option in options:
            if (path / option).is_file():
                logger.debug("Optional file '%s' exists.", path / option)
                option_exists = 1
            else:
                logger.debug("Optional file '%s' does not exist.", path / option)

        if option_exists == 0:
            logger.error(
                "None of the optional files %s exists in '%s'. One is required.",
                options,
                path,
            )
            all_files_present = False
        elif options_exists > 1:
            logger.error(
                "Found multiple files of %s in '%s'. Exactly one must exist.",
                options,
                path,
            )
            all_files_present = False
        else:
            logger.debug("Found exactly one file of %s in '%s'.", options, path)

    return all_files_present


def check_combined_dataset(base_path: Path) -> bool:
    """Return False if any of the required files is not present."""
    all_files_present = True
    if not base_path.is_dir():
        logger.critical("Base directory '%s' does not exist.", base_path)
        return False
    logger.info("Checking uppsala dataset in '%s'.", base_path)
    all_files_present = check_structure_rspt(base_path) and all_files_present
    all_files_present = check_structure_uppasd(base_path) and all_files_present
    all_files_present = (
        _check_all_files_present(base_path, ["intrinsic_properties.yaml"])
        and all_files_present
    )

    if not all_files_present:
        logger.critical("Dataset '%s' is incomplete.", base_path)
    else:
        logger.info("Dataset '%s' contains all required files.", base_path)
    return all_files_present
