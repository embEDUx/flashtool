import os
import flashtool.utility as util
import re
import logging as log
from colorama import Fore

import configparser

__author__ = 'mahieke'


class ConfigManager():
    """
    Class which reads config files and manage them

    """

    def __init__(self, file=''):
        """
        :param file: location of flashtool.cfg file
        """
        assert isinstance(file, str)

        self.file = file
        self.__parser = configparser.ConfigParser()


    def set_file(self,path):
        self.file = path

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


    def enter_config(self, config_options, overwrite=False, required_sections = []):
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
            log.info('  Config file "{}" does not exist: CREATE'.format(self.file))
            open(self.file, 'a')

        self.__parser.read(self.file)

        changed = False

        if not required_sections:
            required_sections = config_options.keys()

        for section in config_options.keys():
            if section not in required_sections:
                continue

            if not self.__parser.has_section(section):
                log.info('  Section "{}" does not exist: CREATE'.format(section))
                self.__parser.add_section(section)

            options = config_options[section]['keywords']
            log.info('  Required options for section [{:15}]: {}'.format(section, ','.join(options)))

            if self.__delete_unused_options(options, section):
                changed = True

            for option in zip(options, config_options[section]['help']):
                value = self.__parser.get(section, option[0], fallback=None)
                if value is not None:
                    if overwrite:
                        answer = util.user_prompt( 'Do you want to overwrite Property [{}]->{}'.format(section, option[0]),
                                                   'Existing value "{}"'.format(value), 'YyNn')

                        if re.match(util.create_regex_allowed('Yy'), answer):
                            print('')
                            new_value = util.user_prompt( 'Type in a value for [{}]->{}\nhelp: {}'.format(section, option[0], option[1]),
                                                          '{} '.format(option[0]))

                            self.__parser.set(section, option[0], new_value)
                            changed = True
                            print('')

                else:
                    new_value = util.user_prompt( 'Type in a value for',
                                                  Fore.YELLOW + '   [{}]->{}'.format(section, option[0]) + Fore.RESET +
                                                                '\nhelp: {}\n'.format(option[1]))

                    self.__parser.set(section, option[0], new_value)
                    changed = True
                    print('')

        if changed:
            cfg_file = open(self.file, 'w')
            self.__parser.write(cfg_file)
            cfg_file.close()
            log.info('  Config file changed: SAVED')
            log.info('New config file content:\n{}'.format(self.__dump_config()))
        else:
            log.info('  Values for required options EXIST')



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

            log.debug('  Existing options: {}'.format(','.join(options_in_parser)))
            log.debug('  Required options: {}'.format(','.join(config_options[section]['keywords'])))

            if not set(config_options[section]['keywords']).issubset(set(options_in_parser)):
                is_valid = False
                log.info('  Section {}: INVALID'.format(section))
                break

            log.info('Section [{}]: VALID'.format(section))

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
            log.info('  Found unused options "{}" in section {}: DELETE'.format(','.join(unused_options), section))

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
