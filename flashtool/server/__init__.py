__author__ = 'mahieke'

import subprocess as sub
import os
import re
from colorama import Fore
import shutil
import logging as log

import flashtool.utility as util

_word = '[a-zA-Z]|[0-9]|[-_.]'

class Git():
    def __init__(self, url, dest, name, branch = 'master'):
        #Check if software is installed
        if not shutil.which('git'):
            raise ReferenceError('You must install "git" to get access to the specified server')

        self.__url = url
        self.__name = name
        self.__branch = branch
        
        if re.match('.*/$', dest):
            self.__dest = dest
        else:
            self.__dest = dest + '/'

        if not self.__check_url():
            raise UrlError('Given URL is not valid!')

        if not os.path.isdir(dest):
            raise PathError('Given path is not a directory!')

    def initial_load(self):
        if os.path.isdir(self.__dest + self.__name):
            # directory already exist
            answer = util.user_prompt('Repository was cloned already.', 'Overwrite?', 'YyNn')

            if re.match('[Yy]',answer):
                shutil.rmtree(self.__dest + self.__name)
                command = 'git clone ' + self.__url + ' ' + self.__dest + self.__name
                log.info('Remove destination path {}'.format(self.__dest + self.__name))
                log.debug('Cloning {} into {} with alias {}'.format(self.__url, self.__dest, self.__name))
                log.info(command)
                sub.call(command, shell=True)
            else:
                answer = util.user_prompt('Pull from repository?', '', 'YyNn')

                if re.match('[Yy]',answer):
                    self.update()
        else:
            log.debug('Cloning {} into {} with alias {}'.format(self.__url, self.__dest, self.__name))
            command = 'git -C {} clone -b {} --single-branch {} {}'.format(self.__dest, self.__branch, self.__url, self.__name)
            log.info(command)
            sub.call(command, shell=True)

    def update(self):
        if os.path.isdir(self.__dest + self.__name):
            command = 'git -C {} pull -X recursive-theirs'.format(self.__dest + self.__name)
            log.debug('Update local repository {}/{} from remote {}'.format(self.__dest, self.__name, self.__url))
            log.info(command)
            git_ret = sub.call(command, shell=True)
        else:
            print('Directory does not exist.' + Fore.RED + 'Can\'t Update!')


    def __check_url(self):
        re_git = r'git@(' + _word + ')+:(\/|' + _word + ')+\.git'
        re_https = r'https:\/\/(' + _word + ')+\/(\/|' + _word + ')+\.git'

        check = False

        if re.match(re_https + '|' + re_git, self.__url):
            check = True

        return check


class UrlError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class PathError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)