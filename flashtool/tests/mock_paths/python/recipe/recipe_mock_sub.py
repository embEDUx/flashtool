__author__ = 'mahieke'

from flashtool.setup.recipe import YAML

class recipe_mock_sub(YAML):
    attr = ['key1', 'key2', 'key3']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        YAML.__init__(self, attributes)