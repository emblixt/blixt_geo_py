from blixt_geo_py import Q_

supported_version = {2.0, 3.0}

allowed_depth_formats = ['md', 'tvd', 'owt', 'twt']  # allowed depth formats
def_water_depth_keys = ['gl', 'egl', 'water_depth', 'wdep']
def_kelly_bushing_keys = ['kb', 'ekb', 'apd', 'edf', 'eref']
def_sonic_units = ['us/f', 'us/ft', 'us/feet',
                   'usec/f', 'usec/ft', 'usec/feet',
                   'us/m', 'usec/m', 's/m']

default_fluids = {
    'brine': dict(rho=Q_(1.02, 'G/cc'), k=Q_(2.56, 'GPa')),
    'oil': dict(rho=Q_(0.8, 'G/cc'), k=Q_(1.15, 'GPa')),
    'heavy oil': dict(rho=Q_(1.1, 'G/cc'), k=Q_(2.76, 'GPa')),
    'rich gas': dict(rho=Q_(0.17, 'G/cc'), k=Q_(0.12, 'GPa')),
    'biogen gas': dict(rho=Q_(0.01, 'G/cc'), k=Q_(0.08, 'GPa'))
}
default_minerals = {
    'quartz': dict(rho=Q_(2.6, 'G/cc'), k=Q_(36.6, 'GPa'), mu=Q_(31., 'GPa')),
    'shale': dict(rho=Q_(2.35, 'G/cc'), k=Q_(11.4, 'GPa'), mu=Q_(3., 'GPa')),
    'calcite': dict(rho=Q_(2.71, 'G/cc'), k=Q_(76.8, 'GPa'), mu=Q_(32., 'GPa')),
    'ooze': dict(rho=Q_(1.8, 'G/cc'), k=Q_(5.5, 'GPa'), mu=Q_(2.3, 'GPa'))
}


rename_well_logs = {
    # depth, or MD
    'depth': ['Depth', 'DEPT', 'MD', 'DEPTH'],

    # Bulk density
    'den': ['RHOB', 'HRHOB', 'DEN', 'HDEN', 'RHO', 'CPI:RHOB', 'HRHO'],

    # Density correction
    'denc': ['HDRHO', 'DENC', 'DCOR'],

    # Sonic
    'ac': ['HDT', 'DT', 'CPI:DT', 'HAC', 'AC'],

    # Shear sonic
    'acs': ['ACS'],

    # Gamma ray
    'gr': ['HGR', 'GR', 'CPI:GR'],

    # Caliper
    'cali': ['HCALI', 'CALI', 'HCAL'],

    # Deep resistivity
    'rdep': ['HRD', 'RDEP', 'ILD', 'RD'],

    # Medium resistivity
    'rmed': ['HRM', 'RMED', 'RM'],

    # Shallow resistivity
    'rsha': ['RS', 'RSHA', 'HRS'],

    # Water saturation
    'sw': ['CPI:SW', 'SW'],

    # Effective porosity
    'phie': ['CPI:PHIE', 'PHIE'],

    # Neutron porosity
    'neu': ['HNPHI', 'NEU', 'CPI:NPHI', 'HPHI'],

    # Shale volume
    'vcl': ['VCLGR', 'VCL', 'CPI:VWCL', 'CPI:VCL']
}


def gr_cmap():
    """
    Creates a useful colormap (color map) for plotting gamma ray logs
    """
    from matplotlib.colors import ListedColormap
    import numpy as np
    N = 256
    vals = np.ones((N, 4))
    vals[:, 0] = np.linspace(1, 0 / 256, N)
    vals[:, 1] = np.linspace(1, 85 / 256, N)
    vals[:, 2] = np.linspace(0, 0 / 256, N)
    return ListedColormap(vals)
