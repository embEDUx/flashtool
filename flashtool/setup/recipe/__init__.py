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

    def check_attributes(self, attributes, subset=True):
        for a in attributes.keys():
            if a not in self.attr:
                raise RecipeContentException(
                    'Attribute {} is not allowed for recipe {}'.format(a, self.__class__.__name__))

        if not subset:
            diff = set(self.attr).difference(attributes.keys())

            if diff:
                raise RecipeContentException('Attributes are missing: {}'.format(diff))

    def __getattr__(self, at):
        return self[at]

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v

    def __repr__(self):
        return '{} ({})'.format(self.__class__.__name__, self.__dict__)


class Load(YAML):
    attr = ['Rootfs_Rootfs', 'Rootfs_Portage', 'Linux_Root', 'Linux_Boot', 'Linux_Config',
            'Uboot', 'Misc_Root', 'Misc_Boot']

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
            self.command = attributes['command'].split(' ', 1)

        if self.device is not None and self.command is not None\
            or self.device is None and self.command is None:
            raise RecipeContentException(
                'Load config: Product "{}" config must state exactly one attribute (device|command). '
                'User set command: {} and device: {}'.format(
                    name, self.device, self.command))

    def __repr__(self):
        return '{} (device: {}, command: {})'.format(self.name, self.device, self.command)



import yaml

def load_recipes(recipe_file, path = 'flashtool.setup.recipe.'):
    stream = open(recipe_file, 'r')
    documents = yaml.safe_load_all(stream)
    doc_pos = 0

    recipes = []

    for doc in documents:
        recipe_type = doc.get('type')
        recipe_content = doc.get('recipe')

        if not recipe_type:
            raise RecipeContentException(
                '{}.document({}): does not define attribute type.'.format(recipe_file, doc_pos))
        if not recipe_content:
            raise RecipeContentException(
                '{}.document({}): does not define attribute recipe.'.format(recipe_file, doc_pos))

        recipe_class = _import_recipe_class(recipe_type, path)
        recipes.append(recipe_class(recipe_content))

        doc_pos += 1

    return recipes


def _import_recipe_class(name, path):
    """import setup recipe class """
    from flashtool.setup.recipe import YAML
    import importlib

    path = path.rstrip('.') + '.'

    python_name = name.lower()

    if path[-1] != '.':
        path += '.'

    try:
        imp = importlib.import_module(path + python_name)
        recipe_class = imp.__entry__
        if issubclass(recipe_class, YAML):
            return recipe_class
        else:
            raise RecipeImportException('Recipe class "{}" must inherit from class "recipe"!'.format(recipe_class))
    except AttributeError as e:
        raise RecipeImportException('Recipe module "{}" must define the attribute __entry__'.format(path + python_name))
    except ImportError as e:
        raise RecipeImportException('Recipe module "{}" could not be found!'.format(path + python_name))
    except TypeError as e:
        raise RecipeImportException('Value of "{}.__entry__" must be a class!'.format(path + python_name))

