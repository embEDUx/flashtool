#!/usr/bin/env python

from setuptools import setup, find_packages

name = "embedux_flashtool"


def get_version(relpath="__init__.py"):
    """read version info from file without importing it"""
    from os.path import dirname, join

    for line in open(join(dirname(__file__), name, relpath)):
        if '__version__' in line:
            if '"' in line:
                # __version__ = "0.9"
                return line.split('"')[1]
            elif "'" in line:
                return line.split("'")[1]


setup(
    name=name,
    description="A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS",
    version=get_version(),
    author="Manuel Hieke",
    author_email="mahieke90@googlemail.com",
    packages=find_packages(),
    keywords="embedded flash",
    entry_points={
        'conosle_scripts': [
            'flashtool=embedux_flashtool:main'
        ]
    },
    install_requires=[
        'colorama>=0.3.2',
        'pyudev>=0.16.1',
        'argcomplete>=0.8.3',
        'PyYAML>=3.11',
        'pyparted'
    ],
    classifiers=[
        'Environment :: Console',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
)
