from pathlib import Path

import pytest

from mammos_parser.uppsala._validate import (
    _validate_csv_file,
    _validate_mc_order,
    load_schema,
    validate_filesystem_structure,
)


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
        "metadata.yaml": "FILE",
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
                "thermal.yaml": "FILE",
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


def test_csv_column_order_mismatch_reports_error(tmp_path):
    (tmp_path / "thermal.dat").write_text("b a\n1 2\n")

    file_ok, errors = _validate_csv_file(
        tmp_path,
        "thermal.dat",
        {
            "sep": r"\s+",
            "columns": ["a", "b"],
        },
    )
    assert not file_ok
    assert len(errors) == 1
    assert "columns are in the wrong order" in errors[0].message
    assert "expected ['a', 'b']" in errors[0].message


def test_mc_order_correct(tmp_path):
    for i, cell in [
        (1, "30 30 30"),
        (2, "20 20 20 comments are ignored"),
    ]:
        (tmp_path / f"MC_{i}").mkdir()
        (tmp_path / f"MC_{i}" / "inpsd.dat").write_text(f"ncell {cell}")

    dir_ok, errors = _validate_mc_order(tmp_path, ".", {})
    assert dir_ok
    assert errors == []


def test_mc_order_missing_ncell(tmp_path):
    (tmp_path / "MC_1").mkdir()
    (tmp_path / "MC_1" / "inpsd.dat").touch()

    dir_ok, errors = _validate_mc_order(tmp_path, ".", {})
    assert not dir_ok
    assert errors[0].file_path == Path("MC_1") / "inpsd.dat"
    assert "File does not contain a line 'ncell" in errors[0].message


def test_mc_order_wrong_ncell_format(tmp_path):
    for i, cell in [
        (1, "30 30 30"),
        (2, "20 20"),
    ]:
        (tmp_path / f"MC_{i}").mkdir()
        (tmp_path / f"MC_{i}" / "inpsd.dat").write_text(f"ncell {cell}")

    dir_ok, errors = _validate_mc_order(tmp_path, ".", {})
    assert not dir_ok
    assert errors[0].file_path == Path("MC_2") / "inpsd.dat"
    assert "File does not contain a line 'ncell" in errors[0].message


def test_mc_order_wrong(tmp_path):
    for i, cell in [
        (1, "20 20 20"),
        (2, "30 30 30"),
        (3, "10 10 10"),
    ]:
        (tmp_path / f"MC_{i}").mkdir()
        (tmp_path / f"MC_{i}" / "inpsd.dat").write_text(f"ncell {cell}")

    dir_ok, errors = _validate_mc_order(tmp_path, ".", {})
    assert not dir_ok
    assert "MC_2, MC_1, MC_3" in errors[0].message
