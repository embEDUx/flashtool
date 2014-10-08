#!/usr/bin/env python

import argparse
import logging as log
from colorama import init

__version__ = '0.0.1'


def get_loglvl(verbosity, minimum=3):
    VERBOSITY_LOGLEVEL = {0: log.CRITICAL,
                          1: log.ERROR,
                          2: log.WARNING,
                          3: log.INFO,
                          4: log.DEBUG}
    verbosity += minimum
    if verbosity > list(VERBOSITY_LOGLEVEL.keys())[-1]:
        return list(VERBOSITY_LOGLEVEL.keys())[-1]
    else:
        return VERBOSITY_LOGLEVEL[verbosity]


def main():
    # Init colorama
    init()

    #Argument parser
    parser=argparse.ArgumentParser(description='A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS')
    parser.add_argument('-V', '--version', action='version', version=__version__)
    parser.add_argument('-v', '--verbosity_', default=0, action='count', help='increase output verbosity')


    #verbosity of logging
    args=parser.parse_args()
    log.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=get_loglvl(args.verbosity))

    print 'Hello World'