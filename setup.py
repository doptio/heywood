#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='heywood',
    version='0.0.1',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points='''
        [console_scripts]
        heywood = heywood.main:console_script
    ''',
    install_requires=[
        'gevent == 0.13.6',
        'pyinotify == 0.9.3',
    ],
)

