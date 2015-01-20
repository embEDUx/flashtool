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