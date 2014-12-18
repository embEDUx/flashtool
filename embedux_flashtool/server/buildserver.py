__author__ = 'mahieke'

import requests
from requests.exceptions import *
from colorama import Fore
import logging as log
from collections import OrderedDict

class BuildserverConnectionError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class BuildserverPackageError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class Buildserver():
    def __init__(self, address, port, configured_platforms):
        '''
        Interface for a buildbot build server. This class provides methods to get information
        about the builds on the server.
        
        :param address: Address to the buildbot server.
        :param port: Port for the buildbot server web interface.
        :param configured_platforms: Valid platforms with existing yaml-recipe.
        '''
        address = address.rstrip('/').rstrip(':')
        self.url = '{}:{}'.format(address, port)
        self.valid_platforms = configured_platforms
        self.info = {
            'builders': None,
            'platforms': None,
            'builds': None,
        }
        self.configured_platforms = configured_platforms

        try:
            r = requests.get(self.url, timeout=1)
            if r.status_code != 200:
                raise BuildserverConnectionError('Can\'t connect to server. Status code {}'.format(r.status_code))
        except ConnectionError as e:
            raise BuildserverConnectionError('Can\'t connect to server. Response: {}, Request: {}'.format(e.response , e.request))
        except Timeout as e:
            raise BuildserverConnectionError('Connection timed out.\n' + Fore.RED + 'Info: {}'.format(e.message))

        log.debug(Fore.GREEN + 'Buildserver url "{}" is valid.'.format(self.url))


    def get_builds(self, platform, product='all'):
        pass


    def get_builds_info(self, force_new=False):
        '''
        Get all built software.
        '''
        platforms = self.info['platforms']

        if not force_new:
            if self.info['builds']:
                return self.info['builds']

        if not platforms or force_new:
            platforms = self.get_platforms_info(force_new)

        builds = OrderedDict()
        for entry in platforms:
            platform = entry[0]
            arch = entry[1]
            
            builder = filter(lambda e: e[0] == arch, self.info['builders'])[0]
            
            for build_num in builder[1]['builds']:
                json_path = 'json/builders/{}/builds/{}'.format(arch, build_num)
                builds_info = self.__get_json_data(json_path)
                
                if builds_info['text'][0] == 'build' and builds_info['text'][1] == 'successful':
                    props = (x for y in builds_info['properties'] for x in y)
                    
                    if platform == (props.next() for item in props if item == 'platform').next():
                        product = (props.next() for item in props if item == 'product').next()
                        files = (props.next() for item in props if item == 'upload_files').next()

                        if builds.get(platform):
                            if builds[platform].get(product):
                                builds[platform][product].extend(files)
                            else:
                                builds[platform].update( { product: files } )
                        else:
                            builds.update(
                                { platform: OrderedDict( { product: files } ) }
                            )

        self.info['builds'] = builds

        return builds


    def get_platforms_info(self, force_new=False):
        '''
        Get information about schedulers of buildbot. Only information about schedulers
        which are in list :param configured_platforms: will be collected.
        Collected information will contain branch-filter name and corresponding
        architecture type.

        :return: List of tuples ({platform}, {architecture})
        '''
        builders = self.info['builders']

        if not force_new:
            if self.info['platforms']:
                return self.info['platforms']

        if not builders or force_new:
            builders = self.get_builders_info(force_new)

        platforms = []
        for entry in builders:
            # get only configured platforms
            result = map(
                lambda x:(x, entry[0]),
                    filter(
                        lambda p: p in self.configured_platforms,
                            entry[1]['schedulers']
                    )
            )

            platforms.extend(result)

        self.info['platforms'] = platforms

        return platforms


    def get_builders_info(self, force_new=False):
        '''
        Tries to get information about all online builders.
        '''
        if not force_new and self.info['builders']:
            return self.info['builders']
        else:
            root_json = self.__get_root_info()

            # collect builders info
            builders = []
            for item in root_json['builders'].values():
                info = self.__builder_info(item)
                if info:
                    builders.append(info)

            self.info['builders'] = builders

            return builders


    def __get_root_info(self):
        '''
        Returns JSON data from buildserver from {server-url}/json
        '''
        root_json_path = 'json'
        return self.__get_json_data(root_json_path)


    def __builder_info(self, info):
        '''
        Returns required information about a builder, if it holds finished builds.

        :param info: json data for a specific builder
        '''
        retVal = (info['basedir'], {'builds': [], 'schedulers': []})

        for entry in info['schedulers']:
            splited_string = entry.split(' / ')
            if len(splited_string) == 3:
                if splited_string[0] == 'default':
                    scheduler = splited_string[2].split(': ')[1].strip('\'').strip('.*')
                    if scheduler in self.valid_platforms:
                        retVal[1]['schedulers'].append(scheduler)
                    
        if retVal[1]['schedulers']:
            arch = retVal[0]
            json_path = 'json/builders/{}/builds/_all'.format(arch)
            retVal[1]['builds'] = self.__get_json_data(json_path).keys()
            return retVal


    def __get_json_data(self, what, opts=[]):
        '''
        Tries to get json data from :attribute url:/:param what: via request call.
        (read json api buildbot for further information)

        :param what: path to specific json data of the buildbot buildserver
        :param opts: list with buildbot options as string (pattern ["{option1}={value}",...])
        :return: Json data as dictionary
        '''
        r = self.__try_request('get', '{}/{}/?{}'.format(self.url, what, '&'.join(opts)).rstrip('?'))

        if r.status_code != 200:
            raise BuildserverConnectionError('Can\'t connect to server. Status code {}'.format(r.status_code))

        json_string = ''
        try:
            json_string = r.json()
        except Exception as e:
            raise BuildserverConnectionError('Can\'t get json data from server.' + Fore.RED + ' Info: {}'.format(e.message))

        return json_string


    def __try_request(self, request, url):
        '''
        Tries a http request on a given url and returns the requested data.
        Exceptions will be handled and raised if an Error occurs

        :param request: Request type. (Supported types: get and post)
        '''
        supported_requests = {
            'get': requests.get,
            'post': requests.post
        }

        retVal = None

        try:
            try:
                retVal = supported_requests[request](url)
            except KeyError:
                raise BuildserverConnectionError(Fore.RED + 'Request type "{}" is not supported! Supported requests: {}'
                                                 .format(request, list(supported_requests.keys())))
        except ConnectionError as e:
            raise BuildserverConnectionError('Can\'t connect to server. {}, {}'.format(e.error, e.request))
        except Timeout as e:
            raise BuildserverConnectionError('Connection timed out.\n' + Fore.RED + 'Info: {}'.format(e.message))
        finally:
            return retVal