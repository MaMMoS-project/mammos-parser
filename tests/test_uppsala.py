from pathlib import Path

import mammos_entity as me

from mammos_parser import uppsala


def make_file(file_path: Path):
    file_path.parent.mkdir(exist_ok=True, parents=True)
    file_path.touch()


def test_all_files_present(tmp_path: Path):
    # Check various different conditions under which the dataset tmp_path is valid or
    # invalid. To reduce overhead of the setup additional files are added/removed as
    # needed. The order is therefor important.
    make_file(tmp_path / "intrinsic_properties.yaml")
    make_file(tmp_path / "structure.cif")

    # incomplete
    assert not uppsala.collect_dataset(tmp_path)

    for name in ["atomdens", "kmap", "spts", "symcof", "symt.inp"]:
        make_file(tmp_path / "RSPt" / "common_input" / name)

    for dir_name in ["gs_x", "gs_z"]:
        for name in ["data", "hist", "out_last"]:
            make_file(tmp_path / "RSPt" / dir_name / name)

    for name in ["green.inp-1", "out-1", "data"]:
        make_file(tmp_path / "RSPt" / "Jij" / name)

    for name in ["jfile", "momfile", "posfile", "inpsd.dat", "output.csv"]:
        make_file(tmp_path / "UppASD" / "MC" / name)

    # all required files, first calculation mode

    # content of intrinsic_properties.yaml missing
    assert not uppsala.collect_dataset(tmp_path)

    # add required entries to intrinsic_properties.yaml
    me.io.entities_to_file(
        tmp_path / "intrinsic_properties.yaml",
        Js=me.Js(2, "T"),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
        Tc=me.Tc(1000, "K"),
    )
    me.io.entities_to_file(
        tmp_path / "UppASD/MC/output.csv",
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m"),
        Cv=me.Entity("IsochoricHeatCapacity", [1.3e-24, 1.4e-24, 1.5e-24], "J/K"),
    )
    assert uppsala.collect_dataset(tmp_path)

    # second calculation mode in addition: not allowed
    for dir_name in ["gs_x", "gs_z"]:
        make_file(tmp_path / "RSPt" / dir_name / "out_MF")

    assert not uppsala.collect_dataset(tmp_path)

    # remove first calculation mode
    for dir_name in ["gs_x", "gs_z"]:
        (tmp_path / "RSPt" / dir_name / "hist").unlink()

    assert uppsala.collect_dataset(tmp_path)

    # optional third directory
    for name in ["data", "out_MF", "out_last"]:
        make_file(tmp_path / "RSPt" / "gs_y" / name)

    assert uppsala.collect_dataset(tmp_path)

    # additional optional files
    make_file(tmp_path / "README.md")
    make_file(tmp_path / "UppASD" / "README.md")

    assert uppsala.collect_dataset(tmp_path)

    # uneven green.inp-* out-*
    make_file(tmp_path / "RSPt" / "Jij" / "out-2")

    assert not uppsala.collect_dataset(tmp_path)

    # add missing green.inp-*
    make_file(tmp_path / "RSPt" / "Jij" / "green.inp-2")

    assert uppsala.collect_dataset(tmp_path)

    # additional files: not allowed
    make_file(tmp_path / "my_custom_file")
    assert not uppsala.collect_dataset(tmp_path)

    (tmp_path / "my_custom_file").unlink()
    make_file(tmp_path / "RSPt" / "gs_x" / "computed_with")
    assert not uppsala.collect_dataset(tmp_path)

    (tmp_path / "RSPt" / "gs_x" / "computed_with").unlink()

    # additional directories: not allowed
    (tmp_path / "mydir").mkdir()
    assert not uppsala.collect_dataset(tmp_path)

    make_file(tmp_path / "mydir" / "myfile")
    assert not uppsala.collect_dataset(tmp_path)

    (tmp_path / "mydir" / "myfile").unlink()
    (tmp_path / "mydir").rmdir()

    make_file(tmp_path / "RSPt" / "common_input" / "extras" / "myfile")
    assert not uppsala.collect_dataset(tmp_path)
