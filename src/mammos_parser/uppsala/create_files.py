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
    # By using a dict we automatically get the desired values.
    moments: dict[str, float] = {}
    directions: dict[str, tuple[float, float, float]] = {}

    with open(file_path) as f:
        for line in f:
            if "Total moment [J=L+S] (mu_B):" in line:
                # line has content
                # <KEY> Total moment ...: <moment_cartesian> <moment_spin_axis>
                parts = line.split()
                try:
                    key = parts[0]
                    moments[key] = float(parts[-2])
                except (IndexError, ValueError) as e:
                    raise RuntimeError(
                        f"Malformed out_last '{file_path}': invalid total moment line:"
                        f" {line.strip()}"
                    ) from e
            elif "Direction of J (Cartesian):" in line:
                # line has content
                # <KEY> Direction of ...: <x> <y> <z>
                parts = line.split()
                try:
                    key = parts[0]
                    direction = tuple(map(float, parts[-3:]))
                except (IndexError, ValueError) as e:
                    raise RuntimeError(
                        f"Malformed out_last '{file_path}': invalid direction line:"
                        f" {line.strip()}"
                    ) from e
                if len(direction) != 3:
                    raise RuntimeError(
                        f"Malformed out_last '{file_path}': invalid direction line: "
                        f"{line.strip()}"
                    )
                directions[key] = direction

    if not moments:
        raise RuntimeError(
            f"Malformed out_last '{file_path}': no "
            "'Total moment [J=L+S] (mu_B):' entries found."
        )

    total_moment = 0 * u.mu_B
    for key, moment in moments.items():
        if key not in directions:
            raise RuntimeError(
                f"Malformed out_last '{file_path}': missing "
                f"'Direction of J (Cartesian)' entry for '{key}'."
            )
        # Cartesian directions of the moment, orientation predominantly along one axis,
        # we are only interested in the sign.
        primary_directions = [dir_ for dir_ in directions[key] if abs(dir_) > 0.9]
        if len(primary_directions) != 1:
            raise RuntimeError(
                f"Malformed out_last '{file_path}': expected exactly one predominant "
                f"direction component (>0.9 in absolute value) for '{key}', got "
                f"{directions[key]}."
            )
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
    if len(peaks) == 0:
        raise RuntimeError("Could not find peaks in Cv.")
    Tc_Cv = temperature_data.T.q[peaks]
    if len(Tc_Cv) > 1:
        logger.info(
            "Found multiple peaks in Cv at temperatures: %s. Will pick the one closest"
            " to Tc from Kuzmin.",
            Tc_Cv,
        )
        idx = np.argmin(np.abs(Tc_Cv - Tc_kuzmin.q))
        Tc_Cv = Tc_Cv[idx]

    Tc_Cv = me.Tc(Tc_Cv.item(), description="Tc from peak in specific heat")
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
    # Determine crossings of two piecewise-linear curves on potentially different
    # temperature grids.
    t_1 = np.atleast_1d(temperature_data_1.T.value)
    t_2 = np.atleast_1d(temperature_data_2.T.value)
    u_l_1 = np.atleast_1d(temperature_data_1.U_L.value)
    u_l_2 = np.atleast_1d(temperature_data_2.U_L.value)

    order_1 = np.argsort(t_1)
    order_2 = np.argsort(t_2)
    t_1, u_l_1 = t_1[order_1], u_l_1[order_1]
    t_2, u_l_2 = t_2[order_2], u_l_2[order_2]

    if np.any(np.diff(t_1) == 0) or np.any(np.diff(t_2) == 0):
        raise RuntimeError(
            "Cannot determine Tc from Binder cumulant: duplicated temperatures in input"
        )

    t_min = max(t_1[0], t_2[0])
    t_max = min(t_1[-1], t_2[-1])
    if t_min >= t_max:
        raise RuntimeError(
            "Cannot determine Tc from Binder cumulant: no overlapping T range"
        )

    knots = np.unique(np.concatenate([t_1, t_2]))
    knots = knots[(knots >= t_min) & (knots <= t_max)]
    if len(knots) < 2:
        raise RuntimeError(
            "Cannot determine Tc from Binder cumulant: insufficient overlapping T "
            f"points: {knots}"
        )

    # Linear interpolation on each curve at all breakpoints of either curve.
    delta_u_l = np.interp(knots, t_1, u_l_1) - np.interp(knots, t_2, u_l_2)
    atol = 1e-12

    roots: list[float] = []
    for i in range(len(knots) - 1):
        left = knots[i]
        right = knots[i + 1]
        delta_left = delta_u_l[i]
        delta_right = delta_u_l[i + 1]

        if np.isclose(delta_left, 0.0, atol=atol):
            # delta_right == 0 will be dealt with in the next iteration
            roots.append(left)
        elif delta_left * delta_right < 0:
            # for the segment
            # delta_ul(x) = delta_left + (delta_right - delta_left) / (right - left) * x
            # crossing at delta_ul(x) = 0
            # -> x = -delta_left * (right - left) / (delta_right - delta_left)
            roots.append(
                left - delta_left * (right - left) / (delta_right - delta_left)
            )

    if np.isclose(delta_u_l[-1], 0.0, atol=atol):
        roots.append(knots[-1])

    if not roots:
        raise RuntimeError(
            "Cannot determine Tc from Binder cumulant: U_L curves do not cross in the"
            " overlapping temperature range."
        )

    roots = np.unique(roots)

    # Select root nearest to each prior estimate. If the priors point to different
    # crossings, the input data are ambiguous and we fail.
    crossing_kuzmin_id = np.argmin(np.abs(roots - Tc_kuzmin.value))
    crossing_cv_id = np.argmin(np.abs(roots - Tc_Cv.value))
    crossing_kuzmin = roots[crossing_kuzmin_id]
    crossing_cv = roots[crossing_cv_id]
    if crossing_kuzmin_id != crossing_cv_id:
        raise RuntimeError(
            "Got two different Tc estimates from Binder cumulant:\n"
            f"With initial guess from Kuzmin ({Tc_kuzmin}) got: {crossing_kuzmin}\n"
            f"With initial guess from Cv ({Tc_Cv}) got: {crossing_cv}"
        )

    Tc_U_L = me.Tc(
        crossing_kuzmin,
        unit=temperature_data_1.T.unit,
        description="Tc from crossing of Binder cumulant from MC_1 and MC_2.",
    )
    logger.info("Tc from crossing of Binder cumulant of MC_1 and MC_2: %s", Tc_U_L)
    return Tc_U_L


def compute_Tc(base_path: Path) -> mammos_entity.Entity:
    """Compute Tc from crossing of Binder cumulants or specific heat."""
    temperature_data = me.from_yaml(base_path / "UppASD/MC_1/thermal.yaml")
    Tc_kuzmin = _Tc_from_kuzmin(temperature_data)
    Tc_Cv = _Tc_from_Cv(temperature_data, Tc_kuzmin)

    if (base_path / "UppASD/MC_2").exists():
        Tc_U_L = _Tc_from_U_L(
            temperature_data,
            me.from_yaml(base_path / "UppASD/MC_2/thermal.yaml"),
            Tc_kuzmin,
            Tc_Cv,
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
    """Read thermal.dat and create thermal.yaml."""
    logger.info(f"Generating '{base_path}/UppASD/{mc_dirname}/thermal.yaml'")
    with open(base_path / f"UppASD/{mc_dirname}/momfile") as f:
        # count all non-empty lines
        atom_count = len(list(filter(lambda line: line.strip(), f.readlines())))
    logger.info("Number of atoms from momfile: %i", atom_count)

    volume = unit_cell_volume(base_path / "RSPt/gs_x/out_last")

    raw_data = pd.read_csv(base_path / f"UppASD/{mc_dirname}/thermal.dat", sep=r"\s+")
    if len(raw_data.index) < 2:
        raise RuntimeError(
            "Cannot compute Cv from "
            f"'{base_path}/UppASD/{mc_dirname}/thermal.dat': need at least 2 "
            f"temperature points, got {len(raw_data.index)}."
        )

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
    """Create metadata.yaml."""
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
