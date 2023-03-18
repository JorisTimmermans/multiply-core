try:
    import gdal
except ImportError:
    from osgeo import gdal


if __name__ == "__main__":
    print('kkkk')
    read_data = gdal.Open('file_name')