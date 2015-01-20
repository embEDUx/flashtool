#!/usr/bin/env python

import argparse
import logging as log
import os
from os.path import expanduser
import re
import argcomplete
from collections import OrderedDict
from colorama import init
from colorama import Fore
from colorama import Style

from embedux_flashtool.configloader import ConfigLoader
from embedux_flashtool.server import cfgserver
from embedux_flashtool.setup import Setup
import embedux_flashtool.utility as util
from embedux_flashtool.server.buildserver import Buildserver


__version__ = '0.0.2'
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
        'Local': ['products'],
    }

    platform_cfg = 'platforms'
    cfg = 'flashtool.cfg'

    def __init__(self):
        home = expanduser("~")
        pwd = os.getcwd()

        flashtool_dir = '/.flashtool'

        self.conf_dir_option_required = False
        self.working_dir = ''

        if os.path.exists(home + flashtool_dir):
            self.working_dir = home + flashtool_dir
        elif os.path.exists(pwd + flashtool_dir):
            self.working_dir = pwd + flashtool_dir
        else:
            self.working_dir = home + flashtool_dir
            self.conf_dir_option_required = True


    def parse(self):
        # Argument parser
        parser = argparse.ArgumentParser(
            description='A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS')

        parser.add_argument('-V', '--version', action='version', version='Version: ' + __version__)
        parser.add_argument('-v', '--verbosity', default=0, action='count', help='increase output verbosity')

        if self.conf_dir_option_required:
            parser.add_argument('-w', '--working_dir', required=True,
                                help='Working directory, default is {}'.format(self.working_dir))
        else:
            parser.add_argument('-w', '--working_dir', required=False,
                                help='Working directory, default is {}'.format(self.working_dir))

        subparser = parser.add_subparsers(title='commands', dest='action')
        subparser.required = True

        # get configs from repository
        conf_parser = subparser.add_parser('conf', help='Manage platform configs')
        conf_parser.add_argument('action', choices=['init', 'update'])
        conf_parser.set_defaults(func=self.__cfg_platform)

        # list_platforms
        list_platforms_parser = subparser.add_parser('list_platforms', help='List all supported platforms')
        list_platforms_parser.set_defaults(func=self.__list_platforms)

        # list_builds
        list_builds_parser = subparser.add_parser('list_builds', help='List built files')
        list_builds_parser.add_argument('platform', metavar='platform', nargs='?')
        list_builds_parser.add_argument('--limit', metavar='N', help='Print top N entries')
        list_builds_parser.add_argument('-w', '--where', choices=['local', 'remote'], default='remote')

        products_group = list_builds_parser.add_argument_group('Products (optional)',
                                                                 description='Select products which should be listed. If none '
                                                                             'is selected, all products for the platform will '
                                                                             'be displayed.')

        products_group.add_argument('-l', '--linux', action='store_true',
                                      help='List all linux kernel versions for platform.')
        products_group.add_argument('-u', '--uboot', action='store_true',
                                      help='List all uboot names for platform.')
        products_group.add_argument('-r', '--rootfs', action='store_true',
                                      help='List all rootfs for platform.')
        products_group.add_argument('-m', '--misc', action='store_true',
                                      help='List all misc files for platform.')

        list_builds_parser.set_defaults(func=self.__list_builds)

        # setup
        setup_parser = subparser.add_parser('setup', help='Setup a platform with specified products or all required '
                                                          'latest products')

        setup_group_general = setup_parser.add_argument_group('General options')

        setup_group_general.add_argument('-s', '--source', choices=['local', 'remote'], default='remote', nargs='?',
                                         help='Select if product should be fetched from a local directory or from '
                                              'the buildbot build server. The path or URL to the local directory or '
                                              'server must be defined in the configuration file \'flashtool.cfg\'.')

        setup_group_general.add_argument('-a', '--auto', action='store_true', default=False,
                                         help='If an argument for a product matches for multiple files, the system '
                                              'will fetch the latest file of a product in lexicographical order. '
                                              'Otherwise the user will be prompted to select a specific file.')

        setup_group_general.add_argument('-L', '--Local', action='store_true', default=False,
                                         help='If this argument is set, all downloaded file will be stored at'
                                              'the directory which is configured in the cfg file (Attribute Local).')

        setup_group1 = setup_parser.add_argument_group('Product Group 1 [linux, uboot, misc]',
                                                       description='If no product options are given, flashtool will '
                                                                   'fetch the latest file of a product in '
                                                                   'lexicographical order. The argument of an option '
                                                                   'will be interpreted as regex .*{string}.*. If this '
                                                                   'string matches for multiple will handle this '
                                                                   'situation dependent to the -a/--auto flag '
                                                                   '(see description above).')

        setup_group1.add_argument('-l', '--linux', metavar='version', required=False,
                                  help='Setup linux kernel.')
        setup_group1.add_argument('-u', '--uboot', metavar='version', required=False,
                                  help='Setup uboot.')
        setup_group1.add_argument('-m', '--misc', metavar='version', required=False,
                                  help='Setup misc files.')

        setup_group2 = setup_parser.add_argument_group('Product Group 2 [rootfs]',
                                                       description='If no rootfs is specified the system will choose a '
                                                                   'factory rootfs for the platform if exist. Otherwise '
                                                                   'the user will be prompted to choose a specific '
                                                                   'rootfs.')

        setup_group2.add_argument('-r', '--rootfs', metavar='name', help='Select rootfs')

        setup_parser.add_argument('platform', help='Specifies the platform which should be setuped')

        setup_parser.set_defaults(func=self.__setup)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        # verbosity of logging
        log.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=get_loglvl(args.verbosity, 2))

        if not args.working_dir:
            args.working_dir = self.working_dir

        self.__configure(args.working_dir)

        if args.func == self.__setup:
            # user must state all products or none of them
            if not (args.linux and args.uboot) \
                    and (args.linux or args.uboot):
                parser.error('Setup command needs either all three products to be stated (linux, uboot, misc) or '
                             'none of them.')

            if args.source == 'local' and not (args.linux and args.uboot and args.rootfs):
                parser.error('Setup: All four products must be stated (linux, uboot, misc, rootfs) when option '
                             'source has value "local".')

        args.func(args)


    def __configure(self, working_dir):
        self.working_dir = working_dir
        cfg_path = '{}/{}'.format(working_dir, self.cfg)

        if not os.path.exists(working_dir):
            print(Fore.YELLOW + 'Working directory does not exist at {}'.format(working_dir))
            answer = util.user_prompt('Do you want to setup working directory "{}"'.format(working_dir), 'Answer',
                                      'YyNn')
            if re.match('[Yy]', answer):
                os.mkdir(working_dir)
            else:
                print(Fore.RED + 'ABORT.')
                exit()

        loader = ConfigLoader(cfg_path)

        # Check config file and set unset properties
        loader.enter_config(self.__flashtool_conf)
        self.__conf = loader.load_config(self.__flashtool_conf)


    def __list_builds(self, args):
        actions = self.__get_args(args, ['linux', 'uboot', 'misc', 'rootfs'])
        action_values = [a for a in actions if getattr(args, a)]

        if not action_values:
            action_values = ['linux', 'uboot', 'rootfs', 'misc']


        buildbot = Buildserver(self.__conf['Buildbot']['server'], self.__conf['Buildbot']['port'],
                               self.__get_platforms())

        build_info = buildbot.get_builds_info(True)
        builds = buildbot.get_build_info(build_info, action_values, args.platform)


        for k,v in builds.items():
            print(Fore.YELLOW + '  +-{}-+'.format('-'*len(k)))
            print(Fore.YELLOW + '  | {} |'.format(k))
            print(Fore.YELLOW + '  +-{}-+'.format('-'*len(k)))
            print()
            for kk,vv in v.items():
                print(Style.BRIGHT + '  {}:'.format(kk))
                if kk == 'rootfs':
                    for rfs, files in vv:
                        print('    {}:'.format(rfs))
                        for file in files:
                            print('      {}'.format(file))
                else:
                    files = sorted(set((f[:f.rfind('_')] for f in vv)))

                    for file in files:
                        types = list((f[f.rfind('_'):] for f in vv if file in f))
                        if len(types) > 1:
                            print('    {} (file types: {})'.format(file, ' | '.join(types)))
                        elif len(types) == 1:
                            print('    {}{}'.format(file, types[0]))

                    print('')


    def __setup(self, args):
        action_values = self.__get_args(args, ['linux', 'uboot', 'misc', 'rootfs'])

        log.debug('Setup following products ' + Fore.YELLOW + '{} '
                  .format(', '.join([k + ':' + v for k, v in action_values.items()]))
                  + Fore.RESET + 'for ' + Fore.YELLOW + '{} (source = {}, auto = {})'
                  .format(args.platform, args.source, args.auto)
        )

        supported_platforms = self.__get_platforms()

        if args.platform not in supported_platforms:
            print(Fore.RED + 'ERROR:')
            print(Fore.RED + 'Recipe for platform "{}" could not be found.'.format(args.platform))
            message = ''
            if supported_platforms:
                message += 'You have to execute command ' + Fore.YELLOW + '"conf update"'
            else:
                message += 'You have to execute command' + Fore.YELLOW + '"conf init"'

            message += Fore.RESET + ' to get the latest recipes from the repository.'
            print(message)

            message = 'Or you must define a new recipe file ' + Fore.YELLOW + "{}.yml".format(args.platform)
            message += Fore.RESET + ' at directory ' + Fore.YELLOW + '"{}/{}" or repository "{}".' \
                .format(self.working_dir, self.platform_cfg, self.__conf['Config']['server'])

            print(message)

            return

        yaml_path = '{}/{}/{}.yml'.format(args.working_dir, self.platform_cfg, args.platform)

        if args.source == 'local':
            url = {'dir': self.__conf['Local']['products']}
            #TODO: delete statement when implemented
            print(Fore.RED + 'Option \'-s local\' \'--source local\' is not implemented yet!')
            exit(1)
        else:
            url = self.__conf['Buildbot']

        user_dest = None
        if args.Local:
            user_dest = self.__conf['Local']['products']
            if not os.path.exists(user_dest):
                os.mkdir(user_dest,mode=0o777)

        setup = Setup(url, action_values, yaml_path, args.auto, args.platform, user_dest)
        setup.setup()


    def __list_platforms(self, args):
        platforms = self.__get_platforms()

        if platforms:
            print(Fore.GREEN + 'The following platforms are supported: ' + Fore.YELLOW +
                  '{}'.format(', '.join(platforms)))
        else:
            print(Fore.RED + 'Found no platform recipe. Please run command ' + Fore.YELLOW + '"conf init" ' +
                  Fore.RED + 'first')


    def __get_platforms(self):
        files = os.listdir('{}/{}'.format(self.working_dir, self.platform_cfg))
        yml_files = filter(lambda file: re.match('.*\.yml$', file) and file != 'template.yml', files)
        platforms = map(lambda yml_file: yml_file.rstrip('.yml'), yml_files)

        return list(platforms)


    def __cfg_platform(self, args):
        cfg = cfgserver.ConfigServer(self.__conf['Config']['server'], self.working_dir, self.platform_cfg)
        method = {
            'init': cfg.get_initial,
            'update': cfg.update_confs,
        }

        action = args.action
        log.debug('{} platform configs'.format(action))

        method[action]()


    def __get_args(self, args, get):
        retVal = OrderedDict(
            map(lambda m: (m, getattr(args, m)),
                filter(lambda a: not a.startswith('__')
                                 and not callable(getattr(args, a))
                                 and a in get
                                 and getattr(args, a)
                       , dir(args))))

        for to_set in get:
            if to_set not in retVal:
                retVal[to_set] = ''

        return retVal


def main():
    # Init colorama
    init(autoreset=True)
    tool = Flashtool()

    try:
        tool.parse()
    except KeyboardInterrupt:
        print('')
        print(Fore.GREEN + 'User aborted the process!')
        print(Fore.RED + Style.BRIGHT + 'This could lead to a inconsistent state for '
                                        'the configured platform, if interrupted after the preparation procedure.')
