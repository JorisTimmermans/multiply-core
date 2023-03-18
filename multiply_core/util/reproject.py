import numpy as np

try:
    import gdal
except ImportError:
    from osgeo import gdal, osr, __version__ as gdalversion


import pyproj
from functools import partial
from shapely.geometry import Polygon
from shapely.ops import transform
from shapely.wkt import dumps, loads
from typing import Optional, Sequence, Tuple, Union

__author__ = "José Luis Gómez-Dans (University College London)," \
             "Tonio Fincke (Brockmann Consult GmbH)"


def reproject_to_wgs84(roi: Union[str, Polygon], roi_grid: str) -> str:
    if roi == '':
        return roi
    if not roi_grid.startswith('EPSG'):
        raise ValueError('ROI grid must be given as EPSG code (e.g., EPSG:4326)')
    if type(roi) is str:
        roi_as_string = roi
        roi_as_polygon = loads(roi)
    else:
        roi_as_string = dumps(roi)
        roi_as_polygon = roi
    if roi_grid == 'EPSG:4326':
        return roi_as_string
    project = partial(
        pyproj.transform,
        pyproj.Proj(init=roi_grid),
        pyproj.Proj(init='EPSG:4326'))
    transformed_roi = transform(project, roi_as_polygon)
    return dumps(transformed_roi)


def transform_coordinates(source: osr.SpatialReference, target: osr.SpatialReference,
                          coords: Sequence[float]) -> Sequence[float]:
    """
    Returns coordinates in a target reference system that have been transformed from coordinates
    in the source reference system.
    :param source: The source spatial reference system
    :param target: The target spatial reference system
    :param coords: The coordinates to be transformed. Coordinates are expected in a sequence
    [x1, y1, x2, y2, ..., xn, yn].
    :return: The transformed coordinates. Will be in a sequence [x1, y1, x2, y2, ..., xn, yn],
    as the source coordinates.
    """
    num_coords = int(len(coords) / 2)
    target_coords = []
    coordinate_transformation = osr.CoordinateTransformation(source, target)
    for i in range(num_coords):
        target_coord = coordinate_transformation.TransformPoint(coords[i * 2], coords[i * 2 + 1])
        if int(gdalversion[0]) >= 3:
            target_coords.append(target_coord[1])
            target_coords.append(target_coord[0])
        else:
            target_coords.append(target_coord[0])
            target_coords.append(target_coord[1])
    return target_coords


def get_spatial_reference_system_from_dataset(dataset: gdal.Dataset) -> osr.SpatialReference:
    """
    Returns the spatial reference system of a dataset
    :param dataset: A dataset
    :return: The spatial reference system of the dataset
    """
    projection = dataset.GetProjection()
    srs = osr.SpatialReference()
    srs.ImportFromWkt(projection)
    return srs


def get_target_resolutions(dataset: gdal.Dataset) -> (float, float):
    """
    Returns the resolution parameters of the geographic transform used by this dataset.
    :param dataset: A dataset
    :return: The resolution parameters of the dataset. The first value refers to the x-axis,
    the second one to the y-axis.
    """
    geo_transform = dataset.GetGeoTransform()
    return geo_transform[1], -geo_transform[5]


def reproject_dataset(dataset: Union[str, gdal.Dataset], bounds: Sequence[float], x_res: int, y_res: int,
                      destination_srs: osr.SpatialReference, bounds_srs: Optional[osr.SpatialReference],
                      resampling_mode: Optional[str]) -> gdal.Dataset:
    """
    Reprojects a gdal dataset to a reference system with the given bounds and the given spatial resolution.
    :param dataset: A dataset
    :param bounds: A 1-d float array specifying the bounds of the resulting dataset. Must consist of the following
    four float values: xmin, ymin, xmax, ymax.
    :param x_res: The resolution the resulting dataset shall have in x-direction. Must be set in accordance to
    destination_srs.
    :param y_res: The resolution the resulting dataset shall have in y-direction. Must be set in accordance to
    destination_srs.
    :param destination_srs: The spatial reference system that the resulting data set shall show.
    :param bounds_srs: The spatial reference system in which the bounds are specified. If not given, it is assumed
    that the bounds are given in the destination_srs.
    :param resampling_mode: The mode by which the values from the source dataset shall be combined to values in the
    target dataset. Available modes are:
    * near (Nearest Neighbour)
    * bilinear
    * cubic
    * cubicspline
    * lanczos
    * average
    * mode
    * max
    * min
    * med
    * q1
    * q3
    If none is selected, 'bilinear' will be selected in case the source values need to be sampled up to a finer
    destination resolution and 'average' in case the values need to be sampled down to a coarser destination resolution.
    :return: A spatial dataset with the chosen destination spatial reference system, in the bounds and the x- and y-
    resolutions that have been set.
    """
    if type(dataset) is str:
        dataset = gdal.Open(dataset)
    if bounds_srs is None:
        bounds_srs = destination_srs
    if resampling_mode is None:
        resampling_mode = _get_resampling(dataset, bounds, x_res, y_res, bounds_srs, destination_srs)
    warp_options = gdal.WarpOptions(format='Mem', outputBounds=bounds, outputBoundsSRS=bounds_srs,
                                    xRes=x_res, yRes=y_res, dstSRS=destination_srs, resampleAlg=resampling_mode)
    reprojected_data_set = gdal.Warp('', dataset, options=warp_options)
    return reprojected_data_set


def _get_resampling(dataset: gdal.Dataset, bounds: Sequence[float], x_res: float, y_res: float,
                    bounds_srs: osr.SpatialReference, destination_srs: osr.SpatialReference) -> str:
    if _need_to_sample_up(dataset, bounds, x_res, y_res, bounds_srs, destination_srs):
        return 'bilinear'
    else:
        return 'average'


def _need_to_sample_up(dataset: gdal.Dataset, bounds: Sequence[float], x_res: float, y_res: float,
                       bounds_srs: osr.SpatialReference, destination_srs: osr.SpatialReference) -> bool:
    source_srs = get_spatial_reference_system_from_dataset(dataset)
    bounds_in_source_coordinates = transform_coordinates(bounds_srs, source_srs, bounds)
    source_resolutions = get_target_resolutions(dataset)
    source_resolution_measure = _get_dist_measure(bounds_in_source_coordinates,
                                                  source_resolutions[0], source_resolutions[1])
    bounds_in_dest_coordinates = transform_coordinates(bounds_srs, destination_srs, bounds)
    dest_resolution_measure = _get_dist_measure(bounds_in_dest_coordinates, x_res, y_res)
    return dest_resolution_measure > source_resolution_measure


def _get_dist_measure(source_coordinates: Sequence[float], x_res: float, y_res: float):
    # this method is not suited for computing actual geographic distances! It only serves to determine the coarse
    # distance between points
    x_dist = np.sqrt(np.square(source_coordinates[0] - source_coordinates[2]))
    y_dist = np.sqrt(np.square(source_coordinates[1] - source_coordinates[3]))
    return (x_dist / x_res) * (y_dist / y_res)


class Reprojection(object):

    def __init__(self, bounds: Sequence[float], x_res: int, y_res: int, destination_srs: osr.SpatialReference,
                 bounds_srs: Optional[osr.SpatialReference]=None, resampling_mode: Optional[str]=None):
        self._bounds = bounds
        self._x_res = x_res
        self._y_res = y_res
        self._destination_srs = destination_srs
        self._resampling_mode = resampling_mode
        if bounds_srs is None:
            self._bounds_srs = destination_srs
        else:
            self._bounds_srs = bounds_srs

    def reproject(self, dataset: Union[str, gdal.Dataset]) -> gdal.Dataset:
        if type(dataset) is str:
            dataset = gdal.Open(dataset)
        if self._resampling_mode is None:
            resampling_mode = _get_resampling(dataset, self._bounds, self._x_res, self._y_res, self._bounds_srs,
                                              self._destination_srs)
        else:
            resampling_mode = self._resampling_mode
        warp_options = gdal.WarpOptions(format='Mem', outputBounds=self._bounds, outputBoundsSRS=self._bounds_srs,
                                        xRes=self._x_res, yRes=self._y_res, dstSRS=self._destination_srs,
                                        resampleAlg=resampling_mode)
        reprojected_data_set = gdal.Warp('', dataset, options=warp_options)
        return reprojected_data_set

    def get_destination_srs(self) -> osr.SpatialReference:
        return self._destination_srs


def reproject_image(source_img, target_img, dstSRSs=None):
    # TODO: replace this method with the other functionality in this module
    """Reprojects/Warps an image to fit exactly another image.
    Additionally, you can set the destination SRS if you want
    to or if it isn't defined in the source image."""
    if type(target_img) is str:
        g = gdal.Open(target_img)
    else:
        g = target_img
    if type(source_img) is str:
        s = gdal.Open(source_img)
    else:
        s = source_img
    geo_t = g.GetGeoTransform()
    x_size, y_size = g.RasterXSize, g.RasterYSize
    xmin = min(geo_t[0], geo_t[0] + x_size * geo_t[1])
    xmax = max(geo_t[0], geo_t[0] + x_size * geo_t[1])
    ymin = min(geo_t[3], geo_t[3] + y_size * geo_t[5])
    ymax = max(geo_t[3], geo_t[3] + y_size * geo_t[5])
    xRes, yRes = abs(geo_t[1]), abs(geo_t[5])
    if dstSRSs is None:
        dstSRS = osr.SpatialReference()
        raster_wkt = g.GetProjection()
        dstSRS.ImportFromWkt(raster_wkt)
    else:
        dstSRS = dstSRSs
    g = gdal.Warp('', s, format='MEM', outputBounds=[xmin, ymin, xmax, ymax], xRes=xRes, yRes=yRes, dstSRS=dstSRS)
    return g


def _get_reference_system(wkt: str) -> Optional[osr.SpatialReference]:
    if wkt is None:
        return None
    spatial_reference = osr.SpatialReference()
    if wkt.startswith('EPSG:'):
        epsg_code = int(wkt.split(':')[1])
        spatial_reference.ImportFromEPSG(epsg_code)
    else:
        spatial_reference.ImportFromWkt(wkt)
    return spatial_reference


def _get_projected_srs(roi_center):
    utm_zone = int(1 + (roi_center.coords[0][0] + 180.0) / 6.0)
    is_northern = int(roi_center.coords[0][1] > 0.0)
    spatial_reference_system = osr.SpatialReference()
    spatial_reference_system.SetWellKnownGeogCS('WGS84')
    spatial_reference_system.SetUTM(utm_zone, is_northern)
    return spatial_reference_system


def _get_default_global_state_mask():
    driver = gdal.GetDriverByName('MEM')
    dataset = driver.Create('', 360, 90, bands=1)
    dataset.SetGeoTransform((-180.0, 1.00, 0.0, 90.0, 0.0, -1.00))
    srs = osr.SpatialReference()
    srs.SetWellKnownGeogCS("WGS84")
    dataset.SetProjection(srs.ExportToWkt())
    dataset.GetRasterBand(1).WriteArray(np.ones((90, 360)))
    return dataset


def get_mask_data_set_and_reprojection(state_mask: Optional[str] = None, spatial_resolution: Optional[int] = None,
                                        roi: Optional[Union[str, Polygon]] = None, roi_grid: Optional[str] = None,
                                        destination_grid: Optional[str] = None):
    if roi is not None and spatial_resolution is not None:
        if type(roi) is str:
            roi = loads(roi)
        roi_bounds = roi.bounds
        roi_center = roi.centroid
        roi_srs = _get_reference_system(roi_grid)
        destination_srs = _get_reference_system(destination_grid)
        wgs84_srs = _get_reference_system('EPSG:4326')
        if roi_srs is None:
            if destination_srs is None:
                roi_srs = wgs84_srs
                destination_srs = _get_projected_srs(roi_center)
            else:
                roi_srs = destination_srs
        elif destination_srs is None:
            if roi_srs.IsSame(wgs84_srs):
                destination_srs = _get_projected_srs(roi_center)
            else:
                raise ValueError('Cannot derive destination grid for roi grid {}. Please specify destination grid'.
                                 format(roi_grid))
        if state_mask is not None:
            mask_data_set = gdal.Open(state_mask)
        else:
            mask_data_set = _get_default_global_state_mask()
        reprojection = Reprojection(roi_bounds, spatial_resolution, spatial_resolution, destination_srs, roi_srs)
        reprojected_dataset = reprojection.reproject(mask_data_set)
        return reprojected_dataset, reprojection
    elif state_mask is not None:
        state_mask_data_set = gdal.Open(state_mask)
        geo_transform = state_mask_data_set.GetGeoTransform()
        ulx, xres, xskew, uly, yskew, yres = geo_transform
        lrx = ulx + (state_mask_data_set.RasterXSize * xres)
        lry = uly + (state_mask_data_set.RasterYSize * yres)
        roi_bounds = (min(ulx, lrx), min(uly, lry), max(ulx, lrx), max(uly, lry))
        destination_spatial_reference_system = osr.SpatialReference()
        projection = state_mask_data_set.GetProjection()
        destination_spatial_reference_system.ImportFromWkt(projection)
        reprojection = Reprojection(roi_bounds, xres, yres, destination_spatial_reference_system)
        return state_mask_data_set, reprojection
    else:
        raise ValueError("Either state mask or roi and spatial resolution must be given")


def get_num_tiles(state_mask: Optional[str] = None, spatial_resolution: Optional[int] = None,
                  roi: Optional[Union[str, Polygon]] = None, roi_grid: Optional[str] = None,
                  destination_grid: Optional[str] = None, tile_width: Optional[int] = None,
                  tile_height: Optional[int] = None) -> Tuple:
    mask_data_set, untiled_reprojection = get_mask_data_set_and_reprojection(state_mask, spatial_resolution, roi,
                                                                              roi_grid, destination_grid)
    raster_width = mask_data_set.RasterXSize
    raster_height = mask_data_set.RasterYSize
    return (int(np.ceil(raster_width / tile_width)), int(np.ceil(raster_height / tile_height)))
