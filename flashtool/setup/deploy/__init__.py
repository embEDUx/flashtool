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
    def __init__(self, recipe, actions, builds, platform, auto):
        pass

    @abc.abstractmethod
    def prepare(self):
        pass

    @abc.abstractmethod
    def load(self):
        pass


def get_setup_step(name):
    return _import_deployment_module(name)


def _import_deployment_module(name):
    """
    Imports corresponding deployment classes for preparation the platform and loading
    products to the platform
    """
    from flashtool.setup.deploy import Deploy
    from flashtool.setup.deploy import DeployImportException
    import importlib

    path="flashtool.setup.deploy."

    python_name = name.lower()

    if path[-1] != '.':
        path += '.'

    try:
        imp = importlib.import_module(path + python_name)
        deploy = imp.__entry__

        if not issubclass(deploy, Deploy):
            raise DeployImportException('Class {} of deploy module "{}" must inherit from class "Deploy"!'.format(prepare, python_name))

    except AttributeError as e:
        raise DeployImportException('Deploy module "{}" must define the attribute __classes__'.format(python_name))
    except ImportError as e:
        raise DeployImportException('Deploy module "{}" could not be found!'.format(python_name))
    except TypeError as e:
        raise DeployImportException('Value of "{}.__classes__" must be a tuple!'.format(path + python_name))

    return deploy