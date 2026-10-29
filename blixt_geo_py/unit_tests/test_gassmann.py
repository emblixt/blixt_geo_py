import unittest

import numpy as np

import blixt_geo_py.rp.rp_core as rp
import blixt_geo_py.rp.moduli as moduli


def avseth_gassmann(ksat1, kf1, kf2, kmin, phi):
    """
    From:
    https://github.com/agile-geoscience/bruges/blob/master/bruges/rockphysics/fluidsub.py
    Applies the Gassmann equation.
    Args:
        ksat1 (float): Ksat1.
        kf1 (float): Kfluid1.
        kf2 (float): Kfluid2.
        kmin (float): Kmineral.
        phi (float): Porosity.
    Returns:
        float: Ksat2.
    """

    s = ksat1 / (kmin - ksat1)
    f1 = kf1 / (phi * (kmin - kf1))
    f2 = kf2 / (phi * (kmin - kf2))

    ksat2 = kmin / ((1/(s - f1 + f2)) + 1)

    return ksat2


def avseth_fluidsub(vp, vs, rho, phi, rhof1, rhof2, kmin, kf1, kf2):
    """
    From:
    https://github.com/agile-geoscience/bruges/blob/master/bruges/rockphysics/fluidsub.py

    Naive fluid substitution from Avseth et al. No pressure/temperature
    correction. Only works for SI units right now.
    Args:
        vp (float): P-wave velocity
        vs (float): S-wave velocity
        rho (float): bulk density
        phi (float): porosity (i.e. 0.20)
        rhof1 (float): bulk density of original fluid (base case)
        rhof2 (float): bulk density of substitute fluid (subbed case)
        kmin (float): bulk modulus of solid mineral(s)
        kf1 (float): bulk modulus of original fluid
        kf2 (float): bulk modulus of substitue fluid
    Returns:
        Tuple: Vp, Vs, and rho for the substituted case
    """

    # Step 1: Extract the dynamic bulk and shear moduli
    ksat1 = moduli.bulk(vp=vp, vs=vs, rho=rho)
    musat1 = moduli.mu(vp=vp, vs=vs, rho=rho)

    # Step 2: Apply Gassmann's relation
    ksat2 = avseth_gassmann(ksat1=ksat1, kf1=kf1, kf2=kf2, kmin=kmin, phi=phi)

    # Step 3: Leave the shear modulus unchanged
    musat2 = musat1

    # Step 4: Correct the bulk density for the change in fluid
    rho2 = rho + phi * (rhof2 - rhof1)

    # Step 5: recompute the fluid substituted velocities
    vp2 = moduli.vp(bulk=ksat2, mu=musat2, rho=rho2)
    vs2 = moduli.vs(mu=musat2, rho=rho2)

    return vp2, vs2, rho2


def create_test_data(l, vp1, vp_vs, rho, k0, kf1, rhof1, kf2, rhof2, por):
    _vp1 = vp1*np.ones(l)
    _vs1 = _vp1/vp_vs
    _rho1 = rho*np.ones(l)
    _k0 = k0*np.ones(l)
    _kf1 = kf1*np.ones(l)
    _rhof1 = rhof1*np.ones(l)
    _kf2 = kf2*np.ones(l)
    _rhof2 = rhof2*np.ones(l)
    _por = por*np.ones(l)
    return _vp1, _vs1, _rho1, _k0, _kf1, _rhof1, _kf2, _rhof2, _por

class GMTest(unittest.TestCase):
    length = 10
    vp_const = 2000.  # m/s
    vp_vs = 2.
    rho_const = 2.5  # g/cm3
    k0 = 10
    k_f1 = 3  # Brine
    rho_f1 = 1.
    k_f2 = 1  # Oil
    rho_f2 = 0.7
    por = 0.2

    def test_simple_fs(self):
        vp1, vs1, rho1, k0, kf1, rhof1, kf2, rhof2, por = create_test_data(
            GMTest.length,
            GMTest.vp_const,
            GMTest.vp_vs,
            GMTest.rho_const,
            GMTest.k0,
            GMTest.k_f1,
            GMTest.rho_f1,
            GMTest.k_f2,
            GMTest.rho_f2,
            GMTest.por
        )

        mu1 = rho1 * vs1 ** 2 * 1E-6  # GPa
        k1 = rho1 * vp1 ** 2 * 1E-6 - (4 / 3.) * mu1  # GPa
        print(vp1[0], vs1[0], rho1[0], k0[0], kf1[0], kf2[0], por[0])

        # Calculate the fluid saturated bulk modulus for the final fluids using
        a = rp.gassmann_a(k1, k0, kf1, kf2, por)
        k2 = k0*a / (1. + a)

        # The calculation should be ok if the two sides (t1 and t2) of the Gassmann fluid subsitution
        # recipe in Avseth et al. 2011 (p. 18) is the same
        t1 = k2 / (k0 - k2) - kf2/(por*(k0 - kf2))
        t2 = k1 / (k0 - k1) - kf1/(por*(k0 - kf1))
        max_diff = max(abs(t1-t2))
        with self.subTest():
            print('Evaluate equation on p. 18: {} = {}'.format(t1[0], t2[0]))
            self.assertLess(max_diff, 1E-12)

        # Compare the k2 with the one calculated using Agile Geoscience Bruges library
        ksat2 = avseth_gassmann(k1*1E9, kf1*1E9, kf2*1E9, k0*1E9, por)
        max_diff = max(abs(ksat2*1E-9 - k2))
        with self.subTest():
            print('Evaluate how k2 is calculated: {} = {}'.format(k2[0], ksat2[0]*1E-9))
            self.assertLess(max_diff, 1E-12)

        # Compute final elastic properties keeping mu unchanged
        rho2 = rho1 + por*(rhof2 - rhof1)  # g/cm3
        vp2 = np.sqrt((k2+4.*mu1/3.) / rho2) * 1E3  # m/s
        vs2 = np.sqrt(mu1 / rho2) * 1E3  # m/s

        # Compute final elastic propertis using Agile Geoscience Bruges library
        vp22, vs22, rho22 = avseth_fluidsub(vp1, vs1, rho1*1000., por, rhof1*1000., rhof2*1000., k0*1E9, kf1*1E9, kf2*1E9)

        print('Evaluate difference between elastic properties calculated directly and via Bruges:')
        print(' Vp; {} : {}'.format(vp2[0], vp22[0]))
        with self.subTest():
            max_diff = max(abs(vp2 - vp22))
            self.assertLess(max_diff, 1E-3)

        print(' Vs; {} : {}'.format(vs2[0], vs22[0]))
        with self.subTest():
            max_diff = max(abs(vs2 - vs22))
            self.assertLess(max_diff, 1E-3)

        print(' rho; {} : {}'.format(rho2[0], rho22[0]/1000.))
        with self.subTest():
            max_diff = max(abs(rho2 - rho22/1000.))
            self.assertLess(max_diff, 1E-3)
