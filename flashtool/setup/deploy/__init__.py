__author__ = 'mahieke'def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

import abc

class DeployImportException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

class Deploy():
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, recipe, actions, builds, platform, auto):
        pass

    @abc.abstractmethod
    def prepare(self):
        pass

    @abc.abstractmethod
    def load(self):
        pass

