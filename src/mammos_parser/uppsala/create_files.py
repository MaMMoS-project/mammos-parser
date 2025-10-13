"""Create derived files."""

from logging import getLogger
from pathlib import Path

import mammos_entity as me
import mammos_units as u

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
                print(key, moment)
            elif "Direction of J (Cartesian):" in line:
                # line has content
                # <KEY> Direction of ...: <x> <y> <z>
                key = line.split()[0]
                direction = tuple(map(float, line.split()[-3:]))
                directions[key] = direction
                print(key, direction)

    total_moment = 0 * u.mu_B
    for key, moment in moments.items():
        print(key, moment, directions[key])
        # Cartesian directions of the moment, orientation predominantly along one axis,
        # we are only interested in the sign.
        direction = [dir_ for dir_ in directions[key] if abs(dir_) > 0.9][0]
        assert len([dir_ for dir_ in directions[key] if abs(dir_) > 0.9]) == 1
        print(moment, direction)
        total_moment += moment * round(direction) * u.mu_B

    return me.Ms((total_moment / unit_cell_volume(file_path)).to("A/m"))


def compute_MAE(dataset: util.Collected) -> me.Entity:
    """Compute MAE from dataset using one of several methods."""
    if "RSPt/gs_x/hist" in dataset.collected_files:
        # Total energy difference
        # example line:
        # e   28 7.82E-14 ( 7.59E-11)     7.25741013        -17,483.270 409 502
        # we need to extract the last number (energy) -17...
        value_expr = r"\ne.*?(-?[0-9,]+\.[0-9 ]+)\n"
        file_ = "hist"
    elif "RSPt/gs_x/out_MF" in dataset.collected_files:
        # Force theorem
        # example line:
        # Eigenvalue sum: -93.5684396400865
        value_expr = r"Eigenvalue sum:\s*([-0-9.]+)"
        file_ = "out_MF"
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
    )


def _compute_Tc(dataset: util.Collected) -> me.Entity:
    return me.Tc(0)
    # raise NotImplementedError()


def generate_intrinsic_properties_yaml(base_path: Path) -> None:
    """Collect intrinsic properties."""
    data = collect_dataset(base_path)

    Ms = compute_spontaneous_magnetization(data.root_dir / "RSPt/gs_x/out_last")
    Js = me.Js(Ms.q.to("T", equivalencies=u.magnetic_flux_field()))
    MAE = compute_MAE(data)
    Tc = _compute_Tc(data)

    me.io.entities_to_file(
        data.root_dir / "intrinsic_properties.yaml",
        Js=Js,
        Ms=Ms,
        MAE=MAE,
        Tc=Tc,
    )


def generate_derived_files(base_path: Path) -> None:
    """Generate derived files."""
    # TODO generate output.csv from M(T)
    generate_intrinsic_properties_yaml(base_path)
