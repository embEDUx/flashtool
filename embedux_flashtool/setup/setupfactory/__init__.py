__author__ = 'mahieke'


def get_setup_step(name):
    return _import_deployment_module(name)


def _import_deployment_module(name):
    """
    Imports corresponding deployment classes for preparation the platform and loading
    products to the platform
    """
    from embedux_flashtool.setup.deploy import Deploy
    from embedux_flashtool.setup.deploy import DeployImportException
    import importlib

    path="embedux_flashtool.setup.deploy."

    python_name = name.lower()

    if path[-1] != '.':
        path += '.'

    try:
        imp = importlib.import_module(path + python_name)
        prepare, load = imp.__classes__

        if not issubclass(prepare, Deploy):
            raise DeployImportException('Class {} of deploy module "{}" must inherit from class "Deploy"!'.format(prepare, python_name))

        if not issubclass(load, Deploy):
            raise DeployImportException('Class {} of deploy module "{}" must inherit from class "Deploy"!'.format(load, python_name))

    except AttributeError as e:
        raise DeployImportException('Deploy module "{}" must define the attribute __classes__'.format(python_name))
    except ImportError as e:
        raise DeployImportException('Deploy module "{}" could not be found!'.format(python_name))
    except TypeError as e:
        raise DeployImportException('Value of "{}.__classes__" must be a tuple!'.format(path + python_name))

    return prepare, load