#!/usr/bin/env python

from setuptools import setup, find_packages

name = "flashtool"

setup(
    name=name,
    description="A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS",
    version='0.1.0',
    author="Manuel Hieke",
    author_email="mahieke90@googlemail.com",
    packages=find_packages(),
    package_dir={'flashtool':'flashtool'},
    package_data={'flashtool': ['templates/fstab.tpl']},
    keywords="embedded flash",
    entry_points={
        'console_scripts': [
            'flashtool=flashtool:main'
        ]
    },
    classifiers=[
        'Environment :: Console',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
    license='GPL-3',
    url='https://github.com/embEDUx/flashtool',
)
