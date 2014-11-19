#!/usr/bin/env python

import argparse
import logging as log
import os
from os.path import expanduser
from colorama import init
from configloader import ConfigLoader


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


class Flashtool():
    __conf_props = ['git_url', 'git_group', 'git_repo']
    __ansible_props = ['server', 'port']

    def __init__(self):
        self.__home = expanduser("~")
        self.__cfg_path = self.__home + '/.flashtool/'
        if not os.path.exists(self.__cfg_path):
            os.mkdir(self.__cfg_path)

        loader = ConfigLoader(self.__cfg_path + 'flashtool.cfg')

        # Check config file and set unset properties
        self.__config = loader.enter_config(self.__conf_props, 'Config')
        self.__config = loader.enter_config(self.__ansible_props, 'Ansible')



    def parse(self):
         #Argument parser
        parser=argparse.ArgumentParser(description='A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS')
        parser.add_argument('-V', '--version', action='version', version=__version__)
        parser.add_argument('-v', '--verbosity', default=0, action='count', help='increase output verbosity')
        #verbosity of logging
        args=parser.parse_args()

        log.basicConfig(level=get_loglvl(args.verbosity))


    def __update_configs(self):
        os.path.exists('')







def main():
    # Init colorama
    init()
    log.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=get_loglvl(3))
    tool = Flashtool()
    #tool.parse()


    #print 'Hello World'