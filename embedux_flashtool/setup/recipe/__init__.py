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


class Recipe(object):
    __metaclass__ = abc.ABCMeta

    def __inti__(self, attributes):
        for k,v in attributes.items():
            self.__dict__[k] = v

    def check_attributes(self, attributes):
        for a in attributes.values:
            if a not in self.attr:
                raise RecipeContentException('Attribute {} is not allowed for recipe {}'.format(a, self.__class__))

    def __iter__(self):
        return iter(self.__dict__)
