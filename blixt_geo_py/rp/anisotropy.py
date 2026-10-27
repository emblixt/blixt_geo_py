"""
Anisotropy effects.

Backus anisotropy is from thin layers.

Copied from the bruges library (bruges/rockphysics/anisotropy.py and bruges/util/util.py, v0.5.4)
https://github.com/agile-geoscience/bruges
to avoid depending on bruges, which is no longer maintained. See third_party/BRUGES_LICENSE.txt

:copyright: 2015 Agile Geoscience
:license: Apache 2.0
"""
from collections import namedtuple

import numpy as np

from blixt_geo_py.rp import moduli


def moving_average(a, length, mode='same'):
    """
    Computes the mean in a moving window using convolution. For an alternative,
    as well as other kinds of average (median, mode, etc.), see bruges.filters.

    Example:
        >>> test = np.array([1,1,9,9,9,9,9,2,3,9,2,2,np.nan,1,1,1,1])
        >>> moving_average(test, 5, mode='same')
        array([ 2.2,  4. ,  5.8,  7.4,  9. ,  7.6,  6.4,  6.4,  5. ,  3.6,  nan,
                nan,  nan,  nan,  nan,  0.8,  0.6])
    """
    padded = np.pad(a, int(length/2), mode='edge')
    boxcar = np.ones(int(length))/length
    smooth = np.convolve(padded, boxcar, mode='same')
    return smooth[int(length/2):-int(length/2)]


def backus_parameters(vp, vs, rho, lb, dz):
    """
    Intermediate parameters for Backus averaging. This is expected to be a
    private function. You probably want backus() and not this.

    Args:
        vp (ndarray): P-wave interval velocity.
        vs (ndarray): S-wave interval velocity.
        rho (ndarray): Bulk density.
        lb (float): The Backus averaging length in m.
        dz (float): The depth sample interval in m.

    Returns:
        tuple: Liner's 5 intermediate parameters: A, C, F, L and M.

    Notes:
        Liner, C (2014), Long-wave elastic attenuation produced by horizontal
        layering. The Leading Edge, June 2014, p 634-638.

    """
    lam = moduli.lam(vp, vs, rho)
    mu = moduli.mu(vp, vs, rho)

    # Compute the layer parameters from Liner (2014) equation 2:
    a = rho * np.power(vp, 2.0)  # Acoustic impedance

    # Compute the Backus parameters from Liner (2014) equation 4:
    A1 = 4 * moving_average(mu*(lam+mu)/a, lb/dz, mode='same')
    A = A1 + np.power(moving_average(lam/a, lb/dz, mode='same'), 2.0)\
        / moving_average(1.0/a, lb/dz, mode='same')
    C = 1.0 / moving_average(1.0/a, lb/dz, mode='same')
    F = moving_average(lam/a, lb/dz, mode='same')\
        / moving_average(1.0/a, lb/dz, mode='same')
    L = 1.0 / moving_average(1.0/mu, lb/dz, mode='same')
    M = moving_average(mu, lb/dz, mode='same')

    BackusResult = namedtuple('BackusResult', ['A', 'C', 'F', 'L', 'M'])
    return BackusResult(A, C, F, L, M)


def backus(vp, vs, rho, lb, dz):
    """
    Backus averaging. Using Liner's algorithm (2014; see Notes).

    Args:
        vp (ndarray): P-wave interval velocity.
        vs (ndarray): S-wave interval velocity.
        rho (ndarray): Bulk density.
        lb (float): The Backus averaging length in m.
        dz (float): The depth sample interval in m.

    Returns:
        namedtuple: the smoothed logs: vp, vs, plus rho. Useful for computing
            other elastic parameters at a seismic scale.

    Notes:
        Liner, C (2014), Long-wave elastic attenuation produced by horizontal
        layering. The Leading Edge, June 2014, p 634-638.

    """
    # Compute the Backus parameters:
    A, C, F, L, M = backus_parameters(vp, vs, rho, lb, dz)

    # Compute the vertical velocities from Liner (2014) equation 5:
    R = moving_average(rho, lb/dz, mode='same')
    vp0 = np.sqrt(C / R)
    vs0 = np.sqrt(L / R)

    BackusResult = namedtuple('BackusResult', ['Vp', 'Vs', 'rho'])
    return BackusResult(Vp=vp0, Vs=vs0, rho=R)
