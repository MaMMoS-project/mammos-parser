"""Create derived files."""

import functools
import re
from logging import getLogger
from pathlib import Path

import mammos_analysis
import mammos_entity
import mammos_entity as me
import mammos_units as u
import numpy as np
import pandas as pd
import scipy.signal
import yaml

from mammos_parser import __version__

from ._validate import load_schema

logger = getLogger(__name__)


def find_in_file(filename: str | Path, expression) -> str:
    """Find subexpression in file.

    Returns the last capture group or the full match if `expression` does not have any
    capture groups.
    """
    matches = re.findall(expression, Path(filename).read_text())
    if not matches:
        raise RuntimeError(f"Could not find {expression} in {filename}.")
    return matches[-1]


@functools.cache
def unit_cell_volume(file_path: Path) -> u.Quantity[u.m**3]:
    """Read unit cell volume from out_last file."""
    unit_cell_volume = (
        float(find_in_file(file_path, r"unit cell volume:[ ]*([0-9.]+)"))
        * u.constants.a0**3
    )
    logger.info(
        "Unit cell volume from '%s': %s",
        file_path,
        round(unit_cell_volume.to("Angstrom3"), 2),
    )
    return unit_cell_volume.to("m3")


def compute_spontaneous_magnetization(
    file_path: Path,
) -> mammos_entity.Entity:
    """Compute spontaneous magnetization from RSPt out_last file."""
    # Use a dictionary to collect moments and directions because results for the same
    # atom+orbital information (used as key in the dict) can appear multiple times in
    # the file. We are only interested in the last occurence (last calculation step).
    # Bu using a dict we automatically get the desired values.
    moments: dict[str, float] = {}
    directions: dict[str, tuple[float, float, float]] = {}

    with open(file_path) as f:
        for line in f:
            if "Total moment [J=L+S] (mu_B):" in line:
                # line has content
                # <KEY> Total moment ...: <moment_cartesian> <moment_spin_axis>
                key = line.split()[0]
                moment = line.split()[-2]
                moments[key] = float(moment)
            elif "Direction of J (Cartesian):" in line:
                # line has content
                # <KEY> Direction of ...: <x> <y> <z>
                key = line.split()[0]
                direction = tuple(map(float, line.split()[-3:]))
                directions[key] = direction

    total_moment = 0 * u.mu_B
    for key, moment in moments.items():
        # Cartesian directions of the moment, orientation predominantly along one axis,
        # we are only interested in the sign.
        primary_directions = [dir_ for dir_ in directions[key] if abs(dir_) > 0.9]
        assert len(primary_directions) == 1
        total_moment += moment * round(primary_directions[0]) * u.mu_B

    return me.Ms((total_moment / unit_cell_volume(file_path)).to("kA/m"))


def compute_Ku(
    base_path: Path,
) -> mammos_entity.Entity:
    """Compute MAE from dataset using one of several methods."""
    if (base_path / "RSPt/gs_x/hist").exists():
        # Total energy difference (preferred method)
        # example line:
        # e   28 7.82E-14 ( 7.59E-11)     7.25741013        -17,483.270 409 502
        # we need to extract the last number (energy) -17483.270409502
        value_expr = r"\ne.*?(-?[0-9,]+\.[0-9 ]+)\n"
        file_ = "hist"
        description = "Ku from total energy"
    elif (base_path / "RSPt/gs_x/out_MF").exists():
        # Force theorem
        # example line:
        # Eigenvalue sum: -93.5684396400865
        value_expr = r"Eigenvalue sum:\s*([-0-9.]+)"
        file_ = "out_MF"
        description = "Ku from force theorem"
    else:
        raise RuntimeError(
            "Did not find a file to extract Ku (gs_x/hist and gs_x/out_MF missing)"
        )

    value_x = float(
        find_in_file(
            base_path / f"RSPt/gs_x/{file_}",
            value_expr,
        )
        .replace(" ", "")
        .replace(",", "")
    )
    if (base_path / f"RSPt/gs_y/{file_}").exists():
        value_y = float(
            find_in_file(
                base_path / f"RSPt/gs_y/{file_}",
                value_expr,
            )
            .replace(" ", "")
            .replace(",", "")
        )
    else:
        value_y = value_x
    value_z = float(
        find_in_file(
            base_path / f"RSPt/gs_z/{file_}",
            value_expr,
        )
        .replace(" ", "")
        .replace(",", "")
    )

    delta_e = max(value_x - value_z, value_y - value_z) * u.Ry
    vol = unit_cell_volume(base_path / "RSPt/gs_x/out_last")

    return me.Entity(
        "UniaxialAnisotropyConstant",
        (delta_e / vol).to("MJ/m3"),
        description=description,
    )


def _Tc_from_kuzmin(
    temperature_data: mammos_entity.EntityCollection,
) -> mammos_entity.Entity:
    Tc_kuzmin = mammos_analysis.kuzmin.kuzmin_properties(
        T=temperature_data.T, Ms=temperature_data.Ms
    ).Tc
    Tc_kuzmin.description = "Tc from Kuz'min fit."
    logger.info("Tc from Kuzmin: %s", Tc_kuzmin)
    return Tc_kuzmin


def _Tc_from_Cv(
    temperature_data: mammos_entity.EntityCollection, Tc_kuzmin: mammos_entity.Entity
) -> mammos_entity.Entity:
    peaks, _props = scipy.signal.find_peaks(temperature_data.Cv.value)
    Tc_Cv = temperature_data.T.q[peaks]
    if len(Tc_Cv) > 1:
        logger.info(
            "Found multiple peaks in Cv at temperatures: %s. Will pick the one closest"
            " to Tc from Kuzmin.",
            Tc_Cv,
        )
        idx = np.argmin(np.abs(Tc_Cv - Tc_kuzmin.q))
        Tc_Cv = Tc_Cv[idx]

    Tc_Cv = me.Tc(Tc_Cv, description="Tc from peak in specific heat")
    logger.info("Tc from Cv peak: %s", Tc_Cv)
    peak_Cv = temperature_data.Cv.q[
        np.argmin(np.abs(temperature_data.T.value - Tc_Cv.value))
    ]
    logger.info("  (Cv peak: %s)", peak_Cv)
    return Tc_Cv


def _Tc_from_U_L(
    temperature_data_1: mammos_entity.EntityCollection,
    temperature_data_2: mammos_entity.EntityCollection,
    Tc_kuzmin: mammos_entity.Entity,
    Tc_Cv: mammos_entity.Entity,
) -> mammos_entity.Entity:
    U_L1 = scipy.interpolate.make_interp_spline(
        temperature_data_1.T.q, temperature_data_1.U_L.q, k=1
    )
    U_L2 = scipy.interpolate.make_interp_spline(
        temperature_data_2.T.q, temperature_data_2.U_L.q, k=1
    )

    # Compute crossing starting from both Tc_kuzmin and Tc_Cv; both should lead to the
    # same result. If they don't, that is a good indication that something failed.
    crossings = scipy.optimize.fsolve(
        lambda t: U_L1(t) - U_L2(t), [Tc_kuzmin.value, Tc_Cv.value]
    )
    if not np.isclose(crossings[0], crossings[1]):
        raise RuntimeError(
            "Got two different Tc estimates from Binder cumulant:\n"
            f"With initial guess from Kuzmin ({Tc_kuzmin}) got: {crossings[0]}\n"
            f"With initial guess from Cv ({Tc_Cv}) got: {crossings[1]}"
        )
    Tc_U_L = me.Tc(
        crossings[0],
        unit=temperature_data_1.T.unit,
        description="Tc from crossing of Binder cumulant from MC_1 and MC_2.",
    )
    logger.info("Tc from crossing of Binder cumulant of MC_1 and MC_2: %s", Tc_U_L)
    return Tc_U_L


def compute_Tc(base_path: Path) -> mammos_entity.Entity:
    """Compute Tc from crossing of Binder cumulants or specific heat."""
    temperature_data = me.io.entities_from_file(base_path / "UppASD/MC_1/thermal.yaml")
    Tc_kuzmin = _Tc_from_kuzmin(temperature_data)
    Tc_Cv = _Tc_from_Cv(temperature_data)

    if (base_path / "UppASD/MC_2").exists():
        Tc_U_L = _Tc_from_U_L(
            temperature_data,
            me.io.entities_from_file(base_path / "UppASD/MC_1/thermal.yaml"),
        )
    else:
        Tc_U_L = None

    max_Tc_diff = 10 * u.K  # TODO x% or ± 1 grid point
    if (delta_T := abs(Tc_Cv.q - Tc_kuzmin.q)) > max_Tc_diff:
        raise RuntimeError(
            f"Tc from Kuzmin '{Tc_kuzmin}' and Cv '{Tc_Cv}' deviate by "
            f"{delta_T} > {max_Tc_diff}"
        )
    if Tc_U_L and (delta_T := abs(Tc_U_L.q - Tc_kuzmin.q)) > max_Tc_diff:
        raise RuntimeError(
            f"Tc from Kuzmin '{Tc_kuzmin}' and Binder cumulant '{Tc_U_L}' deviate by "
            f"{delta_T} > {max_Tc_diff}"
        )

    return Tc_U_L or Tc_Cv


def generate_intrinsic_properties_yaml(base_path: Path) -> None:
    """Collect intrinsic properties."""
    logger.info(f"Generating '{base_path}/intrinsic_properties.yaml'")
    Ms = compute_spontaneous_magnetization(base_path / "RSPt/gs_x/out_last")
    Js = me.Js(Ms.q.to("T", equivalencies=u.magnetic_flux_field()))
    Ku = compute_Ku(base_path)
    Tc = compute_Tc(base_path)

    me.EntityCollection(
        description="Intrinsic magnetic properties computed with RSPt and UppASD.",
        Js=Js,
        Ms=Ms,
        Ku=Ku,
        Tc=Tc,
    ).to_yaml(base_path / "intrinsic_properties.yaml")


def generate_mc_output(base_path: Path, mc_dirname: str) -> None:
    """Read thermal.dat and create thermal.csv."""
    logger.info(f"Generating '{base_path}/UppASD/{mc_dirname}/thermal.yaml'")
    with open(base_path / f"UppASD/{mc_dirname}/momfile") as f:
        # count all non-empty lines
        atom_count = len(list(filter(lambda line: line, f.readlines())))
    logger.info("Number of atoms from momfile: %i", atom_count)

    volume = unit_cell_volume(base_path / "RSPt/gs_x/out_last")

    raw_data = pd.read_csv(base_path / f"UppASD/{mc_dirname}/thermal.dat", sep=r"\s+")

    T = me.T(raw_data["T"], "K")
    M_per_atom = raw_data["<M>"].to_numpy() * u.mu_B
    Ms = me.Ms((M_per_atom * atom_count / volume).to("kA/m"))
    E_per_atom = raw_data["<E>"].to_numpy() * u.mRy
    E = me.Entity("HelmholtzEnergy", (E_per_atom * atom_count).to("eV"))

    Cv = me.Entity(
        "IsochoricHeatCapacity",
        np.gradient(E.q, T.q),
        description="Computed as derivative dE/dT.",
    )
    U_L = me.Entity("BinderCumulant", raw_data["U_{Binder}"].to_numpy())
    chi = me.Entity("MagneticSusceptibility", raw_data[r"\chi"])

    me.EntityCollection(
        description="Temperature-dependent quantities computed with UppASD",
        T=T,
        Ms=Ms,
        Js=me.Js(Ms.q.to("T", equivalencies=u.magnetic_flux_field())),
        E=E,
        Cv=Cv,
        chi=chi,
        U_L=U_L,
    ).to_yaml(base_path / f"UppASD/{mc_dirname}/thermal.yaml")


def generate_metadata_yaml(base_path: Path):
    """Create dataset-schema.yaml."""
    logger.info(f"Generating '{base_path}/metadata.yaml'")
    schema = load_schema()
    content = {
        "dataset_schema_version": schema["meta"]["version"],
        "mammos_parser_version": __version__,
    }
    with open(base_path / "metadata.yaml", "w") as f:
        yaml.dump(content, f)


def generate_derived_files(base_path: Path) -> None:
    """Generate derived files."""
    generate_metadata_yaml(base_path)
    for i in [1, 2, 3]:
        if (base_path / f"UppASD/MC_{i}").is_dir():
            generate_mc_output(base_path, f"MC_{i}")
    generate_intrinsic_properties_yaml(base_path)
