#!/usr/bin/env python

from setuptools import setup, find_packages

long_description = '''Pythonic Procfile runner

Python port of the Ruby Procfile runner foreman, with a few twists:

 * Does not force every process to run inside a shell.
 * Restart process when one fails, instead of kill all others.
 * Restart all processes on file-changes.
'''

setup(
    name='heywood',
    version='0.3',
    maintainer='Sune Kirkeby',
    maintainer_email='mig@ibofobi.dk',
    url='https://github.com/doptio/heywood/',
    license='MIT',
    description=long_description.split('\n')[0],
    long_description=long_description,
    platforms=['POSIX'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    entry_points='''
        [console_scripts]
        heywood = heywood.main:console_script
    ''',
)
