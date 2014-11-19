import os
import embedux_flashtool.utility as util
import re

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

__author__ = 'mahieke'


class ConfigLoader():
    """
    Class which reads a flashtool.cfg file in and check if all parameters
    are given.

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


    def load_config(self, props, section):
        """

        :type props: list
        :param props: List with properties you expect
        :param section: Section of flashtool.cfg file
        :return: Dictionary with flashtool.cfg
        """
        parser = configparser.ConfigParser()

        if os.path.isfile(self.file):
            parser.read(self.file)

            if self.__is_valid_config(parser, props, section):
                return parser[section]


    def enter_config(self, props, section, overwrite=True):
        parser = configparser.ConfigParser()
        if not os.path.isfile(self.file):
            open(self.file, 'a')

        parser.read(self.file)

        if not parser.has_section(section):
            parser.add_section(section)

        for prop in props:
            value = parser.get(section, prop, fallback=None)
            if value:
                if overwrite:
                    answer = util.user_prompt( 'Do you want to overwrite Property [{}]->{}'.format(section, prop),
                                               'Existing value "{}": '.format(value), 'YyNn')

                    if re.match(util.create_regex_allowed('Yy'), answer):
                        new_value = util.user_prompt( 'Type in a value for [{}]->{}'.format(section, prop),
                                                      '{} '.format(prop))

                        parser.set(section, prop, new_value)
                        print('')

            else:
                new_value = util.user_prompt( 'Type in a value for [{}]->{}'.format(section, prop),
                                              '{} '.format(prop))

                parser.set(section, prop, new_value)
                print('')

        cfgfile = open(self.file, 'w')
        parser.write(cfgfile)



    def __is_valid_config(self, config, props, section):
        '''

        :param config: configparser object
        :param section: section in configfile
        :param props: properties which are allowed
        :return: True or False if props exist in File
        '''
        keys = []
        for i in config.options(section):
            keys.append(i)

        if set(props).issubset(set(keys)):
            return True
        else:
            return False
