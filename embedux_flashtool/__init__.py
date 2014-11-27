#!/usr/bin/env python

import argparse
import argcomplete
import logging as log
import os
from os.path import expanduser

from colorama import init
from colorama import Fore

from configloader import ConfigLoader
from server import cfgserver
from embedux_flashtool.device.mmc import MMC


__version__ = '0.0.1'
__author__ = 'mahieke'


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
    __flashtool_conf = {
        'Config': ['server'],
        'Buildbot': ['server', 'port'],
        'Local': ['directory']
    }

    def __init__(self):
        self.__home = expanduser("~")
        self.__cfg_path = self.__home + '/.flashtool'
        self.__platform_cfg = 'platforms'

    def __configure(self):
        if not os.path.exists(self.__cfg_path):
            os.mkdir(self.__cfg_path)
            open(self.file, 'a')

        loader = ConfigLoader(self.__cfg_path + '/' + 'flashtool.cfg')

        # Check config file and set unset properties
        loader.enter_config(self.__flashtool_conf)
        self.__conf = loader.load_config(self.__flashtool_conf)


    def __cfg_platform(self, args):
        cfg = cfgserver.ConfigServer(self.__conf['Config']['server'], self.__cfg_path, self.__platform_cfg)
        method = {
            'init'   : cfg.get_initial,
            'update' : cfg.update_confs,
        }

        action = args.action
        log.debug('{} platform configs'.format(action))

        method[action]()

    def __list(self, args):
        action = self.__get_args(args, ['action', 'verbosity', 'where', 'limit'])[0]
        action_value = getattr(args, action)

        log.debug('List {}s for platform {} ({}, limit = {})'.format(action, action_value, args.where, args.limit))


    def __setup(self, args):
        actions = self.__get_args(args, ['action', 'verbosity', 'source', 'platform'])
        if actions:
            action_values = [(action, getattr(args, action)) for action in actions]
        else:
            action_values = [('all_required', 'latest')]

        log.debug('Setup following components ' + Fore.YELLOW + '{} of {} (source = {})'.format(
            ', '.join([t[0] + ':' + t[1] for t in action_values]),
            args.platform,
            args.source)
        )

        MMC().get_mmc()


    def __get_args(self, args, exclude):
        return filter(lambda a: not a.startswith('__')
                                and not callable(getattr(args, a))
                                and not a in exclude
                                and getattr(args, a), dir(args))

    def parse(self):
        # Argument parser
        parser = argparse.ArgumentParser(
            description='A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS')

        parser.add_argument('-V', '--version', action='version', version='Version: ' + __version__)
        parser.add_argument('-v', '--verbosity', default=0, action='count', help='increase output verbosity')

        subparser = parser.add_subparsers(title='commands', dest='action')
        subparser.required = True

        # TODO: fill patform names automatic
        platforms = ['raspberry_pi', 'beaglebone', 'qemu-arm-virt', 'armrider', 'irisboard']
        # TODO: fill valid architectures
        architectures = ['arm', 'armv7']

        # get configs from repository
        conf_parser = subparser.add_parser('conf', help='Manage platform configs')
        conf_parser.add_argument('action', choices=['init', 'update'])
        conf_parser.set_defaults(func=self.__cfg_platform)

        # list
        list_parser = subparser.add_parser('list', help='List build files')
        list_parser.add_argument('--limit', metavar='N', help='Print top N entries')
        list_parser.add_argument('where', choices=['local', 'remote'])

        device_group = list_parser.add_mutually_exclusive_group(required=True)
        device_group.add_argument('-k', '--kernel', choices=platforms + ['all'],
                                  help='List all kernel versions for platform', nargs='?', const='all')
        device_group.add_argument('-u', '--uboot', choices=platforms + ['all'],
                                  help='List all uboot versions for platform', nargs='?', const='all')
        device_group.add_argument('-r', '--rootfs', choices=platforms + ['all'],
                                  help='List all rootfs versions for platform', nargs='?', const='all')
        device_group.add_argument('-m', '--misc', choices=platforms + ['all'],
                                  help='List all misc files for platform', nargs='?', const='all')
        device_group.add_argument('-t', '--toolchain', choices=architectures + ['all'],
                                  help='List all t files for architecture', nargs='?', const='all')
        list_parser.set_defaults(func=self.__list)

        # setup
        setup_parser = subparser.add_parser('setup', help='Setup a device with specified ')
        setup_parser.add_argument('--source', choices=['local', 'remote'], required=True)
        setup_parser.add_argument('platform', choices=platforms)

        setup_parser.add_argument('-k', '--kernel', metavar='version', nargs='?', const='latest')
        setup_parser.add_argument('-u', '--uboot', metavar='version', nargs='?', const='latest')
        setup_parser.add_argument('-r', '--rootfs', metavar='version', nargs='?', const='latest')
        setup_parser.add_argument('-m', '--misc', metavar='version', nargs='?', const='latest')
        setup_parser.set_defaults(func=self.__setup)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        # verbosity of logging
        log.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=get_loglvl(args.verbosity, 2))

        self.__configure()

        args.func(args)


    def __update_configs(self):
        os.path.exists('')


def main():
    # Init colorama
    init(autoreset=True)
    tool = Flashtool()
    tool.parse()


    # print 'Hello World'
