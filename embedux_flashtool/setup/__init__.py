__author__ = 'mahieke'

import yaml

from embedux_flashtool.setup.recipe import RecipeImportException
from embedux_flashtool.setup.recipe import RecipeContentException
from embedux_flashtool.setup.setupfactory import *
from embedux_flashtool.server.buildserver import Buildserver, LocalBuilds
import embedux_flashtool.utility as util
from colorama import Fore
import re


class Setup():
    '''
    Setup procedure for a platform.
    '''

    def __init__(self, url, actions, recipe_file, auto, platform):
        # get existing builds from local directory or
        if url.get('dir'):
            self.builds = LocalBuilds(url['dir'], platform)
        else:
            # buildserver
            self.builds = Buildserver(url['server'], url['port'], platform)

        self.__url = url
        self.__platform = platform
        self.__auto = auto
        self.__actions = actions

        stream = open(recipe_file, 'r')
        documents = yaml.safe_load_all(stream)
        doc_pos = 0

        self.__setup_chain = []

        for doc in documents:
            recipe_type = doc.get('type')
            recipe_content = doc.get('recipe')

            if not recipe_type:
                raise RecipeContentException(
                    '{}.document({}): does not define attribute type.'.format(recipe_file, doc_pos))
            if not recipe_content:
                raise RecipeContentException(
                    '{}.document({}): does not define attribute recipe.'.format(recipe_file, doc_pos))

            recipe_class = _import_recipe_class(recipe_type)
            recipe_obj = recipe_class(recipe_content)

            cls = get_setup_step(recipe_type)

            self.__setup_chain.append(cls(recipe_obj, self.__actions, self.builds, platform, self.__auto))

            doc_pos += 1


    def setup(self):
        for obj in self.__setup_chain:
            obj.prepare()

        for obj in self.__setup_chain:
            obj.load()

def _import_recipe_class(name):
    """import setup recipe class """
    from embedux_flashtool.setup.recipe import Recipe
    import importlib

    path = "embedux_flashtool.setup.recipe."

    python_name = name.lower()

    if path[-1] != '.':
        path += '.'

    try:
        imp = importlib.import_module(path + python_name)
        recipe_class = imp.__entry__
        if issubclass(recipe_class, Recipe):
            return recipe_class
        else:
            raise RecipeImportException('Recipe class "{}" must inherit from class "recipe"!'.format(recipe_class))
    except AttributeError as e:
        raise RecipeImportException('Recipe module "{}" must define the attribute __entry__'.format(path + python_name))
    except ImportError as e:
        raise RecipeImportException('Recipe module "{}" could not be found!'.format(path + python_name))
    except TypeError as e:
        raise RecipeImportException('Value of "{}.__entry__" must be a class!'.format(path + python_name))

