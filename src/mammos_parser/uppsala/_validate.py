import collections
from logging import getLogger
from pathlib import Path

import cerberus
import yaml

logger = getLogger(__name__)

DERIVED_FILES = ["intrinsic-properties.yamlUppASD/MC/output.csv"]


def load_schema(path: Path | None = None):
    """Load schema for dataset.

    If no path is provided the bundled schema is returned.
    """
    if path is None:
        path = Path(__file__).parent / "datasen-schema.yaml"
    return yaml.load(path, Loader=yaml.SafeLoader)


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

    def _validate_pair_exists(self, constraint, field, value):
        """Check for pairs of prefix1-*, prefix2-*.

        prefix1- and prefix2- must be passed as a list of strings.

        The rule's arguments are validated against this schema:
        {"type": "list", "schema": {"type": "string"}}
        """
        key1, key2 = constraint
        if (
            field.startswith(key1)
            and (other := f"{key2}{field[len(key1) :]}") not in self.document
        ) or (
            field.startswith(key2)
            and (other := f"{key1}{field[len(key2) :]}") not in self.document
        ):
            self._error(field, f"{other} must also exist")


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
            if vals[:-1]:
                print(f"Error for '{root}/{key}':", "; ".join(vals[:-1]))
            report_errors(vals[-1], f"{root}/{key}")
        else:
            print(f"Error for '{root}/{key}':", "; ".join(vals))


def validate_dataset(base_path: Path, check_derived_files: bool = True) -> bool:
    """Validate dataset structure."""
    dataset_valid = True

    logger.info("Reading uppsala dataset '%s'", base_path)
    data_tree = tree_to_dict(base_path)
    schema = load_schema()

    if not check_derived_files:
        # remove derived files from schema
        for filepath in DERIVED_FILES:
            modified = schema
            parts = filepath.split("/")
            for part in parts[:-1]:
                modified = modified[part]
            del modified[parts[-1]]
            schema = modified

    validator = DatasetValidator(schema, require_all=True)
    if not validator.validate(data_tree):
        dataset_valid = False
        report_errors(validator.errors, base_path.name)
    else:
        logger.info("Dataset structure correct")

    if not check_derived_files:
        return dataset_valid

    # check intrinsic-properties.yaml

    # check output.csv

    return dataset_valid
