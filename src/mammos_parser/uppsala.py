"""Read dataset from Uppsala.

The required structure and files are defined in
https://github.com/MaMMoS-project/uppsala-data/blob/data-structure/README.md.
"""

from logging import getLogger
from pathlib import Path

import mammos_entity as me
import ontopy

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


def check_intrinsic_properties(filename: Path) -> bool:
    """Check that intrinsic_properties.yaml contains the required entities."""
    logger.info("Checking content of 'intrinsic_properties.yaml'.")
    try:
        data = me.io.entities_from_file(filename)
    except RuntimeError as e:
        logger.error("Validation of intrinsic_properties.yaml failed: %s", e)
        return False
    except ontopy.utils.NoSuchLabelError as e:
        logger.error(
            "Validation of intrinsic_properties.yaml failed:"
            " entity not found in the ontology: %s",
            e,
        )
        return False

    file_ok = True
    for name, label in [
        ("Js", "SpontaneousMagneticPolarisation"),
        ("MAE", "MagnetocrystallineAnisotropyEnergy"),
        ("Tc", "CurieTemperature"),
    ]:
        if not hasattr(data, name):
            logger.error("Did not find %s.", name)
            file_ok = False
        elif (found_label := getattr(data, name).ontology_label) != label:
            logger.error(
                "Element %s has the wrong type, expected '%s', got '%s'",
                name,
                label,
                found_label,
            )
            file_ok = False
        else:
            logger.debug("Found %s of type %s.", name, label)

    if other_entities := set(data.__dict__) - {"Js", "MAE", "Tc"}:
        logger.error("Found unexpected elements: %s", sorted(other_entities))
        file_ok = False

    return file_ok


def collect_dataset(base_path: Path) -> util.Collected:
    """Return False if any of the required files is not present."""
    base_path = base_path.resolve()

    logger.info("Reading uppsala dataset '%s'", base_path)

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

    if (
        "intrinsic_properties.yaml" in dataset.collected_files
        and not check_intrinsic_properties(base_path / "intrinsic_properties.yaml")
    ):
        dataset.tree_ok = False

    if not dataset:
        logger.critical("Dataset '%s' is incomplete.", base_path)
    else:
        logger.info("Dataset '%s' contains all required files.", base_path)

    return dataset
