from pathlib import Path

import mammos_entity as me
import mammos_units as u
import yaml

from mammos_parser import uppsala


def make_file(file_path: Path):
    file_path.parent.mkdir(exist_ok=True, parents=True)
    file_path.touch()


def test_complete_datasets(tmp_path: Path):
    # Check various different conditions under which the dataset tmp_path is valid or
    # invalid. To reduce overhead of the setup additional files are added/removed as
    # needed. The order is therefor important.
    make_file(tmp_path / "intrinsic_properties.yaml")
    make_file(tmp_path / "structure.cif")
    make_file(tmp_path / "metadata.yaml")

    # incomplete
    assert not uppsala.validate_dataset(tmp_path)

    for name in ["atomdens", "kmap", "spts", "symcof", "symt.inp"]:
        make_file(tmp_path / "RSPt" / "common_input" / name)

    for dir_name in ["gs_x", "gs_z"]:
        for name in ["data", "hist", "out_last"]:
            make_file(tmp_path / "RSPt" / dir_name / name)

    for name in ["green.inp-1", "out-1", "data", "out_last"]:
        make_file(tmp_path / "RSPt" / "Jij" / name)

    for name in [
        "jfile",
        "momfile",
        "posfile",
        "inpsd.dat",
        "thermal.csv",
        "thermal.dat",
    ]:
        make_file(tmp_path / "UppASD" / "MC_1" / name)

    # all required files, first calculation mode

    # content of intrinsic_properties.yaml and thermal.csv missing
    assert not uppsala.validate_dataset(tmp_path)

    # add required file content
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
        Tc=me.Tc(1000, "K"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m"),
        Cv=me.Entity("IsochoricHeatCapacity", [1.3e-24, 1.4e-24, 1.5e-24], "J/K"),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"dataset_schema_version": 1, "mammos_parser_version": "0.1.0"}, f)
    assert uppsala.validate_dataset(tmp_path)

    # break yaml file
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
        T=me.Tc(100, "K").q,
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
        T=me.Tc(100, "K").value,
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
        T=me.Js(2, "T"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    # revert file contents for remaining checks
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
        Tc=me.Tc(1000, "K"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert uppsala.validate_dataset(tmp_path)

    # break csv file
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m"),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m").q,
        Cv=me.Entity("IsochoricHeatCapacity", [1.3e-24, 1.4e-24, 1.5e-24], "J/K"),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m").value,
        Cv=me.Entity("IsochoricHeatCapacity", [1.3e-24, 1.4e-24, 1.5e-24], "J/K"),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m"),
        Cv=me.T([1, 10, 100]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    # revert file contents for remaining checks
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([5e5, 6e5, 7e5], "A/m"),
        Cv=me.Entity("IsochoricHeatCapacity", [1.3e-24, 1.4e-24, 1.5e-24], "J/K"),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert uppsala.validate_dataset(tmp_path)

    # break dataset-schema.yaml
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"dataset_schema_version": 2, "mammos_parser_version": "0.1.0"}, f)
    assert not uppsala.validate_dataset(tmp_path)
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"dataset_schema_version": "1", "mammos_parser_version": "0.1.0"}, f)
    assert not uppsala.validate_dataset(tmp_path)
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump(
            {
                "dataset_schema_version": 1,
                "mammos_parser_version": "0.1.0",
                "other": "false",
            },
            f,
        )
    assert not uppsala.validate_dataset(tmp_path)
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"mammos_parser_version": "0.1.0"}, f)
    assert not uppsala.validate_dataset(tmp_path)
    # revert file content for remaining checks
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"dataset_schema_version": 1, "mammos_parser_version": "0.1.0"}, f)
    assert uppsala.validate_dataset(tmp_path)

    # # overwrite with a file with incompatible Js and Ms
    # me.EntityCollection(
    #     Js=me.Js(2, "T"),
    #     Ms=me.Ms(2, "A/m"),
    #     MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
    #     Tc=me.Tc(1000, "K"),
    # ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    # assert not uppsala.validate_dataset(tmp_path)

    # # revert file for the remaining checks
    # me.EntityCollection(
    #     Js=me.Js(2, "T"),
    #     Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
    #     MAE=me.Entity("MagnetocrystallineAnisotropyEnergy", 1.5, "MJ/m3"),
    #     Tc=me.Tc(1000, "K"),
    # ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    # second calculation mode in addition: not allowed
    for dir_name in ["gs_x", "gs_z"]:
        make_file(tmp_path / "RSPt" / dir_name / "out_MF")

    assert not uppsala.validate_dataset(tmp_path)

    # remove first calculation mode
    for dir_name in ["gs_x", "gs_z"]:
        (tmp_path / "RSPt" / dir_name / "hist").unlink()

    assert uppsala.validate_dataset(tmp_path)

    # optional third directory
    for name in ["data", "out_MF", "out_last"]:
        make_file(tmp_path / "RSPt" / "gs_y" / name)

    assert uppsala.validate_dataset(tmp_path)

    # additional optional files
    make_file(tmp_path / "README.md")
    make_file(tmp_path / "UppASD" / "README.md")

    assert uppsala.validate_dataset(tmp_path)

    # uneven green.inp-* out-*
    make_file(tmp_path / "RSPt" / "Jij" / "out-2")

    assert not uppsala.validate_dataset(tmp_path)

    # add missing green.inp-*
    make_file(tmp_path / "RSPt" / "Jij" / "green.inp-2")

    assert uppsala.validate_dataset(tmp_path)

    # additional files: not allowed
    make_file(tmp_path / "my_custom_file")
    assert not uppsala.validate_dataset(tmp_path)

    (tmp_path / "my_custom_file").unlink()
    make_file(tmp_path / "RSPt" / "gs_x" / "computed_with")
    assert not uppsala.validate_dataset(tmp_path)

    (tmp_path / "RSPt" / "gs_x" / "computed_with").unlink()

    # additional directories: not allowed
    (tmp_path / "mydir").mkdir()
    assert not uppsala.validate_dataset(tmp_path)

    make_file(tmp_path / "mydir" / "myfile")
    assert not uppsala.validate_dataset(tmp_path)

    (tmp_path / "mydir" / "myfile").unlink()
    (tmp_path / "mydir").rmdir()

    make_file(tmp_path / "RSPt" / "common_input" / "extras" / "myfile")
    assert not uppsala.validate_dataset(tmp_path)
