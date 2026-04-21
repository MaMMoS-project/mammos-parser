from pathlib import Path
from textwrap import dedent

import mammos_entity as me
import mammos_units as u
import numpy as np
import pytest
from pytest import approx

from mammos_parser.uppsala import create_files


def test_unit_cell_volume(tmp_path: Path) -> None:
    (tmp_path / "out_last").write_text(
        dedent(
            """
                        MPI RSPT
            RSPt version number:         rspt.6.0102221136

            [...]

            unit cell volume:
                .521098162482626 * 11.0360004**3
                .124403022592820 * 11.0360004**3 * 4pi/3

            Procedures:

            [...]

                    9  1  2  1        1
                    9  1  2  1        2

            unit cell volume:  700.413751849785
                radius of V/N:  2.64854800
                muffin tins      interstitial   v(I)/vcell

            """
        )
    )

    ref_vol = (700.413751849785 * u.constants.a0**3).to("m3")
    unit_cell_volume = create_files.unit_cell_volume(tmp_path / "out_last")
    assert unit_cell_volume.value == pytest.approx(ref_vol.value)
    assert unit_cell_volume.unit == "m3"


def test_compute_magnetization_single(tmp_path: Path) -> None:
    (tmp_path / "out_last").write_text(
        dedent(
            """
                                    MPI RSPT
            RSPt version number:         rspt.6.0102221136
            ...
            unit cell volume:  700.413751849785
            ...

            ID:0102010100-o   Occupation:                       8.235952E+00
            ID:0102010100-o   Energy [Tr(HG)]:                  6.795966E+00
                                                                    Cartesian        Spin axis
            ID:0102010100-o   Spin moment [Sx] (mu_B):          1.524110E-01    -3.405743E-10
            ID:0102010100-o   Spin moment [Sy] (mu_B):         -9.542870E-06    -9.542870E-06
            ID:0102010100-o   Spin moment [Sz] (mu_B):          3.405743E-10     1.524110E-01
            ID:0102010100-o   Total Spin moment [S] (mu_B):     1.524110E-01     1.524110E-01
            ID:0102010100-o   Orbital moment [Lx] (mu_B):       7.452304E-03     2.979691E-10
            ID:0102010100-o   Orbital moment [Ly] (mu_B):       9.811214E-04     9.811214E-04
            ID:0102010100-o   Orbital moment [Lz] (mu_B):      -2.979691E-10     7.452304E-03
            ID:0102010100-o   Total Orbital moment [L] (mu_B):  7.516610E-03     7.516610E-03
            ID:0102010100-o   Total moment [Jx=Lx+Sx] (mu_B):   1.598633E-01    -4.260519E-11
            ID:0102010100-o   Total moment [Jy=Ly+Sy] (mu_B):   9.715785E-04     9.715785E-04
            ID:0102010100-o   Total moment [Jz=Lz+Sz] (mu_B):   4.260520E-11     1.598633E-01
            ID:0102010100-o   Total moment [J=L+S] (mu_B):      1.598663E-01     1.598663E-01
            ID:0102010100-o   Direction of S (Cartesian):       1.00000000 -0.00006261  0.00000000
            ID:0102010100-o   Direction of L (Cartesian):       0.99144474  0.13052711 -0.00000004
            ID:0102010100-o   Direction of J (Cartesian):       0.99998153  0.00607745  0.00000000
            ID:0102010100-o   Angle between L and S vec (deg):  7.50364040
            """  # noqa: E501
        )
    )

    unit_cell_volume = 700.413751849785 * u.constants.a0**3
    ref_Ms = (1.598663e-01 * u.mu_B / unit_cell_volume).to("kA/m")

    Ms = create_files.compute_spontaneous_magnetization(tmp_path / "out_last")
    assert Ms.value == approx(ref_Ms.value, rel=1e-6)
    assert Ms.unit == "kA/m"
    assert Ms.ontology_label == "SpontaneousMagnetization"


def test_compute_magnetization_multiple(tmp_path: Path) -> None:
    (tmp_path / "out_last").write_text(
        dedent(
            """
                                    MPI RSPT
            RSPt version number:         rspt.6.0102221136
            ...
            unit cell volume:  700.413751849785
            ...
            ID:0102010100-o   Total moment [J=L+S] (mu_B):      1.123456E-01     1.598663E-01
            ID:0102010100-o   Direction of J (Cartesian):       0.99998153  0.00607745  0.00000000

            ID:0101010100-o   Total moment [J=L+S] (mu_B):      9.123456E-03     9.608900E-03
            ID:0101010100-o   Direction of J (Cartesian):      -0.99989783 -0.01429458  0.00000000

            ID:0202010100-o   Total moment [J=L+S] (mu_B):      1.123456E-01     1.605796E-01
            ID:0202010100-o   Direction of J (Cartesian):       0.99998188 -0.00602021  0.00000000

            ...

            ID:0102010100-o   Total moment [J=L+S] (mu_B):      1.598663E-01     1.598663E-01
            ID:0102010100-o   Direction of J (Cartesian):       0.99998153  0.00607745  0.00000000

            ID:0101010100-o   Total moment [J=L+S] (mu_B):      9.608900E-03     9.608900E-03
            ID:0101010100-o   Direction of J (Cartesian):      -0.99989783 -0.01429458  0.00000000

            ID:0202010100-o   Total moment [J=L+S] (mu_B):      1.605796E-01     1.605796E-01
            ID:0202010100-o   Direction of J (Cartesian):       0.99998188 -0.00602021  0.00000000
            """  # noqa: E501
        )
    )

    unit_cell_volume = 700.413751849785 * u.constants.a0**3
    ref_Ms = (
        (1.598663e-01 - 9.608900e-03 + 1.605796e-01) * u.mu_B / unit_cell_volume
    ).to("kA/m")

    Ms = create_files.compute_spontaneous_magnetization(tmp_path / "out_last")
    assert Ms.value == approx(ref_Ms.value, rel=1e-6)
    assert Ms.unit == "kA/m"
    assert Ms.ontology_label == "SpontaneousMagnetization"


def test_compute_Ku_total_energy_difference(tmp_path: Path) -> None:
    (tmp_path / "RSPt/gs_x/").mkdir(parents=True)
    (tmp_path / "RSPt/gs_x/out_last").write_text(
        dedent(
            """
                                    MPI RSPT
            RSPt version number:         rspt.6.0102221136
            ...
            unit cell volume:  700.413751849785
            """
        )
    )

    unit_cell_volume = 700.413751849785 * u.constants.a0**3

    (tmp_path / "RSPt/gs_x/hist").write_text(
        dedent(
            """
            History
                Start runs ...
            Iter   <f**2>   (<fe**2>)         Moment                          E
            e    0 1.21E-03 ( 1.02E+00)     7.64784888        -17,447.186 756 597
            @      700.413751 -17447.1867565976

            ...

            Iter   <f**2>   (<fe**2>)         Moment                          E
            e   28 7.82E-14 ( 7.59E-11)     7.25741013        -17,483.270 409 502
            @      700.413751 -17483.2704095028
            ...
            """
        )
    )
    (tmp_path / "RSPt/gs_z/").mkdir()
    (tmp_path / "RSPt/gs_z/hist").write_text(
        dedent(
            """
            History
            ...
            e    0 1.23E-03 ( 1.02E+00)     7.63196137        -17,447.186 947 276
            @      700.413751 -17447.1869472760
            ...
            Iter   <f**2>   (<fe**2>)         Moment                          E
            e   28 7.83E-14 ( 7.49E-11)     7.24648930        -17,483.270 416 975
            @      700.413751 -17483.2704169749
            ...
            """
        )
    )

    Ex = -17483.270409502
    Ez = -17483.270416975
    ref_Ku = ((Ex - Ez) * u.Ry / unit_cell_volume).to("MJ/m3")
    Ku = create_files.compute_Ku(tmp_path)
    assert Ku.value == approx(ref_Ku.value)
    assert Ku.unit == "MJ/m^3"
    assert Ku.ontology_label == "UniaxialAnisotropyConstant"

    # Add y with larger value
    (tmp_path / "RSPt/gs_y/").mkdir()
    (tmp_path / "RSPt/gs_y/hist").write_text(
        dedent(
            """
            History
                Start runs ...
            Iter   <f**2>   (<fe**2>)         Moment                          E
            e    0 1.21E-03 ( 1.02E+00)     7.64784888        -17,447.186 756 597
            @      700.413751 -17447.1867565976

            ...

            Iter   <f**2>   (<fe**2>)         Moment                          E
            e   28 7.82E-14 ( 7.59E-11)     7.25741013        -17,483.270 400 000
            @      700.413751 -17483.2704095028
            ...
            """
        )
    )

    Ey = -17483.270400000
    assert Ex - Ez < Ey - Ez  # ensure yz is larger to confirm we use it
    ref_Ku = ((Ey - Ez) * u.Ry / unit_cell_volume).to("MJ/m3")
    Ku = create_files.compute_Ku(tmp_path)
    assert Ku.value == approx(ref_Ku.value)
    assert Ku.unit == "MJ/m^3"
    assert Ku.ontology_label == "UniaxialAnisotropyConstant"

    # Add y with smaller value
    (tmp_path / "RSPt/gs_y/hist").write_text(
        dedent(
            """
            History
                Start runs ...
            Iter   <f**2>   (<fe**2>)         Moment                          E
            e    0 1.21E-03 ( 1.02E+00)     7.64784888        -17,447.186 756 597
            @      700.413751 -17447.1867565976

            ...

            Iter   <f**2>   (<fe**2>)         Moment                          E
            e   28 7.82E-14 ( 7.59E-11)     7.25741013        -17,483.270 500 000
            @      700.413751 -17483.2704095028
            ...
            """
        )
    )

    Ey = -17483.270500000
    assert Ex - Ez > Ey - Ez  # ensure xz is larger to confirm we use it
    ref_Ku = ((Ex - Ez) * u.Ry / unit_cell_volume).to("MJ/m3")
    Ku = create_files.compute_Ku(tmp_path)
    assert Ku.value == approx(ref_Ku.value)
    assert Ku.unit == "MJ/m^3"
    assert Ku.ontology_label == "UniaxialAnisotropyConstant"


def test_compute_Ku_force_theorem(tmp_path: Path) -> None:
    (tmp_path / "RSPt/gs_x/").mkdir(parents=True)
    (tmp_path / "RSPt/gs_x/out_last").write_text(
        dedent(
            """
                                    MPI RSPT
            RSPt version number:         rspt.6.0102221136
            ...
            unit cell volume:  700.413751849785
            """
        )
    )

    unit_cell_volume = 700.413751849785 * u.constants.a0**3

    (tmp_path / "RSPt/gs_x/out_MF").write_text(
        dedent(
            """
                        MPI RSPT
            RSPt version number:         rspt.6.0102221136

                    N   =  69.9999999

            Eigenvalue sum: -96.5273077386128
            fermi energy =  9.0250775270253E-01
                    D(ef) =  7.1068566218740E+01
            eigenvalues within   71.9999999 mRy of E Fermi ... 17693
            ...
            Energy Vector
                            Eigenvalue sums
                    Valence : -0.96527307738613E+02          -96.527 307 738 6
                        Core : -0.60192833789239E+04       -6,019.283 378 923 8
                        ...
            """
        )
    )
    (tmp_path / "RSPt/gs_z/").mkdir()
    (tmp_path / "RSPt/gs_z/out_MF").write_text(
        dedent(
            """
                    N   =  69.9999999

            Eigenvalue sum: -96.5273735366564
            fermi energy =  9.0251950380843E-01
                    D(ef) =  7.0569173741673E+01
            """
        )
    )

    ev_x = -96.5273077386128
    ev_z = -96.5273735366564
    ref_Ku = ((ev_x - ev_z) * u.Ry / unit_cell_volume).to("MJ/m3")
    Ku = create_files.compute_Ku(tmp_path)
    assert Ku.value == approx(ref_Ku.value)
    assert Ku.unit == "MJ/m^3"
    assert Ku.ontology_label == "UniaxialAnisotropyConstant"

    # Add y with larger value
    (tmp_path / "RSPt/gs_y/").mkdir()
    (tmp_path / "RSPt/gs_y/out_MF").write_text(
        dedent(
            """
                    N   =  69.9999999

            Eigenvalue sum: -96.5273000000000
            fermi energy =  9.0250712640877E-01
                    D(ef) =  7.1081688783164E+01
            """
        )
    )

    ev_y = -96.5273000000000
    assert ev_x - ev_z < ev_y - ev_z  # ensure yz is larger to confirm we use it
    ref_Ku = ((ev_y - ev_z) * u.Ry / unit_cell_volume).to("MJ/m3")
    Ku = create_files.compute_Ku(tmp_path)
    assert Ku.value == approx(ref_Ku.value)
    assert Ku.unit == "MJ/m^3"
    assert Ku.ontology_label == "UniaxialAnisotropyConstant"

    # Add y with smaller value
    (tmp_path / "RSPt/gs_y/out_MF").write_text(
        dedent(
            """
                    N   =  69.9999999

            Eigenvalue sum: -96.5274000000000
            fermi energy =  9.0250712640877E-01
                    D(ef) =  7.1081688783164E+01
            """
        )
    )

    ev_y = -96.5274000000000
    assert ev_x - ev_z > ev_y - ev_z  # ensure xz is larger to confirm we use it
    ref_Ku = ((ev_x - ev_z) * u.Ry / unit_cell_volume).to("MJ/m3")
    Ku = create_files.compute_Ku(tmp_path)
    assert Ku.value == approx(ref_Ku.value)
    assert Ku.unit == "MJ/m^3"
    assert Ku.ontology_label == "UniaxialAnisotropyConstant"


def test_Tc_Cv_one_peak():
    data = me.EntityCollection(
        T=me.T([10, 20, 30, 40, 50]),
        Cv=me.Entity("IsochoricHeatCapacity", [1, 2, 4, 8, 2]),
    )
    Tc_Cv = create_files._Tc_from_Cv(data, me.Tc(42))
    assert Tc_Cv.ontology_label == "CurieTemperature"
    assert Tc_Cv.value == 40
    assert Tc_Cv.unit == "K"


def test_Tc_Cv_multiple_peaks():
    data = me.EntityCollection(
        T=me.T([10, 20, 30, 40, 50]),
        Cv=me.Entity("IsochoricHeatCapacity", [1, 6, 4, 8, 2]),
    )
    Tc_Cv = create_files._Tc_from_Cv(data, me.Tc(42))
    assert Tc_Cv.ontology_label == "CurieTemperature"
    assert Tc_Cv.value == 40
    assert Tc_Cv.unit == "K"

    # different guess from Kuzmin:
    Tc_Cv = create_files._Tc_from_Cv(data, me.Tc(10))
    assert Tc_Cv.value == 20


def test_Tc_U_L():
    data1 = me.EntityCollection(
        T=me.T([10, 20, 30, 40]),
        U_L=me.Entity("SpontaneousMagnetization", [0.67, 0.67, 0.20, 0.20]),
    )
    data2 = me.EntityCollection(
        T=me.T([10, 20, 30, 40]),
        U_L=me.Entity("SpontaneousMagnetization", [0.66, 0.66, 0.25, 0.25]),
    )
    Tc_U_L = create_files._Tc_from_U_L(data1, data2, me.Tc(22), me.Tc(20))
    assert Tc_U_L.ontology_label == "CurieTemperature"
    assert np.isclose(Tc_U_L.value, 21.666666666666)
    assert Tc_U_L.unit == "K"


def test_Tc_U_L_multi_crossing():
    data1 = me.EntityCollection(
        T=me.T([10, 20, 30, 40, 50, 60]),
        U_L=me.Entity("SpontaneousMagnetization", [0.67, 0.67, 0.20, 0.25, 0.20, 0.25]),
    )
    data2 = me.EntityCollection(
        T=me.T([10, 20, 30, 40, 50, 60]),
        U_L=me.Entity("SpontaneousMagnetization", [0.66, 0.66, 0.25, 0.20, 0.25, 0.20]),
    )
    Tc_U_L = create_files._Tc_from_U_L(data1, data2, me.Tc(22), me.Tc(20))
    assert Tc_U_L.ontology_label == "CurieTemperature"
    assert np.isclose(Tc_U_L.value, 21.666666666)
    assert Tc_U_L.unit == "K"


def test_Tc_U_L_multi_crossing_mismatch():
    data1 = me.EntityCollection(
        T=me.T([10, 20, 30, 40, 50, 60]),
        U_L=me.Entity("SpontaneousMagnetization", [0.67, 0.67, 0.20, 0.25, 0.20, 0.25]),
    )
    data2 = me.EntityCollection(
        T=me.T([10, 20, 30, 40, 50, 60]),
        U_L=me.Entity("SpontaneousMagnetization", [0.66, 0.66, 0.25, 0.20, 0.25, 0.20]),
    )
    with pytest.raises(RuntimeError):
        create_files._Tc_from_U_L(data1, data2, me.Tc(22), me.Tc(40))
