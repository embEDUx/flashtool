__author__ = 'mahieke'

from flashtool.server import Git

class ConfigServer():
    '''
    Gets all files from a given Git repository
    '''

    def __init__(self, url, dest, name):
        self.__url = url
        self.__dest = dest
        self.__accessor = Git(url, dest, name)


    def get_initial(self):
        self.__accessor.initial_load()


    def update_confs(self):
        self.__accessor.update()