#!/usr/bin/env python
import setuptools
import os

on_rtd = os.environ.get('READTHEDOCS') == 'True'
if on_rtd:
    requirements = ['mock']
else:
    requirements = []
#     requirements = [
#         'setuptools',
#         'numpy',
#         'pytest',
#         'shapely',
#         'scipy',
#         'pyyaml']

__version__ = None
with open('multiply_core/version.py') as f:
    exec(f.read())

setup_args = dict(name='multiply-core',
                  packages=setuptools.find_packages(),
                  include_package_data = True,
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

if __name__ == "__main__":
    setuptools.setup(**setup_args)