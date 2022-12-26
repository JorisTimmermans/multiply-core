#!/usr/bin/env python

from setuptools import setup
import os

on_rtd = os.environ.get('READTHEDOCS') == 'True'
if on_rtd:
    requirements = ['mock']
else:
    # requirements = [
    #     'gdal',
    #     'numpy',
    #     'pytest',
    #     'shapely',
    #     'scipy',
    #     'pyyaml']
    requirements = []

__version__ = None
with open('multiply_core/version.py') as f:
    exec(f.read())

setup(name='multiply-core',
      packages=find_packages(),
      version=__version__,
      description='MULTIPLY Core',
      author='MULTIPLY Team',
      entry_points={
          'observations_creators': [
              's2_observation_creator = multiply_core.observations:s2_observations.S2ObservationsCreator',
          ],
          'variables': ['core_variables = multiply_core.variables:variables.get_default_variables'],
          'aux_data_provider_creators': ['default_provider_creator = '
                                         'multiply_core.util:aux_data_provision.DefaultAuxDataProviderCreator']
      },
      install_requires=requirements
      )
