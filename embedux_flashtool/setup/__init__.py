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
        self.load_info = []
        self.actions = actions

        stream = open(recipe_file, 'r')
        documents = yaml.safe_load_all(stream)
        doc_pos = 0

        products_conf = next(documents)

        recipe_type = products_conf.get('type')

        if not recipe_type:
            raise RecipeContentException(
                '{}.document({}): does not define attribute "type".'.format(recipe_file, doc_pos))

        if recipe_type != 'ProductsConfig':
            raise RecipeContentException('First document must be of type "ProductsConfig"')

        recipe_content = products_conf.get('recipe')

        if not recipe_content:
            raise RecipeContentException(
                '{}.document({}): does not define attribute "recipe".'.format(recipe_file, doc_pos))

        recipe_class = _import_recipe_class(recipe_type)

        self.products_conf = recipe_class(recipe_content)

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

            prepare, load = get_setup_step(recipe_type)

            self.__setup_chain.append({
                'preparation': (prepare, recipe_obj),
                'load': (load, self.products_conf)
            })

            doc_pos += 1


    def setup(self):
        self.prepare()
        self.load()

    def prepare(self):
        '''
        Executes all preparation steps which are declared in the member variable
        __setup_chain
        :return: None
        '''
        for s in map(lambda s: s['preparation'], self.__setup_chain):
            load_info = s[0](s[1]).run()
            if load_info:
                self.load_info.append(load_info)


    def load(self):
        '''
        Executes all load steps which are declared in the member variable
        __setup_chain
        :return: None
        '''
        if not self.load_info:
            for s in map(lambda s: s['preparation'], self.__setup_chain):
                self.load_info.append(s[0].get_load_info(s[0].get_device()[1]))

                if not self.__auto:
                    answer = util.user_prompt('Do you want to continue?', 'Answer', "YyNn")

                    if re.match("[Nn]", answer):
                        print(Fore.RED + 'ABORT!')
                        exit(0)

        for s in zip(map(lambda s: s['load'], self.__setup_chain), self.load_info):
            load_cls = s[0][0]
            # filter products info which is for the load_class
            products_conf = (p for p in s[0][1] if p[1].module in load_cls.__name__)
            hw_layout = s[1]

            # extract information for loading products to platform
            load_info = {}
            for product_name, values in products_conf:
                device_index = values.device
                prod = product_name.lower().split('_')
                product = prod[0]

                if product in self.actions:
                    name = ''
                    if len(prod) == 1:
                        name = product
                    elif len(prod) == 2:
                        name = prod[1]

                    if load_info.get(prod[0]):
                        load_info[prod[0]].update(
                            {
                                name: hw_layout[device_index]
                            }
                        )
                    else:
                        load_info.update({
                            prod[0]: {
                                'r_name': self.actions[prod[0]],
                                name: hw_layout[device_index]
                            }
                        })
            print('')

            load_cls(load_info, self.builds, self.__platform, self.__auto).run()


# TODO: check if path is suitable when installed via pip
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

