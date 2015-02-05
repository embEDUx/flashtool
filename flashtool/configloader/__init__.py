import os
import flashtool.utility as util
import re
import logging as log
from colorama import Fore

import configparser

__author__ = 'mahieke'


class ConfigLoader():
    """
    Class which reads config files and manage them

    """

    def __init__(self, file):
        """
        :param file: location of flashtool.cfg file
        """
        try:
            assert isinstance(file, basestring)
        except NameError:
            assert isinstance(file, str)

        self.file = file
        self.__parser = configparser.ConfigParser()


    def load_config(self, config_options):
        """
        Loads a config if all options are given in the config file.

        :type options: list
        :param config_options: Dict with tuples of section:[options...]
        :return: Dictionary with flashtool.cfg
        """
        if os.path.isfile(self.file):
            self.__parser.read(self.file)

            if self.__is_valid_config(config_options):
                return self.__parser


    def enter_config(self, config_options, overwrite=False):
        '''
        Creates or reads a the config file given by self.file and sets up
         all needed options. Values for unset options will be asked to be
         set by the user.

        :param config_options: Dict with tuples of section:[options...]
        :param overwrite: Flag whether existing options should be overwritten
        :return: None
        '''
        log.info('Enter config file "{}"'.format(self.file))
        if not os.path.isfile(self.file):
            log.info('  Config file "{}" does not exist: '.format(self.file) + Fore.GREEN + 'CREATE')
            open(self.file, 'a')

        self.__parser.read(self.file)

        changed = False

        for section in config_options.keys():
            if not self.__parser.has_section(section):
                log.info('  Section "{}" does not exist: '.format(section) + Fore.GREEN + 'CREATE')
                self.__parser.add_section(section)

            options = config_options[section]
            log.info('  Required options for section ' + Fore.YELLOW + '[{:15}]: {}'.format(section, ','.join(options)))

            if self.__delete_unused_options(options, section):
                changed = True


            for option in options:
                value = self.__parser.get(section, option, fallback=None)
                if value:
                    if overwrite:
                        answer = util.user_prompt( 'Do you want to overwrite Property [{}]->{}'.format(section, option),
                                                   'Existing value "{}": '.format(value), 'YyNn')

                        if re.match(util.create_regex_allowed('Yy'), answer):
                            new_value = util.user_prompt( 'Type in a value for [{}]->{}'.format(section, option),
                                                          '{} '.format(option))

                            self.__parser.set(section, option, new_value)
                            changed = True
                            print('')

                else:
                    new_value = util.user_prompt( 'Type in a value for',
                                                  '[{}]->{}'.format(section, option))

                    self.__parser.set(section, option, new_value)
                    changed = True
                    print('')

        if changed:
            cfgfile = open(self.file, 'w')
            self.__parser.write(cfgfile)
            cfgfile.close()
            log.info('  Config file changed: ' + Fore.GREEN + 'SAVED')
            log.info('New config file content:\n{}'.format(self.__dump_config()))
        else:
            log.info('  Values for required options  ' + Fore.GREEN + 'EXIST')


    def check_values(self, config_options):
        self.__parser.read(self.file)
        answer = True
        if self.__is_valid_config(config_options):
            for section in config_options.keys():
                options = config_options[section]

                for option in options:
                    if not self.__parser[section][option]:
                        answer = False

        return answer



    def __is_valid_config(self, config_options):
        '''
        Checks if all options are given in the config

        :param config_options: Dict with tuples of section:[options...]
        :return: True or False if options exist in File
        '''
        is_valid = True
        for section in config_options.keys():
            if not self.__parser.has_section(section):
                is_valid = False
                break

            log.info('Check options in section "{}"'.format(section))
            options_in_parser = []
            for i in self.__parser.options(section):
                options_in_parser.append(i)

            log.debug('  Existing options: ' + Fore.YELLOW + '{}'.format(','.join(options_in_parser)))
            log.debug('  Required options: ' + Fore.YELLOW + '{}'.format(','.join(config_options[section])))

            if not set(config_options[section]).issubset(set(options_in_parser)):
                is_valid = False
                log.info('  Section {}: ' + Fore.RED + 'INVALID'.format(section))
                break

            log.info('Section [{}]: '.format(section) + Fore.GREEN + 'VALID')

        return is_valid


    def __delete_unused_options(self, used_options, section):
        '''
        Deletes all options of a section which are unused

        :param parser: configparser object with loaded config
        :param used_options: options which are used
        :param section: section in config file to be checked
        :return: True for deleting options, False if not
        '''
        hasDeleted = False

        keys = []
        for i in self.__parser.options(section):
            keys.append(i)

        unused_options = set(keys) - set(used_options)

        if unused_options:
            hasDeleted = True
            log.info('  Found unused options "{}" in section {}: '.format(','.join(unused_options), section) + Fore.RED + 'DELETE')

        for option in unused_options:
            self.__parser.remove_option(section, option)

        return hasDeleted


    def __dump_config(self):
        '''
        Dump entire config file
        :return: Dump as string
        '''
        output = ""
        for section in self.__parser.sections():
            output += '  [{}]:\n'.format(section)
            for option in self.__parser.options(section):
                output += '    {} = {}\n'.format(option, self.__parser.get(section, option))

        return output
