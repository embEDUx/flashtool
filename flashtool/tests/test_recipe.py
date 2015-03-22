__author__ = 'mahieke'

import sys
import pytest

sys.path.extend('..')

from flashtool.setup.recipe import RecipeContentException, load_recipes
from flashtool.tests.mock_paths.python.recipe.recipe_mock import recipe_mock
from flashtool.tests.mock_paths.python.recipe.recipe_mock_sub import recipe_mock_sub



def test_yaml_valid():
    input_dict = {
        'key1' : 'value1',
        'key2' : 'value2',
        'key3' : ['a', 'b', 'c'],
    }

    obj = recipe_mock(input_dict)

    assert obj.key1 == input_dict['key1']
    assert obj.key2 == input_dict['key2']
    assert obj.key3 == input_dict['key3']


def test_yaml_invalid_key():
    input_dict = {
        'key2' : 'value1',
        'key3' : 'value2',
        'key4' : 'value3',
    }

    with pytest.raises(RecipeContentException) as excinfo:
        obj = recipe_mock(input_dict)

    assert 'Attribute key4 is not allowed for recipe recipe_mock' in str(excinfo)



def test_yaml_missing_attribute():
    input_dict = {
        'key1' : 'value1'
    }

    with pytest.raises(Exception) as excinfo:
        obj = recipe_mock(input_dict)

    assert 'Attributes are missing: {\'key3\', \'key2\'}' in str(excinfo) or \
           'Attributes are missing: {\'key2\', \'key3\'}' in str(excinfo)


def test_yaml_missing_attribute_subset():
    input_dict = {
        'key1' : 'value1'
    }

    obj = recipe_mock_sub(input_dict)

    assert obj.key1 == input_dict['key1']

    with pytest.raises(TypeError):
        obj.key2

    with pytest.raises(TypeError):
        obj.key3

from flashtool.setup.recipe import load_recipes

def test_load_recipe_from_yaml():
    recipe_dict = {
        'key1' : 'value1',
        'key2' : 'value2',
        'key3' : 'a, b, c',
    }

    import os
    recipe_file = os.path.abspath('flashtool/tests/mock_paths/recipes/test_recipe.yml')

    recipes = load_recipes(recipe_file, 'flashtool.tests.mock_paths.python.recipe')

    for recipe in recipes:
        if isinstance(recipe, recipe_mock):
            assert recipe.key1 == recipe_dict['key1']
            assert recipe.key2 == recipe_dict['key2']
            assert recipe.key3 == recipe_dict['key3']

        if isinstance(recipe, recipe_mock_sub):
            assert recipe.key1 == recipe_dict['key1']

            with pytest.raises(TypeError):
                recipe.key2

            with pytest.raises(TypeError):
                recipe.key3

