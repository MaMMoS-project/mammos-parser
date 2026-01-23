from pathlib import Path

import pytest

from mammos_parser.uppsala._validate import load_schema, validate_filesystem_structure


def make_tree(base: Path, structure: dict):
    for name, value in structure.items():
        path = base / name
        if value == "FILE":
            path.write_text("FILE")
        else:
            path.mkdir()
            make_tree(path, value)


@pytest.fixture
def valid_dataset():
    return {
        "dataset-schema.yaml": "FILE",
        "intrinsic_properties.yaml": "FILE",
        "structure.cif": "FILE",
        "RSPt": {
            "common_input": {
                "atomdens": "FILE",
                "kmap": "FILE",
                "spts": "FILE",
                "symcof": "FILE",
                "symt.inp": "FILE",
            },
            "gs_x": {
                "data": "FILE",
                "out_last": "FILE",
                "hist": "FILE",
            },
            "gs_z": {
                "data": "FILE",
                "out_last": "FILE",
                "out_MF": "FILE",
            },
            "Jij": {
                "data": "FILE",
                "out_last": "FILE",
                "green.inp-1": "FILE",
                "out-1": "FILE",
                "green.inp-1-1": "FILE",
                "out-1-1": "FILE",
            },
        },
        "UppASD": {
            "MC_1": {
                "jfile": "FILE",
                "momfile": "FILE",
                "posfile": "FILE",
                "inpsd.dat": "FILE",
                "thermal.csv": "FILE",
                "thermal.dat": "FILE",
            },
        },
    }


@pytest.fixture
def schema():
    return load_schema()["filesystem-schema"]


def test_valid_dataset_structure(tmp_path, valid_dataset, schema):
    make_tree(tmp_path, valid_dataset)
    assert validate_filesystem_structure(tmp_path, schema)


def test_missing_required_file(tmp_path, valid_dataset, schema):
    del valid_dataset["structure.cif"]

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_jij_missing_required_file(tmp_path, valid_dataset, schema):
    del valid_dataset["RSPt"]["Jij"]["data"]

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_jij_missing_inp_out(tmp_path, valid_dataset, schema):
    for name in ["green.inp-1", "out-1", "green.inp-1-1", "out-1-1"]:
        del valid_dataset["RSPt"]["Jij"][name]

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_jij_pair_violation_no_out(tmp_path, valid_dataset, schema):
    del valid_dataset["RSPt"]["Jij"]["out-1"]

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_jij_pair_violation_no_inp(tmp_path, valid_dataset, schema):
    del valid_dataset["RSPt"]["Jij"]["green.inp-1"]

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_unknown_file(tmp_path, valid_dataset, schema):
    valid_dataset["RSPt"]["Jij"]["foo"] = "FILE"

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_unknown_directory(tmp_path, valid_dataset, schema):
    valid_dataset["foo"] = {}

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)


def test_optional_gs_y(tmp_path, valid_dataset, schema):
    valid_dataset["RSPt"].pop("gs_y", None)

    make_tree(tmp_path, valid_dataset)
    assert validate_filesystem_structure(tmp_path, schema)


def test_directory_instead_of_file(tmp_path, valid_dataset, schema):
    valid_dataset["intrinsic_properties.yaml"] = {}

    make_tree(tmp_path, valid_dataset)
    assert not validate_filesystem_structure(tmp_path, schema)
