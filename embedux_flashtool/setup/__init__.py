__author__ = 'mahieke'

import yaml
from embedux_flashtool.setup.prepare import RecipeImportException
from embedux_flashtool.setup.prepare import RecipeContentException


class Setup():
    '''
    Setup a setup.
    '''
    def __chain_link_template(self, name, klass, params):
        return {
            'name': name,
            'class' : klass,
            'params' : params
        }

    def __init__(self, recipe_file, url, actions):
        stream = open(recipe_file, 'r')
        documents = yaml.safe_load_all(stream)
        doc_pos = 0

        comp_conf = next(documents)

        recipe_type = comp_conf.get('type')

        if not recipe_type:
            raise RecipeContentException('{}.document({}): does not define attribute "type".'.format(recipe_file, doc_pos))

        if recipe_type != 'components_config':
            raise RecipeContentException('First document must be of type "components_config"')

        recipe_content = comp_conf.get('recipe')

        if not recipe_content:
            raise RecipeContentException('{}.document({}): does not define attribute "recipe".'.format(recipe_file, doc_pos))

        recipe_class = _import_recipe_class(recipe_type)

        self.components_conf = recipe_class(recipe_content, actions)

        self.__setup_chain = []

        for doc in documents:
            recipe_type = doc.get('type')
            recipe_content = doc.get('recipe')

            if not recipe_type:
                raise RecipeContentException('{}.document({}): does not define attribute type.'.format(recipe_file, doc_pos))
            if not recipe_content:
                raise RecipeContentException('{}.document({}): does not define attribute recipe.'.format(recipe_file, doc_pos))

            recipe_class = _import_recipe_class(recipe_type)
            recipe_class.check_attributes(recipe_content)

            self.__setup_chain.append(self.__chain_link_template(recipe_type, recipe_class, recipe_content))

            doc_pos += 1

        self.__url = url


    def setup(self):
        for setup_info in self.__setup_chain:
            setup_process = setup_info['class'](setup_info['params'])
            #setup_process.info = getattr(self.components_conf, setup_info['name'])
            setup_process.run()


# TODO: check if path is suitable when installed via pip
def _import_recipe_class(name, path="embedux_flashtool.setup.prepare."):
    """import setup recipe class """
    from embedux_flashtool.setup.prepare import recipe
    import importlib

    if path[-1] != '.':
        path += '.'

    try:
        imp = importlib.import_module(path + name)
        recipe_class = imp.__entry__
        if issubclass(recipe_class, recipe):
            return recipe_class
        else:
            raise RecipeImportException('Recipe class "{}" must inherit from class "recipe"!'.format(recipe_class))
    except AttributeError as e:
        raise RecipeImportException('Recipe module "{}" must define the attribute __entry__'.format(path + name))
    except ImportError as e:
        raise RecipeImportException('Recipe module "{}" could not be found!'.format(path + name))
    except TypeError as e:
        raise RecipeImportException('Value of "{}.__entry__" must be a class!'.format(path + name))

