import collections
from logging import getLogger
from pathlib import Path

import cerberus
import mammos_entity as me
import mammos_units as u
import ontopy
import yaml

logger = getLogger(__name__)

DERIVED_FILES = [
    ("intrinsic_properties.yaml",),
    ("UppASD", "schema", "MC_1", "schema", "thermal.csv"),
]


def load_schema(path: Path | None = None):
    """Load schema for dataset.

    If no path is provided the bundled schema is returned.
    """
    if path is None:
        path = Path(__file__).parent / "dataset-schema.yaml"
    with path.open() as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def tree_to_dict(root_path: Path) -> dict:
    """Convert directory tree into dictionary.

    Recursively traverse the directory tree starting from root_path
    and convert it into a nested dictionary.
    - Directories become keys with sub-dicts.
    - Files become keys with string value FILE.
    """
    result = {}

    for item in root_path.iterdir():
        if item.is_dir():
            result[item.name] = tree_to_dict(item)
        else:
            result[item.name] = "FILE"

    return result


class DatasetValidator(cerberus.Validator):
    """Custom validator for datasets.

    Adds:
    - type alias 'file' for 'str'
    - type alias 'directory' for 'dict'
    - pair_exists validator that takes a list of two strings for which elements with
          common suffix must exist
    """

    types_mapping = cerberus.Validator.types_mapping.copy()
    types_mapping["file"] = cerberus.TypeDefinition("file", (str,), ())
    types_mapping["directory"] = cerberus.TypeDefinition(
        "directory", (collections.abc.Mapping), ()
    )

    def _validate_paired_prefix(self, constraint, field, value):
        """Check for pairs of prefix1-*, prefix2-*.

        prefix1- and prefix2- must be passed as a list of strings.

        The rule's arguments are validated against this schema:
        {"type": "list", "schema": {"type": "string"}}
        """
        prefix_1, prefix_2 = constraint
        keys = set(value)

        def suffixes(prefix):
            return {key[len(prefix) :] for key in keys if key.startswith(prefix)}

        suffixes_1 = suffixes(prefix_1)
        suffixes_2 = suffixes(prefix_2)

        for suffix in suffixes_1 - suffixes_2:
            self._error(field, f"'{prefix_2}{suffix}' missing")
        for suffix in suffixes_2 - suffixes_1:
            self._error(field, f"'{prefix_1}{suffix}' missing")
        return False


class FileSystemErrorHandler(cerberus.errors.BasicErrorHandler):
    messages = cerberus.errors.BasicErrorHandler.messages.copy()
    messages[0x02] = "missing {element_type} '{field}'"
    messages[0x03] = "unknown {element_type} '{field}'"

    def __init__(self, tree=None, validator=None):
        super().__init__(tree=tree)
        self.validator = validator

    def _schema_from_error(self, error):
        node = self.validator.schema
        for key in error.schema_path[:-1]:  # drop 'required'
            node = node[key]
        return node

    def _format_message(self, field, error):
        element_type = None

        if error.code == cerberus.errors.REQUIRED_FIELD.code:
            schema_node = self._schema_from_error(error)
            element_type = schema_node.get("type")

        elif error.code == cerberus.errors.UNKNOWN_FIELD.code:
            if isinstance(error.value, dict):
                element_type = "directory"
            elif error.value == "FILE":
                element_type = "file"

        return self.messages[error.code].format(
            *error.info,
            constraint=error.constraint,
            field=field,
            value=error.value,
            element_type=element_type,
        )


def report_errors(errors: dict, root: str):
    """Print all errors in cerberus error dict."""
    # TODO this could probably be replaced with a custom error handler
    # The format of the BasicErrorHandler is:
    # > The keys refer to the document’s ones and the values are lists containing error
    # > messages. Errors of nested fields are kept in a dictionary as last item of these
    # > lists.
    # https://docs.python-cerberus.org/errors.html#error-handlers
    for key, vals in errors.items():
        if isinstance(vals[-1], dict):
            for val in vals[:-1]:
                logger.error(f"'{root}/{key}': {val}")
            report_errors(vals[-1], f"{root}/{key}")
        else:
            for val in vals:
                logger.error(f"'{root}/{key}': {val}")


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
        ("Ms", "SpontaneousMagnetization"),
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

    if hasattr(data, "Ms") and hasattr(data, "Js"):
        with u.set_enabled_equivalencies(u.magnetic_flux_field()):
            if data.Ms.q.to(data.Js.unit) != data.Js.q:
                logger.error(
                    "Values for Ms and Js do not match:\nJs='%s'\nMs='%s' ('%s')",
                    data.Js,
                    data.Ms,
                    data.Ms.q.to(data.Js.unit),
                )
                file_ok = False

    if other_entities := set(data.__dict__) - {"Js", "Ms", "MAE", "Tc", "description"}:
        logger.error("Found unexpected elements: %s", sorted(other_entities))
        file_ok = False

    return file_ok


def check_mc_output(filename: Path) -> bool:
    """Check that intrinsic_properties.yaml contains the required entities."""
    logger.info(f"Checking content of '{filename.parent}/output.csv'")
    try:
        data = me.io.entities_from_file(filename)
    except RuntimeError as e:
        logger.error("Validation of output.csv failed: %s", e)
        return False
    except ontopy.utils.NoSuchLabelError as e:
        logger.error(
            "Validation of output.csv failed: entity not found in the ontology: %s",
            e,
        )
        return False

    file_ok = True
    for name, label in [
        ("T", "ThermodynamicTemperature"),
        ("Ms", "SpontaneousMagnetization"),
        ("Cv", "IsochoricHeatCapacity"),
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

    if other_entities := set(data.__dict__) - {"T", "Ms", "Cv"}:
        logger.error("Found unexpected elements: %s", sorted(other_entities))
        file_ok = False

    return file_ok


def validate_dataset(base_path: Path, check_derived_files: bool = True) -> bool:
    """Validate dataset structure."""
    dataset_valid = True

    logger.info("Reading uppsala dataset '%s'", base_path)
    data_tree = tree_to_dict(base_path)
    schema = load_schema()

    if not check_derived_files:
        # remove derived files from schema
        for schemapath in DERIVED_FILES:
            modified = schema
            for part in schemapath[:-1]:
                modified = modified[part]
            del modified[schemapath[-1]]

    validator = DatasetValidator(
        schema,
        require_all=False,  # schema components cary required:true to get better errors
    )
    error_handler = FileSystemErrorHandler(validator=validator)
    validator.error_handler = error_handler

    if not validator.validate(data_tree):
        dataset_valid = False
        report_errors(validator.errors, base_path.name)
    else:
        logger.info("Dataset structure correct")

    if not check_derived_files:
        return dataset_valid

    dataset_valid = (
        check_intrinsic_properties(base_path / "intrinsic_properties.yaml")
        and dataset_valid
    )

    for i in range(1, 4):
        if (base_path / f"MC_{i}").exists():
            dataset_valid = (
                check_mc_output(base_path / f"MC_{i}" / "thermal.csv") and dataset_valid
            )

    return dataset_valid
