__author__ = 'mahieke'

import abc


class RecipeContentException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class RecipeImportException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class YAML():
    __metaclass__ = abc.ABCMeta

    def __init__(self, attributes):
        for k, v in attributes.items():
            if k in self.attr:
                self.__dict__[k] = v

    def check_attributes(self, attributes):
        for a in attributes.keys():
            if a not in self.attr:
                raise RecipeContentException(
                    'Attribute {} is not allowed for recipe {}'.format(a, self.__class__.__name__))

    def __getattr__(self, at):
        return self[at]

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v

    def __repr__(self):
        return '{} ({})'.format(self.__class__.__name__, self.__dict__)


class Load(YAML):
    attr = ['Rootfs_Rootfs', 'Rootfs_Portage', 'Linux_Root', 'Linux_Boot', 'Linux_Config', 'Uboot', 'Misc_Root', 'Misc_Boot']

    def __init__(self, attributes):
        self.check_attributes(attributes)

        new_attributes = {}
        for k, v in attributes.items():
            if v:
                new_attributes[k] = Product(k, v)
        YAML.__init__(self, new_attributes)


class Product():
    def __init__(self, name, attributes):
        self.name = name
        self.device = None
        self.command = None

        if attributes.get('device') is not None:
            self.device = int(attributes['device'])

        if attributes.get('command') is not None:
            split_cmd = attributes['command'].split(' ')
            self.command = [split_cmd[0], ' '.join(split_cmd[1:])]

        if self.device is not None and self.command is not None\
            or self.device is None and self.command is None:
            raise RecipeContentException(
                'Load config: Product "{}" config must state exactly one attribute (device|command). '
                'User set command: {} and device: {}'.format(
                    name, self.device, self.command))

    def __repr__(self):
        return '{} (device: {}, command: {})'.format(self.name, self.device, self.command)
