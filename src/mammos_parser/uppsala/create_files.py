"""Create derived files."""

import re
from logging import getLogger
from pathlib import Path

import mammos_analysis
import mammos_entity as me
import mammos_units as u
import numpy as np
import pandas as pd

from mammos_parser import util

from . import collect_dataset

logger = getLogger(__name__)


def _generate_MC_results_csv():
    pass


def unit_cell_volume(file_path: Path) -> u.Quantity[u.m**3]:
    """Read unit cell volume from out_last file."""
    unit_cell_volume_au = float(
        util.find_in_file(file_path, r"unit cell volume:[ ]*([0-9.]+)")
    )
    logger.debug("Unit cell volume (a.u.): %s", unit_cell_volume_au)
    return (unit_cell_volume_au * u.constants.a0**3).to("m3")


def compute_spontaneous_magnetization(file_path: Path) -> me.Entity:
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
        direction = [dir_ for dir_ in directions[key] if abs(dir_) > 0.9][0]
        assert len([dir_ for dir_ in directions[key] if abs(dir_) > 0.9]) == 1
        total_moment += moment * round(direction) * u.mu_B

    return me.Ms((total_moment / unit_cell_volume(file_path)).to("kA/m"))


def compute_MAE(dataset: util.Collected) -> me.Entity:
    """Compute MAE from dataset using one of several methods."""
    if "RSPt/gs_x/hist" in dataset.collected_files:
        # Total energy difference
        # example line:
        # e   28 7.82E-14 ( 7.59E-11)     7.25741013        -17,483.270 409 502
        # we need to extract the last number (energy) -17...
        value_expr = r"\ne.*?(-?[0-9,]+\.[0-9 ]+)\n"
        file_ = "hist"
        description = "MAE from total energy"
    elif "RSPt/gs_x/out_MF" in dataset.collected_files:
        # Force theorem
        # example line:
        # Eigenvalue sum: -93.5684396400865
        value_expr = r"Eigenvalue sum:\s*([-0-9.]+)"
        file_ = "out_MF"
        description = "MAE from force theorem"
    else:
        raise RuntimeError(
            "Did not find a file to extract MAE (gs_x/hist and gs_x/out_MF missing)"
        )

    value_x = float(
        util.find_in_file(
            dataset.root_dir / f"RSPt/gs_x/{file_}",
            value_expr,
        )
        .replace(" ", "")
        .replace(",", "")
    )
    if f"RSPt/gs_y/{file_}" in dataset.collected_files:
        value_y = float(
            util.find_in_file(
                dataset.root_dir / f"RSPt/gs_y/{file_}",
                value_expr,
            )
            .replace(" ", "")
            .replace(",", "")
        )
    else:
        value_y = value_x
    value_z = float(
        util.find_in_file(
            dataset.root_dir / f"RSPt/gs_z/{file_}",
            value_expr,
        )
        .replace(" ", "")
        .replace(",", "")
    )

    delta_e = max(value_x - value_z, value_y - value_z) * u.Ry
    vol = unit_cell_volume(dataset.root_dir / "RSPt/gs_x/out_last")

    return me.Entity(
        "MagnetocrystallineAnisotropyEnergy",
        (delta_e / vol).to("MJ/m3"),
        description=description,
    )


def _compute_Tc(uppasd_data: Path) -> me.Entity:
    if (uppasd_data / "MC_2").exists():
        raise NotImplementedError(
            "Computing Tc from Binder cumulant is not yet implemented."
        )
    else:
        temperature_data = me.io.entities_from_file(uppasd_data / "MC_1" / "output.csv")
        Tc_kuzmin = mammos_analysis.kuzmin.kuzmin_properties(
            T=temperature_data.T, Ms=temperature_data.Ms
        ).Tc
        logger.info("Tc from Kuzmin: %s", Tc_kuzmin)

        cv_peak = temperature_data.Cv.q.max()
        cv_peak_position = temperature_data.Cv.value.argmax()
        Tc_Cv = me.Tc(
            temperature_data.T.q[cv_peak_position], description="Tc from specific heat"
        )
        logger.info("Tc from Cv peak: %s", Tc_Cv)
        logger.info("Cv peak: %s", cv_peak)
        if (delta_T := abs(Tc_Cv.q - Tc_kuzmin.q)) > 50 * u.K:
            raise RuntimeError(
                f"Tc from Kuzmin '{Tc_kuzmin}' and Cv '{Tc_Cv}' deviate by {delta_T} >"
                " 50K"
            )
        return Tc_Cv


def generate_intrinsic_properties_yaml(base_path: Path) -> None:
    """Collect intrinsic properties."""
    data = collect_dataset(base_path)

    Ms = compute_spontaneous_magnetization(data.root_dir / "RSPt/gs_x/out_last")
    Js = me.Js(Ms.q.to("T", equivalencies=u.magnetic_flux_field()))
    MAE = compute_MAE(data)
    Tc = _compute_Tc(base_path / "UppASD")

    me.io.entities_to_file(
        data.root_dir / "intrinsic_properties.yaml",
        Js=Js,
        Ms=Ms,
        MAE=MAE,
        Tc=Tc,
    )


def generate_mc_output(base_path: Path) -> None:
    """Read M(T) and create output.csv."""
    data = collect_dataset(base_path)

    with open(data.root_dir / "UppASD/MC_1/momfile") as f:
        # count all non-empty lines
        atom_count = len(list(filter(lambda line: line, f.readlines())))
    logger.info("Number of atoms: %i", atom_count)

    with open(data.root_dir / "UppASD/MC_1/inpsd.dat") as f:
        inpsd = f.read()

    alat = re.search(r"alat\s+([^\s]+)", inpsd).groups()[0]
    scaling = float(alat) * u.m
    vector = r"[^\s]+\s+[^\s]+\s+[^\s]+"
    unit_cell_strings = re.search(
        rf"cell\s+({vector}).*\n\s+({vector}).*\n\s+({vector})", inpsd
    )
    a, b, c = map(
        lambda string: tuple(map(float, string.split())), unit_cell_strings.groups()
    )

    unit_cell_volume = np.dot(a, np.cross(b, c)) * scaling**3
    logger.info("Unit cell volume: %s", unit_cell_volume.to("Angstrom3"))

    raw_data = pd.read_csv(data.root_dir / "UppASD/MC_1/M(T)", sep=r"\s+")
    # in the final dataset we keep T, Ms, E, Cv and U_{Binder}

    T = me.T(raw_data["#T[K]"], "K")
    M_per_atom = raw_data["<M>[μB]"].to_numpy() * u.mu_B
    Ms = me.Ms((M_per_atom * atom_count / unit_cell_volume).to("kA/m"))
    # random failures when creating an Energy entity:
    # https://github.com/MaMMoS-project/mammos-entity/issues/96
    E_per_atom = raw_data["<E>"].to_numpy() * u.mRy
    # E = me.Entity("Energy", (E_per_atom * atom_count).to("J"))
    E_q = (E_per_atom * atom_count).to("J")

    assert E_q.value.ndim == 1
    Cv = me.Entity("IsochoricHeatCapacity", np.gradient(E_q, T.q))

    me.io.entities_to_file(
        data.root_dir / "UppASD/MC_1/output.csv",
        description="Temperature-dependent quantities computed with UppASD",
        T=T,
        Ms=Ms,
        Js=me.Js(Ms.q.to("T", equivalencies=u.magnetic_flux_field())),
        E=E_q,
        Cv=Cv,
        U_Binder=raw_data["U_{Binder}"].to_numpy(),
    )


def generate_derived_files(base_path: Path) -> None:
    """Generate derived files."""
    generate_mc_output(base_path)
    generate_intrinsic_properties_yaml(base_path)
