import collections
import importlib
from logging import getLogger
from pathlib import Path

import cerberus
import mammos_entity as me
import yaml

logger = getLogger(__name__)

DERIVED_FILES = [
    ("intrinsic_properties.yaml",),
    ("UppASD", "schema", "MC_1", "schema", "thermal.csv"),
]


def load_schema(path: Path | None = None, index: int = 0) -> dict:
    """Load schema for dataset.

    If no path is provided the bundled schema is returned.
    """
    if path is None:
        path = Path(__file__).parent / "dataset-schema.yaml"
    with path.open() as f:
        return list(yaml.safe_load_all(f))[index]


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
    for key, vals in errors.items():
        if isinstance(vals[-1], dict):
            for val in vals[:-1]:
                logger.error(f"'{root}/{key}': {val}")
            report_errors(vals[-1], f"{root}/{key}")
        else:
            for val in vals:
                logger.error(f"'{root}/{key}': {val}")


class ContentValidationError:
    def __init__(self, path, message):
        self.path = path
        self.message = message

    def __str__(self):
        return f"'{self.path}': {self.message}"


def type_from_string(type_name: str):
    # type_name like "datetime.datetime" or "collections.abc.Mapping"
    module_name, _, attr = type_name.rpartition(".")
    if not module_name:
        raise ValueError("Use a fully-qualified name like 'datetime.datetime'")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def validate_content(filepath, schema) -> tuple[bool, list[ContentValidationError]]:
    if not filepath.is_file():
        return False, []
    try:
        obj = me.io.entities_from_file(filepath)
    except Exception as e:
        return False, [ContentValidationError(filepath, str(e))]

    errors = []
    seen = {"description"}
    for name, spec in schema.items():
        if not hasattr(obj, name):
            errors.append(
                ContentValidationError(filepath, f"missing property '{name}'")
            )
            continue

        value = getattr(obj, name)
        if not isinstance(value, type_from_string(spec["type"])):
            vt = type(value)
            errors.append(
                ContentValidationError(
                    filepath,
                    f"property '{name}' has type '{vt.__module__}.{vt.__name__}', "
                    f"expected '{spec['type']}'",
                )
            )
            continue

        if getattr(value, "ontology_label", None) != spec["ontology_label"]:
            errors.append(
                ContentValidationError(
                    filepath,
                    f"property '{name}' has label "
                    f"'{getattr(value, 'ontology_label', None)}', "
                    f"expected '{spec['ontology_label']}'",
                )
            )

        seen.add(name)

    extra = set(vars(obj)) - seen
    if extra:
        for elem in sorted(extra):
            errors.append(
                ContentValidationError(filepath, f"unknown property: '{elem}'")
            )

    return len(errors) == 0, errors


def drop_derived_files(schema):
    keys = list(schema.keys())
    for key in keys:
        if schema[key].get("meta", {}).get("preprocessed-output", False):
            schema.pop(key)
        elif "schema" in schema[key]:
            drop_derived_files(schema[key]["schema"])


def validate_dataset(base_path: Path, check_derived_files: bool = True) -> bool:
    """Validate dataset structure."""
    dataset_valid = True

    logger.info("Reading uppsala dataset '%s'", base_path)
    data_tree = tree_to_dict(base_path)
    schema = load_schema(index=1)["schema"]

    if not check_derived_files:
        drop_derived_files(schema)

    validator = DatasetValidator(
        schema,
        require_all=False,  # schema components cary required:true to get better errors
    )
    error_handler = FileSystemErrorHandler(validator=validator)
    validator.error_handler = error_handler

    # filesystem structure
    if not validator.validate(data_tree):
        dataset_valid = False
        report_errors(validator.errors, base_path.name)
    else:
        logger.info("Dataset structure correct")

    if not check_derived_files:
        return dataset_valid

    # intrinsic_properties.yaml
    file_valid, errors = validate_content(
        base_path / "intrinsic_properties.yaml", load_schema(index=2)["schema"]
    )
    dataset_valid = dataset_valid and file_valid
    for error in errors:
        logger.error(str(error))

    # UppASD/MC_*/thermal.csv
    for dir in base_path.glob("UppASD/MC_*"):
        file_valid, errors = validate_content(
            dir / "thermal.csv", load_schema(index=3)["schema"]
        )
        dataset_valid = dataset_valid and file_valid
        for error in errors:
            logger.error(str(error))

    return dataset_valid
