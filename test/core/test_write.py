import os

try:
    import gdal
    import osr
except ImportError:
    from osgeo import gdal, osr

__author__ = "Tonio Fincke (Brockmann Consult GmbH)"

if os.path.exists('test'):
    base_path = 'test/test/test_data/'
elif os.path.exists('util'):
    base_path = '../test/test_data/'

S2_FILE = base_path + 'T32UME_20170910T104021_B10.jp2'
# S2_TIFF_FILE = base_path + 'T32UME_20170910T104021_B10.tiff'
# LAI_TIFF_FILE = base_path + 'Priors_lai_125_[50_60N]_[000_010E].tiff'
ALA_TIFF_FILE = base_path + 'Priors_ala_125_[50_60N]_[000_010E].tiff'
# GLOBAL_VRT_FILE = base_path + 'Priors_lai_060_global.vrt'
