import os

try:
    import gdal
    import osr
except ImportError:
    from osgeo import gdal, osr


import urllib.request
import zipfile

__author__ = "Tonio Fincke (Brockmann Consult GmbH)"

test_data_save_path = '/tmp/test_data.zip'
if not os.path.exists(test_data_save_path):
    urllib.request.urlretrieve('https://github.com/QCDIS/multiply-core/raw/master/test/test_data.zip', test_data_save_path)
    with zipfile.ZipFile(test_data_save_path, 'r') as zip_ref:
        zip_ref.extractall('/tmp')
    zip_ref.close()
base_path = '/tmp/test_data/'

S2_FILE = base_path + 'T32UME_20170910T104021_B10.jp2'
# S2_TIFF_FILE = base_path + 'T32UME_20170910T104021_B10.tiff'
# LAI_TIFF_FILE = base_path + 'Priors_lai_125_[50_60N]_[000_010E].tiff'
ALA_TIFF_FILE = base_path + 'Priors_ala_125_[50_60N]_[000_010E].tiff'
# GLOBAL_VRT_FILE = base_path + 'Priors_lai_060_global.vrt'
