__author__ = 'mahieke'

import abc

class DeployImportException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

class Deploy():
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def run(self):
        pass


class Load():
    __metaclass__ = abc.ABCMeta


class Prepare():
    __metaclass__ = abc.ABCMeta

    @abc.abstractstaticmethod
    def get_device(self):
        pass

    @abc.abstractstaticmethod
    def get_load_info(self):
        pass