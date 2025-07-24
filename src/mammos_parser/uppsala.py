"""Read dataset from Uppsala.

The required structure and files are defined in
https://github.com/MaMMoS-project/uppsala-data/blob/data-structure/README.md.
"""

from logging import getLogger
from pathlib import Path

from . import util

logger = getLogger(__name__)


def collect_uppasd_data(base_path: Path) -> util.Collected:
    """Check structure of uppasd dataset."""
    data = util.check_directory(
        base_path, "uppasd", optional_files={"README.md"}, required_subdirs={"mc"}
    )
    if "uppasd/mc" in data.collected_dirs:
        data += util.check_directory(
            base_path,
            "uppasd/mc",
            required_files={"jfile", "momfile", "posfile", "inpsd.dat", "M(T)"},
            optional_files={"README.md"},
        )
    return data


def collect_rspt_data(base_path: Path) -> util.Collected:
    """Check structure of rspt dataset."""
    data = util.check_directory(
        base_path,
        "rspt",
        optional_files={"README.md"},
        required_subdirs={"common_rspt_input", "gs_x", "gs_z", "Jij"},
        optional_subdirs={"gs_y"},
    )

    if "rspt/common_rspt_input" in data.collected_dirs:
        data += util.check_directory(
            base_path,
            "rspt/common_rspt_input",
            required_files={"atomdens", "kmap", "spts", "symcof", "symt.inp"},
        )

    for dir_ in "xyz":
        if f"rspt/gs_{dir_}" in data.collected_dirs:
            data += util.check_directory(
                base_path,
                f"rspt/gs_{dir_}",
                required_files={"data", "out_last"},
                required_files_from_choices=[{"hist", "out_MF"}],
            )

    if "rspt/Jij" in data.collected_dirs:
        data += util.check_directory(
            base_path,
            "rspt/Jij",
            required_files={"data"},
            required_file_pairs=[("green.inp-", "out-")],
        )

    return data


def collect_dataset(base_path: Path) -> util.Collected:
    """Return False if any of the required files is not present."""
    logger.info("Reading uppsala dataset '%s'", base_path)

    base_path = base_path.absolute()

    if not base_path.is_dir():
        logger.critical("Base directory '%s' does not exist.", base_path)
        return util.Collected(base_path, False, set(), set())

    dataset = util.check_directory(
        base_path,
        ".",
        required_files={"intrinsic_properties.yaml", "structure.cif"},
        optional_files={"README.md"},
        required_subdirs={"rspt", "uppasd"},
    )

    if "rspt" in dataset.collected_dirs:
        dataset += collect_rspt_data(base_path)

    if "uppasd" in dataset.collected_dirs:
        dataset += collect_uppasd_data(base_path)

    if not dataset:
        logger.critical("Dataset '%s' is incomplete.", base_path)
    else:
        logger.info("Dataset '%s' contains all required files.", base_path)

    return dataset
