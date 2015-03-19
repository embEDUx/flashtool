__author__ = 'mahieke'

import yaml

from flashtool.setup.recipe import RecipeImportException
from flashtool.setup.recipe import RecipeContentException
from flashtool.setup.recipe import load_recipes
from flashtool.setup.deploy import get_setup_step
from flashtool.server.buildserver import Buildserver, LocalBuilds

class Setup():
    '''
    Setup procedure for a platform.
    '''

    def __init__(self, url, actions, recipe_file, auto, platform, user_dest=None):
        # get existing builds from local directory or
        if url.get('dir'):
            self.builds = LocalBuilds(url['dir'], platform)
        else:
            # buildserver
            self.builds = Buildserver(url['server'], url['port'], platform, user_dest)

        self.__setup_chain = []
        recipes = load_recipes(recipe_file)

        for recipe in recipes:
            setup_class = get_setup_step(recipe.__class__.__name__)

            self.__setup_chain.append(setup_class(recipe, actions, self.builds, platform, auto))


    def setup(self):
        for obj in self.__setup_chain:
            obj.prepare()

        for obj in self.__setup_chain:
            obj.load()
