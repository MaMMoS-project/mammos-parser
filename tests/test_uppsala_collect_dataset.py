from pathlib import Path

import mammos_entity as me
import mammos_units as u
import yaml

from mammos_parser import __version__, uppsala


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
        Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
        Tc=me.Tc(1000, "K"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    (tmp_path / "UppASD" / "MC_1" / "inpsd.dat").write_text("ncell 10 10 10")
    (tmp_path / "UppASD" / "MC_1" / "thermal.dat").write_text(
        "T <M> <M^2> <M^4> U_{Binder} \\chi C_v(tot) <E> <E_{exc}> <E_{lsf}>\n"
        "1 1 1 1 0.5 0.1 0.2 0.3 0.4 0.5\n"
    )
    # Numbers of thermal.dat and thermal.csv do not match but the parser does not check
    # for that because thermal.csv is (supposed to be) auto-generated.
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([500, 600, 700], "kA/m"),
        Js=me.Js(
            ([500, 600, 700] * u.kA / u.m).to(
                "T", equivalencies=u.magnetic_flux_field()
            )
        ),
        E=me.Entity("HelmholtzEnergy", [1.0, 2.0, 3.0], "eV"),
        Cv=me.Entity("IsochoricHeatCapacity", [0.1, 0.2, 0.3], "eV/K"),
        chi=me.Entity("MagneticSusceptibility", [1.0, 2.0, 3.0]),
        U_L=me.Entity("BinderCumulant", [0.7, 0.6, 0.5]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump(
            {"dataset_schema_version": 1, "mammos_parser_version": __version__}, f
        )
    assert uppsala.validate_dataset(tmp_path)

    # break intrinsic_properties.yaml
    # missing Tc
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    # Tc is a quantity
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
        Tc=me.Tc(100, "K").q,
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    # Tc is a number
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
        Tc=me.Tc(100, "K").value,
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    # Tc is of the wrong entity type
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
        Tc=me.Js(2, "T"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert not uppsala.validate_dataset(tmp_path)
    # revert file contents for remaining checks
    me.EntityCollection(
        Js=me.Js(2, "T"),
        Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
        Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
        Tc=me.Tc(1000, "K"),
    ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    assert uppsala.validate_dataset(tmp_path)

    # break thermal.csv file
    # missing Cv
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([500, 600, 700], "kA/m"),
        Js=me.Js([0.6, 0.7, 0.8], "T"),
        E=me.Entity("HelmholtzEnergy", [1.0, 2.0, 3.0], "eV"),
        chi=me.Entity("MagneticSusceptibility", [1.0, 2.0, 3.0]),
        U_L=me.Entity("BinderCumulant", [0.7, 0.6, 0.5]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    # Ms is a quantity
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([500, 600, 700], "kA/m").q,
        Js=me.Js([0.6, 0.7, 0.8], "T"),
        E=me.Entity("HelmholtzEnergy", [1.0, 2.0, 3.0], "eV"),
        Cv=me.Entity("IsochoricHeatCapacity", [0.1, 0.2, 0.3], "eV/K"),
        chi=me.Entity("MagneticSusceptibility", [1.0, 2.0, 3.0]),
        U_L=me.Entity("BinderCumulant", [0.7, 0.6, 0.5]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    # Ms is a value
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([500, 600, 700], "kA/m").value,
        Js=me.Js([0.6, 0.7, 0.8], "T"),
        E=me.Entity("HelmholtzEnergy", [1.0, 2.0, 3.0], "eV"),
        Cv=me.Entity("IsochoricHeatCapacity", [0.1, 0.2, 0.3], "eV/K"),
        chi=me.Entity("MagneticSusceptibility", [1.0, 2.0, 3.0]),
        U_L=me.Entity("BinderCumulant", [0.7, 0.6, 0.5]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    # Cv is the wrong entity
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([500, 600, 700], "kA/m"),
        Js=me.Js([0.6, 0.7, 0.8], "T"),
        E=me.Entity("HelmholtzEnergy", [1.0, 2.0, 3.0], "eV"),
        Cv=me.T([1, 10, 100]),
        chi=me.Entity("MagneticSusceptibility", [1.0, 2.0, 3.0]),
        U_L=me.Entity("BinderCumulant", [0.7, 0.6, 0.5]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert not uppsala.validate_dataset(tmp_path)
    # revert file contents for remaining checks
    me.EntityCollection(
        T=me.T([1, 10, 100], "K"),
        Ms=me.Ms([500, 600, 700], "kA/m"),
        Js=me.Js([0.6, 0.7, 0.8], "T"),
        E=me.Entity("HelmholtzEnergy", [1.0, 2.0, 3.0], "eV"),
        Cv=me.Entity("IsochoricHeatCapacity", [0.1, 0.2, 0.3], "eV/K"),
        chi=me.Entity("MagneticSusceptibility", [1.0, 2.0, 3.0]),
        U_L=me.Entity("BinderCumulant", [0.7, 0.6, 0.5]),
    ).to_csv(tmp_path / "UppASD/MC_1/thermal.csv")
    assert uppsala.validate_dataset(tmp_path)

    # break dataset-schema.yaml
    # wrong dataset schema version
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"dataset_schema_version": 2, "mammos_parser_version": "0.1.0"}, f)
    assert not uppsala.validate_dataset(tmp_path)
    # wrong datatype for dataset schema version
    with open(tmp_path / "metadata.yaml", "w") as f:
        yaml.dump({"dataset_schema_version": "1", "mammos_parser_version": "0.1.0"}, f)
    assert not uppsala.validate_dataset(tmp_path)
    # additional keys in metadata.yaml
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
    # missing keys in metadata.yaml
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
    #     Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
    #     Tc=me.Tc(1000, "K"),
    # ).to_yaml(tmp_path / "intrinsic_properties.yaml")
    # assert not uppsala.validate_dataset(tmp_path)

    # # revert file for the remaining checks
    # me.EntityCollection(
    #     Js=me.Js(2, "T"),
    #     Ms=me.Ms((2 * u.T).to("kA/m", equivalencies=u.magnetic_flux_field())),
    #     Ku=me.Entity("UniaxialAnisotropyConstant", 1.5, "MJ/m3"),
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

    # non matching green.inp-* out-*
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
