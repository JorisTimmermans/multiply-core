from osgeo.gdal import BuildVRT, Dataset, Open
import _pickle as cPickle
import glob
import logging
import os
import numpy as np
import scipy.sparse as sp
import xml.etree.ElementTree as eT

from multiply_core.observations import ProductObservations, ObservationData, ProductObservationsCreator, \
    data_validation
from multiply_core.util import FileRef, Reprojection, get_aux_data_provider
from typing import List, Optional, Tuple, Union

__author__ = "Tonio Fincke (Brockmann Consult GmbH)"

# todo exchange this
EMULATOR_BAND_MAP = [2, 3, 4, 5, 6, 7, 8, 9, 12, 13]
BAND_NAMES = ['B02_sur.tif', 'B03_sur.tif', 'B04_sur.tif', 'B05_sur.tif', 'B06_sur.tif', 'B07_sur.tif',
              'B08_sur.tif', 'B8A_sur.tif', 'B09_sur.tif', 'B12_sur.tif', 'B01_sur.tif', 'B10_sur.tif', 'B11_sur.tif']
NO_DATA_VALUES = [0.0] * len(BAND_NAMES)
BAND_PROB_THRESHOLD = 5
CLOUD_MASK_NAME = 'cloud.tif'
SUN_ANGLES_NAME = 'SAA_SZA.tif'
VIEW_ANGLES_NAME = 'VAA_VZA_B05.tif'


LOG = logging.getLogger(__name__ + ".Sentinel2_Observations")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - ' +
                                  '%(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    LOG.addHandler(ch)
LOG.propagate = False


def _get_xml_root(xml_file_name: str):
    tree = eT.parse(xml_file_name)
    return tree.getroot()


def extract_angles_from_metadata_file(filename: str) -> Tuple[float, float, float, float]:
    """Parses the XML metadata file to extract view/incidence
    angles. The file has grids and all sorts of stuff, but
    here we just average everything, and you get
    1. SZA
    2. SAA
    3. VZA
    4. VAA.
    """
    root = _get_xml_root(filename)
    sza = 0.
    saa = 0.
    vza = []
    vaa = []
    for child in root:
        for x in child.findall("Tile_Angles"):
            for y in x.find("Mean_Sun_Angle"):
                if y.tag == "ZENITH_ANGLE":
                    sza = float(y.text)
                elif y.tag == "AZIMUTH_ANGLE":
                    saa = float(y.text)
            for s in x.find("Mean_Viewing_Incidence_Angle_List"):
                for r in s:
                    if r.tag == "ZENITH_ANGLE":
                        vza.append(float(r.text))
                    elif r.tag == "AZIMUTH_ANGLE":
                            vaa.append(float(r.text))

    return sza, saa, float(np.mean(vza)), float(np.mean(vaa))


def extract_tile_id(filename: str) -> str:
    """Parses the XML metadata file to extract the tile id."""
    root = _get_xml_root(filename)
    for child in root:
        for x in child.findall("TILE_ID"):
            return x.text


def _get_uncertainty(rho_surface: np.array, mask: np.array) -> sp.lil_matrix:
    r_mat = rho_surface * 0.05
    r_mat[np.logical_not(mask)] = 0.
    n = mask.ravel().shape[0]
    r_mat_sp = sp.lil_matrix((n, n))
    r_mat_sp.setdiag(1. / (r_mat.ravel()) ** 2)
    return r_mat_sp.tocsr()


def _prepare_band_emulators(emulator_folder: str, sza: float, saa: float, vza: float, vaa: float):
    aux_data_provider = get_aux_data_provider()
    emulator_files = aux_data_provider.list_elements(emulator_folder, "*_[0-9]*_[0-9]*_[0-9]*.pkl")
    if len(emulator_files) == 0:
        return None
    emulator_files.sort()
    raa = np.abs(vaa - saa)
    vzas = np.array([float(s.split("_")[-3])
                     for s in emulator_files])
    szas = np.array([float(s.split("_")[-2])
                     for s in emulator_files])
    raas = np.array([float(s.split("_")[-1].split(".")[0])
                     for s in emulator_files])
    e1 = szas == szas[np.argmin(np.abs(szas - sza))]
    e2 = vzas == vzas[np.argmin(np.abs(vzas - vza))]
    e3 = raas == raas[np.argmin(np.abs(raas - raa))]
    iloc = np.where(e1 * e2 * e3)[0][0]
    emulator_file = emulator_files[iloc]
    aux_data_provider.assure_element_provided(emulator_file)
    return cPickle.load(open(emulator_file, 'rb'), encoding='latin1')


class S2Observations(ProductObservations):

    def __init__(self, file_refs: List[FileRef], reprojection: Optional[Reprojection], emulator_folder: Optional[str]):
        self._file_refs = file_refs
        self._reprojection = reprojection
        # we assume that all file refs are of the same type
        self._data_type = data_validation.get_valid_type(file_refs[0].url)
        file_szas = np.empty(shape=len(self._file_refs), dtype=np.float32)
        file_saas = np.empty(shape=len(self._file_refs), dtype=np.float32)
        file_vzas = np.empty(shape=len(self._file_refs), dtype=np.float32)
        file_vaas = np.empty(shape=len(self._file_refs), dtype=np.float32)
        for i, file_ref in enumerate(file_refs):
            meta_data_file = self._get_metadata_file(file_ref.url)
            file_szas[i], file_saas[i], file_vzas[i], file_vaas[i] = extract_angles_from_metadata_file(meta_data_file)
        self._meta_data_infos = dict(zip(["sza", "saa", "vza", "vaa"], [float(np.mean(file_szas)),
                                                                        float(np.mean(file_saas)),
                                                                        float(np.mean(file_vzas)),
                                                                        float(np.mean(file_vaas))]))
        self._band_emulators = None
        if emulator_folder is not None:
            self._band_emulators = _prepare_band_emulators(emulator_folder,
                                                           float(np.mean(file_szas)), float(np.mean(file_saas)),
                                                           float(np.mean(file_vzas)), float(np.mean(file_vaas)))
        # todo this is not correct! This is not the number of observations but the number of observations for which
        # emulators are available! revise this by setting up an emulator description
        self._bands_per_observation = len(EMULATOR_BAND_MAP)
        self._no_data_values = NO_DATA_VALUES

    def _get_metadata_file(self, url: str):
        metadata_file_names = ["metadata.xml", "MTD_TL.xml"]
        for metadata_file_name in metadata_file_names:
            candidate_file = os.path.join(url, metadata_file_name)
            if os.path.exists(candidate_file):
                return candidate_file
        raise ValueError(f'No valid metadata file found at {url}')

    def _get_raw_band_data(self, band_index: int) -> np.array:
        if band_index > len(BAND_NAMES):
            raise ValueError(f'Invalid band index: {band_index} > {len(BAND_NAMES)}')
        return self._get_raw_band_data_from_name(BAND_NAMES[band_index])

    def _get_raw_band_data_from_name(self, band_name: str) -> np.array:
        data_set = self._get_raw_data_set_from_name(band_name)
        if self._reprojection is not None:
                data_set = self._reprojection.reproject(data_set)
        return data_set.ReadAsArray()

    def _get_raw_data_set_from_name(self, band_name: str) -> Dataset:
        #import pdb
        #pdb_set_trace()
        if len(self._file_refs) > 1:
            data_set_base_url = self._file_refs[0].url
            relative_path = data_validation.get_relative_path(data_set_base_url, self._data_type)
            vrt_file_name = data_set_base_url.replace(relative_path, f"/{band_name.split('.')[0]}.vrt")
            if relative_path=='':
                vrt_file_name = '/'.join(data_set_base_url.split('/')[:-1]) + '/'+ band_name.split('.')[0]+'.vrt'

            if not os.path.exists(vrt_file_name):
                data_set_base_urls = []
                for file_ref in self._file_refs:
                    data_set_urls = glob.glob('{}/*{}*'.format(file_ref.url, band_name))
                    if len(data_set_urls) > 0:
                        data_set_base_urls.append(data_set_urls[0])
                if len(data_set_base_urls) == 0:
                    raise ValueError(f'Could not find band {band_name}')
                vrt_data_set = BuildVRT(vrt_file_name, data_set_base_urls)
                vrt_data_set.FlushCache()
            return Open(vrt_file_name)
        else:
            data_set_base_url = self._file_refs[0].url
            data_set_urls = glob.glob('{}/*{}*'.format(data_set_base_url, band_name))
            if len(data_set_urls) == 0:
                raise ValueError(f'Could not find band {band_name}')
            return Open(data_set_urls[0])

    def get_band_data_by_name(self, band_name: str, retrieve_uncertainty: bool = True) -> ObservationData:
        for i, base_band_name in enumerate(BAND_NAMES):
            if base_band_name in band_name:
                return self.get_band_data(i, retrieve_uncertainty)

    def get_band_data(self, band_index: int, retrieve_uncertainty: bool = True) -> ObservationData:
        data = self._get_raw_band_data(band_index)
        mask = data > 0
        data = np.where(mask, data / 10000., self._no_data_values[band_index])

        if retrieve_uncertainty:
            uncertainty = _get_uncertainty(data, mask)
        else:
            uncertainty = None
        band_emulator = self._get_band_emulator(band_index)

        observation_data = ObservationData(observations=data, uncertainty=uncertainty, mask=mask,
                                           metadata=self._meta_data_infos, emulator=band_emulator)
        return observation_data

    def _get_band_emulator(self, band_index: int):
        if self._band_emulators is not None:
            s2_band = bytes("S2A_MSI_{:02d}".format(EMULATOR_BAND_MAP[band_index]), 'latin1')
            return self._band_emulators[s2_band]
        return None

    @property
    def bands_per_observation(self) -> int:
        return self._bands_per_observation

    @property
    def data_type(self) -> str:
        return self._data_type

    def set_no_data_value(self, band: Union[str, int], no_data_value: float):
        if type(band) is str:
            band = BAND_NAMES.index(band)
        self._no_data_values[band] = no_data_value

    def read_granule(self) -> (List[np.array], np.array, np.float, np.float, np.float, List[np.array]):
        band_map = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12']
        cloud_mask = self._get_raw_band_data_from_name(CLOUD_MASK_NAME)
        mask = cloud_mask <= BAND_PROB_THRESHOLD
        if mask.sum() == 0:
            return None, None, None, None, None, None
        rho_surface = []
        rho_unc = []
        for band in band_map:
            rho = self._get_raw_band_data_from_name(f'{band}_sur.tif')
            rho_surface.append(rho)
            # rho_unc.append(self._get_raw_band_data_from_name(f'{band}_sur_unc.tif'))
            rho_unc.append(np.ones_like(rho) * 0.005)

        rho_surface = np.array(rho_surface) / 10000.0
        rho_unc = np.array(rho_unc) / 10000.0

        # Ensure all surface reflectance pixels have values above 0 & aren't cloudy.
        sel_bands = np.array([1, 2, 3, 4, 5, 6, 7, 8])
        mask = np.logical_and(
            np.all(rho_surface[sel_bands] > 0, axis=0), mask
        )
        if mask.sum() == 0:
            return None, None, None, None, None, None
        rho_unc[:, ~mask] = np.nan
        rho_unc = np.nanmean(rho_unc, axis=(1, 2))
        rho_surface[:, ~mask] = np.nan

        sun_angles = self._get_raw_band_data_from_name(SUN_ANGLES_NAME)
        view_angles = self._get_raw_band_data_from_name(VIEW_ANGLES_NAME)
        sza = np.cos(np.deg2rad(sun_angles[1].mean() / 100.0))
        vza = np.cos(np.deg2rad(view_angles[1].mean() / 100.0))
        saa = sun_angles[0].mean() / 100.0
        vaa = view_angles[0].mean() / 100.0
        raa = np.cos(np.deg2rad(vaa - saa))
        return rho_surface, mask, sza, vza, raa, rho_unc


class S2ObservationsCreator(ProductObservationsCreator):

    @classmethod
    def can_read(cls, file_refs: List[FileRef]) -> bool:
        i = 0
        while i < len(file_refs) and (data_validation.AWSS2L2Validator().is_valid(file_refs[i].url)
                                      or data_validation.S2L2Validator().is_valid(file_refs[i].url)):
            i+=1
        return i == len(file_refs)

    @classmethod
    def create_observations(cls, file_refs: List[FileRef], reprojection: Optional[Reprojection],
                            emulator_folder: Optional[str]) -> ProductObservations:
        """
        Creates an Observations object for the given fileref object.
        :param file_refs: A list of references to files containing data. These are expected to be of the same data type.
        :param reprojection: A Reprojection object to reproject the data
        :param emulator_folder: A folder containing the emulators for the observations.
        :return: An Observations object that encapsulates the data.
        """
        return S2Observations(file_refs, reprojection, emulator_folder)
