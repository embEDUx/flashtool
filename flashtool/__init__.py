#!/usr/bin/env python

import argparse
import argcomplete
import logging as log
import os
from os.path import expanduser
import re
from collections import OrderedDict
from datetime import datetime

from colorama import init
from colorama import Fore
from colorama import Style
import subprocess

from flashtool.configmanager import ConfigManager
from flashtool.server import cfgserver
from flashtool.setup import Setup
import flashtool.utility as util
from flashtool.server.buildserver import Buildserver, BuildserverConnectionError
import flashtool.setup.udev.mmc as udev
from flashtool.setup.constants import mkfs_check

__version__ = '1.0.0'
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
    """
    Entry class for the flashtool. It will manage the command line input with argparse.
    """

    # Sections and Options for the flashtool configuration file.
    flashtool_conf = {
        'Recipes': {
            'keywords': ['server', 'user'],
            'help': [
               '  Address or URL to a git server which contains yml recipes for different platforms\n'
               '  Must look like: git@{URL-to-server}:{path-to-git-repository}.git',
               '  Directory where the user can save own recipe files. Path must not include underscores!'
            ]},
        'Buildbot': {
            'keywords': ['server', 'port'],
            'help': [
                '  Address or URL to a buildbot server. Optional Port must be set as next parameter.',
                '  Port of the web frontend of the buildbot server'
            ]},
        'Local': {
            'keywords': ['products'],
            'help': [
                '  Local path where flashtool should save downloaded products if option is selected.'
            ]},
    }

    platform_cfg = 'platforms'
    cfg = 'flashtool.cfg'
    cfg_loader = ConfigManager()

    def __init__(self):
        '''
        Will set the attribute working_dir with default values.
        :return:
        '''
        home = expanduser("~")
        pwd = os.getcwd()

        flashtool_dir = '/.flashtool'

        self.working_dir = ''

        if os.path.exists(pwd + flashtool_dir):
            self.working_dir = pwd + flashtool_dir
        else:
            self.working_dir = home + flashtool_dir

    def parse(self):
        '''
        Argparse routine. Will handle the command line input.
        :return: None
        '''
        # Argument parser
        parser = argparse.ArgumentParser(
            description='A utility that allows to flash several embedded devices with different versions of u-boot, kernel and rootFS')

        parser.add_argument('-V', '--version',
                            action='version',
                            version='Version: ' + __version__
        )
        parser.add_argument('-v', '--verbosity',
                            default=0,
                            action='count',
                            help='increase output verbosity'
        )
        parser.add_argument('-w', '--working_dir',
                            default=self.working_dir,
                            help='Working directory, default is {}'.format(self.working_dir)
        )

        subparser = parser.add_subparsers(title='commands',
                                          dest='action'
        )
        subparser.required = True

        # get configs from repository
        init_parser = subparser.add_parser('init',
                                           help='Initialize flashtool, must be done before using flashtool.')

        init_parser.set_defaults(func=self.__configure)

        conf_parser = subparser.add_parser('platform_recipes',
                                           help='Manage platform recipes'
        )
        conf_parser.add_argument('action',
                                 choices=['init', 'update']
        )
        conf_parser.set_defaults(func=self.__cfg_platform)

        # configure flashtool cfg file
        flashtool_cfg_parser = subparser.add_parser('config',
                                                    help='Manage flashtool config')

        flashtool_cfg_parser.add_argument('keywords',
                                          choices=list(self.flashtool_conf.keys()) + [''],
                                          nargs='*',
                                          default='',
                                          help='Options which should be configured. '
                                               'All option will be asked for configuration, if not given'
        )

        flashtool_cfg_parser.set_defaults(func=self.configure_flashtool)

        # list_platforms
        list_platforms_parser = subparser.add_parser('list_platforms',
                                                     help='List all supported platforms'
        )
        list_platforms_parser.set_defaults(func=self.__list_platforms)

        # list_builds
        list_builds_parser = subparser.add_parser('list_builds',
                                                  help='List built files'
        )
        list_builds_parser.add_argument('platform',
                                        metavar='platform',
                                        nargs='?',
                                        help='Specify a platform name. Only products for this platform will be listed. '
                                             'If none is selected, information for all platforms will be printed.'
        )
        list_builds_parser.add_argument('--limit', metavar='N',
                                        help='Print top N entries'
        )

        # list_builds_parser.add_argument('-w', '--where',
        #                                 choices=['local', 'remote'],
        #                                 default='remote'
        # )

        products_group = list_builds_parser.add_argument_group('Products (optional)',
                                                               description='Select products which should be listed. If none '
                                                                           'is selected, all products for the platform will '
                                                                           'be displayed.')

        products_group.add_argument('-l', '--linux',
                                    action='store_true',
                                    help='List all linux kernel versions for platform.'
        )
        products_group.add_argument('-u', '--uboot',
                                    action='store_true',
                                    help='List all uboot names for platform.'
        )
        products_group.add_argument('-r', '--rootfs',
                                    action='store_true',
                                    help='List all rootfs for platform.'
        )
        products_group.add_argument('-m', '--misc',
                                    action='store_true',
                                    help='List all misc files for platform.'
        )

        list_builds_parser.set_defaults(func=self.__list_builds)

        # setup
        setup_parser = subparser.add_parser('setup',
                                            help='Setup a platform with specified products or all required '
                                                 'latest products'
        )

        setup_group_general = setup_parser.add_argument_group('General options')

        # setup_group_general.add_argument('-s', '--source',
        #                                 choices=['local', 'remote'],
        #                                 default='remote',
        #                                 nargs='?',
        #                                 help='Select if product should be fetched from a local directory or from '
        #                                      'the buildbot build server. The path or URL to the local directory or '
        #                                      'server must be defined in the configuration file \'flashtool.cfg\'.'
        # )

        setup_group_general.add_argument('-a', '--auto', action='store_true',
                                         default=False,
                                         help='If an argument for a product matches for multiple files, the system '
                                              'will fetch the latest file of a product in lexicographical order. '
                                              'Otherwise the user will be prompted to select a specific file.'
        )

        setup_group_general.add_argument('-L', '--Local',
                                         action='store_true',
                                         default=False,
                                         help='If this argument is set, all downloaded file will be stored at'
                                              'the directory which is configured in the cfg file (Attribute Local).'
        )

        setup_group1 = setup_parser.add_argument_group('Product Group 1 [linux, uboot, misc]',
                                                       description='The argument of an option will be interpreted as '
                                                                   'regex .*{string}.*. If this string matches for '
                                                                   'multiple will handle this situation dependent '
                                                                   'to the -a/--auto flag (see description -a Flag). '
                                                                   'The default value for an option is \'\''
        )

        setup_group1.add_argument('-l', '--linux',
                                  metavar='version',
                                  required=False,
                                  default='',
                                  help='Set linux kernel version.'
        )
        setup_group1.add_argument('-u', '--uboot',
                                  metavar='version',
                                  required=False,
                                  default='',
                                  help='Set uboot version.'
        )
        setup_group1.add_argument('-m', '--misc',
                                  metavar='version',
                                  required=False,
                                  default='',
                                  help='Select misc files.'
        )

        setup_group2 = setup_parser.add_argument_group('Product Group 2 [rootfs]',
                                                       description='If no rootfs is specified the system will choose a '
                                                                   'factory rootfs for the platform if exist. Otherwise '
                                                                   'the user will be prompted to choose a specific '
                                                                   'rootfs.'
        )

        setup_group2.add_argument('-r', '--rootfs',
                                  metavar='name',
                                  help='Select rootfs',
                                  default=''
        )

        setup_parser.add_argument('platform',
                                  help='Specifies the platform which should be setuped'
        )

        setup_parser.set_defaults(func=self.__setup)

        fs_check_parser = subparser.add_parser('check_mmc',
                                            help='Filesystem check on partitions of a mmc device'
        )

        fs_check_parser.add_argument('fs_type',
                                     choices=['vfat', 'btrfs', 'ext2', 'ext4'],
                                     nargs='?',
                                     const='',
                                     help='Filesystem types which should be checked.'
        )


        fs_check_parser.set_defaults(func=self.__fs_check)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        self.set_working_dir(args.working_dir)

        if os.path.exists(self.working_dir):
            if not os.path.exists('{}/logs'.format(self.working_dir)):
                os.mkdir('{}/logs'.format(self.working_dir))

            # verbosity of logging
            log.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                            level=get_loglvl(args.verbosity, 2),
                            filename='{}/logs/{}-log'.format(self.working_dir, datetime.now()))

            cfg_path = '{}/{}'.format(self.working_dir, self.cfg)

            self.cfg_loader.set_file(cfg_path)

            # Check config file and set unset properties
            self.conf = self.cfg_loader.load_config(self.flashtool_conf)


        args.func(args)

    def set_working_dir(self, w_dir):
        '''
        setter for the member working_dir
        :param w_dir: working directory path
        :return: None
        '''
        self.working_dir = w_dir.rstrip('/')

    def check_working_dir(self):
        '''
        Check if working directory exists. If not it will terminate the program with
        a Error Message.
        :return: None
        '''
        if not os.path.exists(self.working_dir):
            print('Working directory {0} does not exist.\n'
                  'Please initialize the flashtool first with command:\n'
                  '  flashtool init {0}'.format(self.working_dir))
            exit(1)

    def get_conf(self, section, option):
        '''
        Helper method to retrieve values from the conf dictionary.
        It checks if section and option is specified in flashtoo__conf.

        If section or option does not exist it will raise an exception.
        If conf[section][option] does not exist it will terminate the programm with
        an error Message.

        :param section: Configuration Section
        :param option:  Option of a Section
        :return: Returns the value type:str
        '''
        if section not in list(self.flashtool_conf.keys()):
            raise KeyError('Section {} is not valid for flashtool config.'.format(section))

        if option not in self.flashtool_conf[section]['keywords']:
            raise KeyError('Option {} is not valid for the section {} of the flashtool config'.format(option, section))

        try:
            value = self.conf[section][option]
        except TypeError:
            print(Fore.YELLOW + '[{}]->{} is not set in the configuration file {}'.format(section, option,
                                                                                          self.cfg_loader.file))
            print('  Please run \'flashtool init\'')
            exit(1)

        return value

    def __configure(self, args):
        '''
        Will manage the flashtool config file via the configmanager object.
        It will check the config file and set unset properties, This method
        for initializing the flashtool.
        :param args: Is only need for the call of the module argparse
        :return: None
        '''
        cfg_path = '{}/{}'.format(self.working_dir, self.cfg)

        if not os.path.exists(self.working_dir):
            print(Fore.YELLOW + 'Working directory does not exist at {}'.format(self.working_dir))
            answer = util.user_prompt('Do you want to setup working directory "{}"'.format(self.working_dir), 'Answer',
                                      'YyNn')
            if re.match('[Yy]', answer):
                os.mkdir(self.working_dir)
            else:
                print(Fore.RED + 'ABORT.')
                exit()

        self.cfg_loader.set_file(cfg_path)

        # Check config file and set unset properties
        self.cfg_loader.enter_config(self.flashtool_conf)
        self.conf = self.cfg_loader.load_config(self.flashtool_conf)

    def configure_flashtool(self, args):
        '''
        Allows user to reconfigure options of the flashtool
        with the configmanager object.
        :param args: Arguments given by arparse, must contain a attribute 'keywords'.
        :return: None
        '''
        self.check_working_dir()
        options = args.keywords
        self.cfg_loader.enter_config(self.flashtool_conf, True, options)

    def __list_builds(self, args):
        '''
        Retrieves selected information from the Buildbot server via Buildserver object.
        The information will be printed on the console.
        :param args:
        :return:
        '''
        actions = self.__get_args(args, ['linux', 'uboot', 'misc', 'rootfs'])
        action_values = [a for a in actions if getattr(args, a)]

        if not action_values:
            action_values = ['linux', 'uboot', 'rootfs', 'misc']


        print('  Retrieving information from Server {}:{}...'.format(self.get_conf('Buildbot','server'), self.get_conf('Buildbot', 'port')))
        buildbot = Buildserver(self.get_conf('Buildbot', 'server'), self.get_conf('Buildbot', 'port'),
                               list(map(lambda entry: entry[0], self.get_platforms())))

        build_info = buildbot.get_builds_info()
        print('  Processing json information...');
        builds = buildbot.get_build_info(build_info, action_values, args.platform)

        for k, v in builds.items():
            print(Fore.YELLOW + '  +-{}-+'.format('-' * len(k)))
            print(Fore.YELLOW + '  | {} |'.format(k))
            print(Fore.YELLOW + '  +-{}-+'.format('-' * len(k)))
            print('')
            for kk, vv in v.items():
                print(Style.BRIGHT + '  {}:'.format(kk))
                if kk == 'rootfs':
                    for rfs, files in vv.items():
                        print('    {}:'.format(rfs))
                        for file in files:
                            print('      {}'.format(file))
                else:
                    files = sorted(set((f[:f.rfind('_')] for f in vv)))

                    for file in files:
                        types = set(list((f[f.rfind('_'):] for f in vv if file in f)))
                        if len(types) > 1:
                            print('    {} (file types: {})'.format(file, ' | '.join(types)))
                        elif len(types) == 1:
                            print('    {}{}'.format(file, list(types)[0]))

                print('')

    def __setup(self, args):
        '''
        Setup routine entry point. Will check the command line input first and starts
        calls the setup method of the Setup object.
        :param args: Parsed arguments from argparse
        :return: None
        '''
        self.check_working_dir()
        action_values = self.__get_args(args, ['linux', 'uboot', 'misc', 'rootfs'])

        log.debug('Setup following products {} for {} (auto = {})'
                  .format(', '.join([k + ':' + v for k, v in action_values.items()]),
                          args.platform, args.auto)
        )

        supported_platforms = self.get_platforms()

        try:
            match = next(filter(lambda f: f == args.platform, map(lambda x: x[0], supported_platforms)))
        except StopIteration:
            print(Fore.RED + 'Failure')
            print('  The given platform {} is not configured with a recipe file.'.format(args.platform))
            exit(1)

        if not match:
            print(Fore.RED + 'FAILURE:')
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
                .format(self.working_dir, self.platform_cfg, self.get_conf('Recipes', 'server'))

            print(message)

            return
        else:
            platform, files = next(filter(lambda f: f[0] == args.platform, supported_platforms))
            if len(files) == 1:
                    yaml_path = files[0]
            elif len(files) > 1:
                print('There are multiple recipe files for platform {}.'.format(args.platform))
                i = 0
                for t in files:
                    print('{}:  {}'.format(i, files[i]))
                    i += 1
                selection = int(util.user_select('Please select a recipe:', 0, i))
                yaml_path = files[selection]
            else:
                print(Fore.RED + 'ERROR:')
                print('Unexpected Error occured: THIS SHOULD NEVER HAPPEN!!!')


        # if args.source == 'local':
        #     url = {'dir': self.conf['Local']['products']}
        #     # TODO: delete statement when implemented
        #     print(Fore.RED + 'Option \'-s local\' \'--source local\' is not implemented yet!')
        #     exit(1)
        # else:
        url = self.conf['Buildbot']

        user_dest = None
        if args.Local:
            user_dest = self.get_conf('Local', 'products')
            if not os.path.exists(user_dest):
                os.mkdir(user_dest, mode=0o777)

        setup = Setup(url, action_values, yaml_path, args.auto, args.platform, user_dest)
        setup.setup()

    def __list_platforms(self, args):
        '''
        Prints user all valid platforms.
        :param args: parsed arguments from argparse
        :return: None
        '''
        platforms = self.get_platforms()

        if platforms:
            print(Fore.GREEN + 'The following platforms are supported:')
            for platform_info in platforms:
                print(Fore.YELLOW + '  {}'.format(platform_info[0]))
                for types in platform_info[1]:
                    if types:
                        print(Fore.YELLOW + '    {}'.format(types))
                print('')
        else:
            print(Fore.RED + 'Found no platform recipe. Please run command ' + Fore.YELLOW + '"conf init" ' +
                  Fore.RED + 'first')

    def get_platforms(self):
        '''
        Checks working directory and user recipe path for recipes and
        retrieves for each platform the amount of recipe files.
        :return: List with platform, recipe files tuple
        '''
        self.check_working_dir()
        recipe_path = '{}/{}/'.format(self.working_dir, self.platform_cfg)
        user_recipe_path = '{}/'.format(self.get_conf('Recipes', 'user').rstrip('/'))
        files = [recipe_path + file for file in os.listdir(recipe_path)]

        if os.path.exists(user_recipe_path):
            files += [user_recipe_path + file for file in os.listdir(user_recipe_path)]
        else:
            os.mkdir(user_recipe_path)
            files += [user_recipe_path + file for file in os.listdir(user_recipe_path)]

        yml_files = list(filter(lambda file: re.match('.*\.yml$', file) and 'template.yml' not in file, files))
        platforms = set(map(lambda yml_file: yml_file.split('/')[-1].rstrip('.yml').split('_')[0], yml_files))

        ret_val = []
        for platform in platforms:
            types = []
            for matched_file in filter(lambda x: platform in x, yml_files):
                types.append(matched_file)

            ret_val.append((platform, types))

        return ret_val

    def __cfg_platform(self, args):
        '''
        Loads the recipe files from git server via cfgserver module.
        :param args: Parsed arguments from argparse
        :return: None
        '''
        cfg = cfgserver.ConfigServer(self.get_conf('Recipes', 'server'), self.working_dir, self.platform_cfg)

        method = {
            'init': cfg.get_initial,
            'update': cfg.update_confs,
        }

        action = args.action
        log.debug('{} platform configs'.format(action))

        method[action]()

    def __get_args(self, args, get):
        '''
        Extract arguments from the argparse.Namespace object.
        :param args: argparse.Namespace object
        :param get: list with keys for the argparse.Namespace object
        :return: Dictionary with selected arguments.
        '''
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


    def __fs_check(self,args):
        '''
        Routine to check the filesystem of the partitions of a device.
        :param args: Not needed, but required from argparse API
        :return:
        '''
        device, partitions = udev.get_device(True)

        for partition in partitions:
            fs_type = partition['fs_type']
            path = partition['path']
            print('Check partition {}:'.format(path))
            print('')
            try:
                cmd = mkfs_check[fs_type] + [path]
                if not util.shutil_which(cmd[0]):
                    print(Fore.YELLOW + 'Could not do filesystem check on partition {}. Filesystem format \'{}\' '
                                        'is not supported on your system.'.format(fs_type, path))
                    print('')
                subprocess.call(cmd)
            except KeyError:
                print(Fore.YELLO + 'Could not do filesystem check on partition {}. Filesystem format \'{}\' '
                                   'is not supported by the flashtool'.format(fs_type, path))
                print('')


def main():
    '''
    entry point
    :return:
    '''
    # Init colorama
    init(autoreset=True)
    tool = Flashtool()

    from flashtool.setup.recipe import RecipeContentException

    try:
        tool.parse()
    except KeyboardInterrupt:
        print('')
        print(Fore.GREEN + 'User aborted the process!')
        print(Fore.RED + Style.BRIGHT + 'This could lead to a inconsistent state for '
                                        'the configured platform, if interrupted after the preparation procedure.')
    except BuildserverConnectionError as e:
        print(Fore.RED + '{}'.format(e.message))
        print(Fore.YELLOW + 'Please check your network connection!')
    except RecipeContentException as e:
        print(Fore.RED + '{}'.format(e.message))
        print(Fore.YELLOW + 'Please check the recipe file.\nYou might consider reading '
                            '\nhttps://embedux.github.io/documentation/usage/flashtool/index.html#recipe-files\n'
                            'or update your recipe file with \'flashtool platform_recipes update\' if you have '
                            'an old version of the recipe files.')
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        with open('{}/uncaught_exceptions'.format(tool.working_dir), 'a') as file:
            file.write(tb)


