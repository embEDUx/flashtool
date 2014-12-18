__author__ = 'mahieke'

import abc


class Recipe():
    __metaclass__ = abc.ABCMeta
    attr = []

    def __init__(self, attributes):
        for k, v in attributes.items():
            self.__setattr__(k, v)

    def __setattr__(self, attr, value):
        self.__dict__[attr] = value

    @classmethod
    def check_attributes(cls, attributes):
        import collections

        if not hasattr(cls, 'attr'):
            raise RecipeDefinitionException(
                'Class for recipe "{}" does not define class attribute "attr".'.format(cls.__name__))

        if not collections.Counter(cls.attr) == collections.Counter(attributes.keys()):
            raise RecipeContentException(
                'Found invalid attributes for recipe {}: Valid attributes: {} - Given attributes: {}'.format(cls.__name__, ', '.join(cls.attr),
                                                                                              ', '.join(
                                                                                                  attributes.keys())))

    def __repr__(self):
        return '{}: ({})'.format(self.__class__.__name__, self.__dict__)


class Runnable():
    @abc.abstractmethod
    def run(self):
        pass


class RecipeDefinitionException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class RecipeImportException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class RecipeContentException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)