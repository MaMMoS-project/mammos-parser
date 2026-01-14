from pathlib import Path

import pytest

from mammos_parser.uppsala import validate_dataset


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
        # "intrinsic_properties.yaml": "FILE",  # if preset its contet would be checked
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
                # "thermal.csv": "FILE",  # if preset its content would be checked
                "thermal.dat": "FILE",
            },
        },
    }


def test_valid_dataset_structure(tmp_path, valid_dataset):
    make_tree(tmp_path, valid_dataset)
    assert validate_dataset(tmp_path, check_derived_files=False) is True


def test_missing_required_file(tmp_path, valid_dataset):
    data = valid_dataset
    del data["structure.cif"]

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False


def test_jij_missing_required_file(tmp_path, valid_dataset):
    data = valid_dataset
    del data["RSPt"]["Jij"]["data"]

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False


def test_jij_pair_violation_no_out(tmp_path, valid_dataset):
    data = valid_dataset
    del data["RSPt"]["Jij"]["out-1"]

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False


def test_jij_pair_violation_no_inp(tmp_path, valid_dataset):
    data = valid_dataset
    del data["RSPt"]["Jij"]["green.inp-1"]

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False


def test_unknown_file(tmp_path, valid_dataset):
    data = valid_dataset
    data["RSPt"]["Jij"]["foo"] = "FILE"

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False


def test_unknown_directory(tmp_path, valid_dataset):
    data = valid_dataset
    data["foo"] = {}

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False


def test_optional_gs_y(tmp_path, valid_dataset):
    data = valid_dataset
    data["RSPt"].pop("gs_y", None)

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is True


def test_directory_instead_of_file(tmp_path, valid_dataset):
    data = valid_dataset
    data["intrinsic_properties.yaml"] = {}

    make_tree(tmp_path, data)
    assert validate_dataset(tmp_path, check_derived_files=False) is False
