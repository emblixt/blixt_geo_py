from blixt_geo_py import Q_

supported_version = {2.0, 3.0}

allowed_depth_formats = ['md', 'tvd', 'owt', 'twt']  # allowed depth formats
def_water_depth_keys = ['gl', 'egl', 'water_depth', 'wdep']
def_kelly_bushing_keys = ['kb', 'ekb', 'apd', 'edf', 'eref']
def_sonic_units = ['us/f', 'us/ft', 'us/feet',
                   'usec/f', 'usec/ft', 'usec/feet',
                   'us/m', 'usec/m', 's/m']

default_fluids = {
    'brine': dict(rho=Q_(1.02, 'G/cc'), k=Q_(2.56, 'GPa'), mu=Q_(0., 'GPa')), # RokDoc
    'oil': dict(rho=Q_(0.8, 'G/cc'), k=Q_(1.152, 'GPa'), mu=Q_(0., 'GPa')), # RokDoc
    'heavy oil': dict(rho=Q_(1.1, 'G/cc'), k=Q_(2.76, 'GPa'), mu=Q_(0.044, 'GPa')), # RokDoc
    'gas': dict(rho=Q_(0.15, 'G/cc'), k=Q_(0.037, 'GPa'), mu=Q_(0., 'GPa')), # RokDoc
    'condensate': dict(rho=Q_(0.45, 'G/cc'), k=Q_(0.325, 'GPa'), mu=Q_(0., 'GPa')), # RokDoc
    'rich gas': dict(rho=Q_(0.17, 'G/cc'), k=Q_(0.12, 'GPa'), mu=Q_(0., 'GPa')), # Terje
    'biogen gas': dict(rho=Q_(0.01, 'G/cc'), k=Q_(0.08, 'GPa'), mu=Q_(0., 'GPa')) # Terje
}
default_minerals = {
    'quartz': dict(rho=Q_(2.65, 'G/cc'), k=Q_(36.6, 'GPa'), mu=Q_(45., 'GPa')),  # RokDoc
    'shale': dict(rho=Q_(2.63, 'G/cc'), k=Q_(11.4, 'GPa'), mu=Q_(37., 'GPa')),  # RokDoc
    'calcite': dict(rho=Q_(2.71, 'G/cc'), k=Q_(63.7, 'GPa'), mu=Q_(31.7, 'GPa')),  # RokDoc
    'bituminous coal': dict(rho=Q_(1.24, 'G/cc'), k=Q_(4.62, 'GPa'), mu=Q_(2.61, 'GPa')),  # RokDoc
    'shallow silty shale': dict(rho=Q_(1.8, 'G/cc'), k=Q_(4., 'GPa'), mu=Q_(0.8, 'GPa')), # CoPilot
    'shallow silty sand': dict(rho=Q_(1.9, 'G/cc'), k=Q_(5., 'GPa'), mu=Q_(1.5, 'GPa')), # CoPilot
    'silty shale': dict(rho=Q_(2.22, 'G/cc'), k=Q_(12., 'GPa'), mu=Q_(5., 'GPa')), # CoPilot
    'silty sand': dict(rho=Q_(2.17, 'G/cc'), k=Q_(10., 'GPa'), mu=Q_(5.5, 'GPa')), # CoPilot
    'ooze': dict(rho=Q_(1.4, 'G/cc'), k=Q_(2.5, 'GPa'), mu=Q_(0.2, 'GPa'))  # CoPilot, with a big range
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
