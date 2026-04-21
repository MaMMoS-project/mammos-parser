import collections
import importlib
import math
import re
from logging import getLogger
from pathlib import Path

import cerberus
import mammos_entity as me
import pandas as pd
import yaml

logger = getLogger(__name__)


def load_schema() -> dict:
    """Load schema for dataset."""
    path = Path(__file__).parent / "dataset-schema.yaml"
    with path.open() as f:
        schema = yaml.safe_load(f)
    if schema["meta"]["version"] != 1:
        raise RuntimeError(
            f"Can only read schema version 1, not {schema['meta']['version']}"
        )
    return schema


def tree_to_dict(root_path: Path) -> dict:
    """Convert directory tree into dictionary.

    Recursively traverse the directory tree starting from root_path and convert it into
    a nested dictionary:
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
    - paired_prefix validator that takes a list of two strings for which elements with
          common suffix must exist; the validator returns false if elements do not
          appear in pairs or no elements are present at all.
    """

    types_mapping = cerberus.Validator.types_mapping.copy()
    types_mapping["file"] = cerberus.TypeDefinition("file", (str,), ())
    types_mapping["directory"] = cerberus.TypeDefinition(
        "directory", (collections.abc.Mapping,), ()
    )

    def _validate_paired_prefix(self, constraint, field, value) -> bool:
        """Check for pairs of prefix1-*, prefix2-*.

        prefix1- and prefix2- must be passed as a list of strings.

        The validation also returns False if no elements prefix1-* and prefix2-* exist.

        The rule's arguments are validated against this schema:
        {"type": "list", "schema": {"type": "string"}}
        """
        prefix_1, prefix_2 = constraint
        keys = set(value)

        def suffixes(prefix) -> set[str]:
            return {key[len(prefix) :] for key in keys if key.startswith(prefix)}

        suffixes_1 = suffixes(prefix_1)
        suffixes_2 = suffixes(prefix_2)

        if len(suffixes_1) == len(suffixes_2) == 0:
            self._error(field, f"missing '{prefix_1}*' and '{prefix_2}*' files")
            return False

        for suffix in (missing_2 := suffixes_1 - suffixes_2):
            self._error(field, f"missing file '{prefix_2}{suffix}'")
        for suffix in (missing_1 := suffixes_2 - suffixes_1):
            self._error(field, f"missing file '{prefix_1}{suffix}'")
        return len(missing_1) == 0 and len(missing_2) == 0


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


def report_errors(errors: dict, root: str, sep: str = "/"):
    """Print all errors in cerberus error dict."""
    for key, vals in errors.items():
        if isinstance(vals[-1], dict):
            for val in vals[:-1]:
                logger.error(f"'{root}{sep}{key}': {val}")
            report_errors(vals[-1], root=f"{root}{sep}{key}", sep=sep)
        else:
            for val in vals:
                logger.error(f"'{root}{sep}{key}': {val}")


class ContentValidationError:
    def __init__(self, base_path: Path, file_path: Path | str, message: str):
        self.base_path = base_path
        self.file_path = file_path
        self.message = message

    def __str__(self):
        path = (self.base_path / self.file_path).relative_to(self.base_path.parent)
        return f"'{path}': {self.message}"


def type_from_string(type_name: str):
    module_name, _dot, attr = type_name.rpartition(".")
    if not module_name:
        raise ValueError("Use a fully-qualified name like 'mammos_entity.Entity'")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _validate_mammos_entity_file(
    base_path: Path, filepath: Path | str, schema: dict[str, dict]
) -> tuple[bool, list[ContentValidationError]]:
    try:
        entity_collection = getattr(me, f"from_{filepath.suffix}")(base_path / filepath)
    except Exception as e:
        return False, [ContentValidationError(base_path, filepath, str(e))]

    errors = []
    seen = set()
    for name, spec in schema.items():
        seen.add(name)
        if name not in entity_collection:
            errors.append(
                ContentValidationError(base_path, filepath, f"missing element '{name}'")
            )
            continue

        entity_like = entity_collection[name]
        if not isinstance(entity_like, type_from_string(spec["type"])):
            errors.append(
                ContentValidationError(
                    base_path,
                    filepath,
                    f"element '{name}' has type "
                    f"'{type(entity_like).__module__}.{type(entity_like).__name__}', "
                    f"expected '{spec['type']}'",
                )
            )
            continue

        if (
            "ontology_label" in spec
            and getattr(entity_like, "ontology_label", None) != spec["ontology_label"]
        ):
            errors.append(
                ContentValidationError(
                    base_path,
                    filepath,
                    f"element '{name}' has label "
                    f"'{getattr(entity_like, 'ontology_label', None)}', "
                    f"expected '{spec['ontology_label']}'",
                )
            )
        if (unit := getattr(entity_like, "unit", None)) != spec["unit"]:
            errors.append(
                ContentValidationError(
                    base_path,
                    filepath,
                    f"element '{name}' has unit '{unit}', expected '{spec['unit']}'",
                )
            )

    extra = set(name for name, _ in entity_collection) - seen
    if extra:
        for elem in sorted(extra):
            errors.append(
                ContentValidationError(
                    base_path, filepath, f"unknown property: '{elem}'"
                )
            )

    return len(errors) == 0, errors


def _validate_yaml_file(
    base_path: Path, filepath: Path | str, schema: dict[str, dict]
) -> tuple[bool, list[ContentValidationError]]:
    try:
        with open(base_path / filepath) as f:
            content = yaml.safe_load(f)
    except Exception as e:
        return False, [ContentValidationError(base_path, filepath, str(e))]

    if content is None:
        return False, [ContentValidationError(base_path, filepath, "File is empty")]

    validator = cerberus.Validator(schema)
    if not validator.validate(content):
        path = (base_path / filepath).relative_to(base_path.parent)
        report_errors(validator.errors, path, sep=":")
        return False, []

    return True, []


def _validate_csv_file(
    base_path: Path, filepath: Path | str, schema: dict[str, dict]
) -> tuple[bool, list[ContentValidationError]]:
    try:
        data = pd.read_csv(base_path / filepath, sep=schema["sep"])
    except Exception as e:
        return False, [ContentValidationError(base_path, filepath, str(e))]

    if (columns := list(data.columns)) == schema["columns"]:
        return True, []

    errors = []
    if unknown := set(columns) - set(schema["columns"]):
        for elem in unknown:
            errors.append(
                ContentValidationError(base_path, filepath, f"unknown column '{elem}")
            )
    if missing := set(schema["columns"]) - set(columns):
        for elem in missing:
            errors.append(
                ContentValidationError(base_path, filepath, f"missing column '{elem}")
            )

    return False, errors


def _validate_mc_order(
    base_path: Path, filepath: Path | str, schema: dict[str, dict]
) -> tuple[bool, list[ContentValidationError]]:
    system_sizes = []
    errors = []
    for i in range(1, 4):
        if (file := base_path / filepath / f"MC_{i}" / "inpsd.dat").exists():
            size_match = re.search(r"ncell\s+(\d+\s+\d+\s+\d+\s+)", file.read_text())
            if size_match:
                # to simplify comparing grid sizes we use the total number of cells
                system_sizes.append(
                    (i, math.prod(map(int, size_match.group(1).split())))
                )
            else:
                errors.append(
                    ContentValidationError(
                        base_path,
                        Path(filepath) / f"MC_{i}/inpsd.dat",
                        "File does not contain a line 'ncell <number> <number> <number>"
                        " ...'",
                    )
                )

    if errors:
        return False, errors

    system_sizes_sorted = sorted(system_sizes, key=lambda t: t[1], reverse=True)
    if system_sizes != system_sizes_sorted:
        order = ", ".join(f"MC_{i}" for i, size in system_sizes_sorted)
        error = ContentValidationError(
            base_path,
            filepath,
            "MC directories are not ordered by system size (total number of cells) in "
            f"descending order. The order by system size is currently: {order}\n"
            "Rename the directories to bring them into the correct order.",
        )
        return False, [error]

    return True, []


def validate_filesystem_structure(base_path: Path, schema: dict) -> bool:
    if not base_path.is_dir():
        logger.error("Base directory '%s' does not exist.", base_path)
        return False

    data_tree = tree_to_dict(base_path)

    validator = DatasetValidator(
        schema,
        require_all=False,  # schema components have required:true to get better errors
    )
    error_handler = FileSystemErrorHandler(validator=validator)
    validator.error_handler = error_handler
    if not validator.validate(data_tree):
        report_errors(validator.errors, base_path.name)
        return False
    else:
        return True


def validate_file_content(base_path: Path, schema: dict) -> bool:
    dataset_valid = True
    for file_group in schema:
        validator = globals().get(f"_validate_{file_group['validator']}")
        if not validator:
            logger.critical(
                "Did not find validator for %s; required for %s",
                file_group["validator"],
                ", ".join(file_group["files"]),
            )
            dataset_valid = False
            continue

        for file in file_group["files"]:
            if not (base_path / file).exists():
                # the filesystem validation has already warned about missing files;
                # silently continue here
                continue

            file_valid, errors = validator(base_path, file, file_group["schema"])
            dataset_valid = dataset_valid and file_valid
            for error in errors:
                logger.error(str(error))

    return dataset_valid


def validate_dataset(base_path: Path) -> bool:
    """Validate dataset structure."""
    logger.info("Checking dataset '%s'", base_path)

    schema = load_schema()

    filesystem_structure_valid = validate_filesystem_structure(
        base_path, schema["filesystem-schema"]
    )
    file_content_valid = validate_file_content(base_path, schema["file-schemas"])

    if filesystem_structure_valid and file_content_valid:
        logger.info("Dataset is valid")
        return True
    else:
        return False
