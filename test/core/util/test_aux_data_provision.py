import os
from typing import Optional, List

from multiply_core.util.aux_data_provision import AuxDataProvider, DefaultAuxDataProvider, get_aux_data_provider, \
    DefaultAuxDataProviderCreator, _get_aux_data_provider, _add_aux_data_provider, _set_up_aux_data_provider_registry, \
    AuxDataProviderCreator

import urllib.request
import zipfile

__author__ = 'Tonio Fincke (Brockmann Consult GmbH)'

test_data_save_path = '/tmp/test_data.zip'
if not os.path.exists(test_data_save_path):
    urllib.request.urlretrieve('https://github.com/QCDIS/multiply-core/raw/master/test/test_data.zip', test_data_save_path)
    with zipfile.ZipFile(test_data_save_path, 'r') as zip_ref:
        zip_ref.extractall('/tmp')
    zip_ref.close()
base_path = '/tmp/test_data/'

TEST_DATA_PATH = base_path + '2018_10_23/'


def test_name():
    provider = DefaultAuxDataProvider({})

    assert 'DEFAULT' == provider.name()


def test_list_elements():
    provider = DefaultAuxDataProvider({})
    elements = provider.list_elements(TEST_DATA_PATH, return_absolute_paths=False)
    assert 6 == len(elements)
    assert base_path + '2018_10_23\\2018_10_23_aod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_aod550.tif' in elements
    assert base_path + '2018_10_23\\2018_10_23_bcaod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_bcaod550.tif' in elements
    assert base_path + '2018_10_23\\2018_10_23_duaod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_duaod550.tif' in elements
    assert base_path + '2018_10_23\\2018_10_23_gtco3.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_gtco3.tif' in elements
    assert base_path + '2018_10_23\\2018_10_23_omaod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_omaod550.tif' in elements
    assert base_path + '2018_10_23\\2018_10_23_suaod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_suaod550.tif' in elements


def test_list_elements_with_pattern():
    provider = DefaultAuxDataProvider({})
    elements = provider.list_elements(TEST_DATA_PATH, '*uaod*.tif', return_absolute_paths=False)
    assert 2 == len(elements)
    assert base_path + '2018_10_23\\2018_10_23_duaod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_duaod550.tif' in elements
    assert base_path + '2018_10_23\\2018_10_23_suaod550.tif' in elements \
           or base_path + '2018_10_23/2018_10_23_suaod550.tif' in elements


def test_assure_element_provided():
    provider = DefaultAuxDataProvider({})
    provided = provider.assure_element_provided(base_path + '2018_10_23/2018_10_23_duaod550.tif')
    assert provided
    assert os.path.exists(base_path + '2018_10_23/2018_10_23_duaod550.tif')


def test_assure_element_provided_not():
    provider = DefaultAuxDataProvider({})
    provided = provider.assure_element_provided(base_path + '2018_10_23\\2018_10_23_dumaod550.tif')
    assert not provided
    assert not os.path.exists(base_path + '2018_10_23\\2018_10_23_dumaod550.tif')


def test_default_aux_data_provider_creator_name():
    assert 'DEFAULT' == DefaultAuxDataProviderCreator().name()


def test_default_aux_data_provider_creator_create_aux_data_provider():
    provider = DefaultAuxDataProviderCreator().create_aux_data_provider({})

    assert provider is not None
    assert 'DEFAULT' == provider.name()

def test_get_aux_data_provider():
    provider = get_aux_data_provider()
    assert provider is not None
    assert 'DEFAULT' == provider.name()


def test_get_aux_data_provider_dummy():

    class DummyAuxDataProvider(AuxDataProvider):

        def __init__(self, parameters:dict):
            pass

        @classmethod
        def name(cls) -> str:
            return 'DUMMY'

        def list_elements(self, base_folder: str, pattern: [Optional[str]]) -> List[str]:
            pass

        def assure_element_provided(self, name: str) -> bool:
            pass

    class DummyAuxDataProviderCreator(AuxDataProviderCreator):

        @classmethod
        def name(cls):
            return 'DUMMY'

        @classmethod
        def create_aux_data_provider(self, parameters: dict) -> DummyAuxDataProvider:
            return DummyAuxDataProvider(parameters)

    _set_up_aux_data_provider_registry()
    _add_aux_data_provider(DummyAuxDataProviderCreator())
    provider = _get_aux_data_provider(base_path + 'aux_data_provider.json')

    assert provider is not None
    assert 'DUMMY' == provider.name()
