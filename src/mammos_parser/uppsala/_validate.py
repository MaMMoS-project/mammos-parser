import collections
import importlib
from logging import getLogger
from pathlib import Path

import cerberus
import mammos_entity as me
import yaml

logger = getLogger(__name__)


def load_schema(path: Path | None = None) -> dict:
    """Load schema for dataset.

    If no path is provided the bundled schema is returned.
    """
    if path is None:
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
            self._error(field, f"missing file '{prefix_2}{suffix}'")
        for suffix in suffixes_2 - suffixes_1:
            self._error(field, f"missing file '{prefix_1}{suffix}'")
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


def report_errors(errors: dict, root: str, sep: str = "/"):
    """Print all errors in cerberus error dict."""
    for key, vals in errors.items():
        if isinstance(vals[-1], dict):
            for val in vals[:-1]:
                logger.error(f"'{root}{sep}{key}': {val}")
            report_errors(vals[-1], f"{root}/{key}")
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
    # type_name like "datetime.datetime" or "collections.abc.Mapping"
    module_name, _, attr = type_name.rpartition(".")
    if not module_name:
        raise ValueError("Use a fully-qualified name like 'datetime.datetime'")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _validate_mammos_entity_file(
    base_path: Path, filepath: Path | str, schema: dict[str, dict]
) -> tuple[bool, list[ContentValidationError]]:
    try:
        entity_collection = me.io.entities_from_file(base_path / filepath)
    except Exception as e:
        return False, [ContentValidationError(base_path, filepath, str(e))]

    errors = []
    seen = {"description"}
    for name, spec in schema.items():
        if not hasattr(entity_collection, name):
            errors.append(
                ContentValidationError(
                    base_path, filepath, f"missing property '{name}'"
                )
            )
            continue

        entity = getattr(entity_collection, name)
        if not isinstance(entity, type_from_string(spec["type"])):
            errors.append(
                ContentValidationError(
                    base_path,
                    filepath,
                    "property '{name}' has type "
                    f"'{type(entity).__module__}.{type(entity).__name__}', "
                    f"expected '{spec['type']}'",
                )
            )
            continue

        if getattr(entity, "ontology_label", None) != spec["ontology_label"]:
            errors.append(
                ContentValidationError(
                    base_path,
                    filepath,
                    f"property '{name}' has label "
                    f"'{getattr(entity, 'ontology_label', None)}', "
                    f"expected '{spec['ontology_label']}'",
                )
            )

        seen.add(name)

    extra = set(vars(entity_collection)) - seen
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


def validate_filesystem_structure(base_path: Path, schema: dict) -> bool:
    data_tree = tree_to_dict(base_path)

    validator = DatasetValidator(
        schema,
        require_all=False,  # schema components cary required:true to get better errors
    )
    error_handler = FileSystemErrorHandler(validator=validator)
    validator.error_handler = error_handler
    if not validator.validate(data_tree):
        report_errors(validator.errors, base_path.name)
        return False
    else:
        logger.info("Dataset structure correct")
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
    logger.info("Reading uppsala dataset '%s'", base_path)

    schema = load_schema()

    filesystem_structure_valid = validate_filesystem_structure(
        base_path, schema["filesystem-schema"]
    )
    file_content_valid = validate_file_content(base_path, schema["file-schemata"])

    return filesystem_structure_valid and file_content_valid
