__author__ = 'mahieke'

import requests
from requests.exceptions import *
from colorama import Fore
import logging as log
from collections import OrderedDict
import os
import re
import sys
from urllib.request import urlretrieve
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.error import URLError
import json

import flashtool.utility as util


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
    def __init__(self, address, port, configured_platforms, dest=None):
        '''
        Interface for a buildbot build server. This class provides methods to get information
        about the builds on the server.

        :param address: Address to the buildbot server.
        :param port: Port for the buildbot server web interface.
        :param configured_platforms: Valid platforms
        '''
        address = address.rstrip('/').rstrip(':')
        if port is '':
            self.url = '{}'.format(address)
        else:
            self.url = '{}:{}'.format(address,port)

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
            raise BuildserverConnectionError(
                'Can\'t connect to server. Response: {}, Request: {}'.format(e.response, e.request))
        except Timeout as e:
            raise BuildserverConnectionError('Connection timed out.\n' + Fore.RED + 'Info: {}'.format(e.message))

        log.debug('Buildserver url "{}" is valid.'.format(self.url))

        self.loaded_files = []

        self.dest = dest

        if dest:
            self.json_file = '{}/.platforms'.format(self.dest)
            if not os.path.exists(self.json_file):
                open(self.json_file, 'a').close()

            if os.path.getsize(self.json_file) > 0:
                self.local_platform_info = json.load(open(self.json_file))
            else:
                self.local_platform_info = {}


    def get_file(self, file_path):
        '''
        Downloads files from the buildserver to the local destination. If dest is None the default path
        will be at /tmp.
        :param files: files per file_type
        :param dest:
        :return:
        '''

        def reporthook(blocknum, blocksize, totalsize):
            percentage = (min(100, float(blocknum * blocksize) / totalsize * 100))

            if 1023 < totalsize < 1024 * 1024:
                size = float(totalsize/1024.0)
                print('     {:3.1f}% of {:5.4f} kBytes'.format(percentage, size), end='\r'),
            elif 1024 * 1024 < totalsize:
                size = float(totalsize / (1024.0 * 1024.0))
                print('     {:3.1f}% of {:5.4f} MBytes'.format(percentage, size), end='\r'),
            else:
                print('     {:3.1f}% of {} Bytes'.format(percentage, totalsize), end='\r'),

            sys.stdout.flush()

        def file_exists(file_name):
            return os.path.isfile(file_name)

        ret_val = []
        if not self.dest:
            dest = '/tmp/flashtool'
        else:
            dest = self.dest.rstrip('/')

        url = '{}/{}'.format(self.url, file_path)
        file_name = file_path.split('/')[-1]
        product = file_path.split('/')[0]
        dest_name = '{}/{}'.format(dest, '/'.join(file_path.split('/')[:-1]))
        dest_file = '{}/{}'.format(dest_name, file_name)

        if not os.path.isdir(dest_name):
            os.makedirs(dest_name)

        if not file_exists(dest_file):
            print('    DOWNLOAD FILE:\n'
                  '    URL:  {}\n'
                  '    FILE: {}\n'.format(url, file_name))
            try:
                urlretrieve(url, dest_file, reporthook)
            except KeyboardInterrupt:
                print(Fore.YELLOW + '   User aborted download')
                os.remove(dest_file)
                raise
            except Exception as e:
                print(Fore.RED + '   An Error occured while downloading.')
                print(Fore.RED + '   {}'.format(repr(e)))
                os.remove(dest_file)
                raise

        else:
            print(Fore.YELLOW + '   FILE {} WAS ALREADY DOWNLOADED:'.format(file_name))


        return dest_file, os.stat(dest_file).st_size

    def get_file_size(self, file):
        url = '{}/{}'.format(self.url, file)
        meta = dict(urlopen(url).info())

        return meta["Content-Length"]

    def get_files_path(self, file_info, reg_name, file_types, auto):
        '''

        :param file_info:
        :param reg_name:
        :param file_types:
        :param auto:
        :return:
        '''
        for platform, products_info in file_info.items():
            for product, unsorted_files in products_info.items():
                if product == 'rootfs':
                    files = ['rootfs/{}/{}'.format(k, e) for k,v in unsorted_files.items() for e in v]
                else:
                    files = ['{}/{}/{}'.format(product, platform, e) for e in unsorted_files]

                # check if file is available on server
                #files = [f for f in files if self.is_file_available(f)]

                str_match = '.*{}.*'.format(reg_name)
                re_file = re.compile(str_match)
                matched_files = list(filter(lambda f_name: re_file.match(f_name), files))
                versions = sorted(set([f[:f.rfind('_')] for f in matched_files]))

                #sort via date stamp of file

                if len(versions) > 1:
                    print(
                    Fore.YELLOW + '  Found multiple versions for product {} with regex {}'.format(product, str_match))

                    if auto:
                        if product == 'rootfs' and str_match == '.*.*':
                            print(Fore.GREEN + '  [AUTO-MODE] Take newest factory built.')
                            filtered_versions = list(filter(lambda x: 'factory' in x,versions))
                            version = filtered_versions[-1]
                        else:
                            # take newest
                            print(Fore.GREEN + '  [AUTO-MODE] Take newest built.')
                            version = versions[-1]
                    else:
                        i = 0
                        for f in versions:
                            print('    [{}]: {}'.format(i, f.split('/')[-1]))
                            i += 1

                        print('')
                        selection = int(util.user_select('  [MANUAL-MODE] Please select a file:', 0, i))
                        version = versions[selection]
                elif len(versions) == 1:
                    print(Fore.YELLOW + '  Found one version for product {} with regex {}'.format(product, str_match))
                    version = versions[0]

                print(Fore.GREEN + '  -> Selected version: {}:'.format(version.split('/')[-1]))

        ret_val = []
        for product, f_types in file_types:
            f_info = []
            for f_type in f_types:
                f_info.append((f_type, next(f_name for f_name in matched_files if re.match('{}_{}.*'.format(version, f_type), f_name))))
            ret_val.append((product, f_info))

        return ret_val

    def is_file_available(self, path_to_file):
        try:
            urlopen('{}/{}'.format(self.url,path_to_file))
        except HTTPError as e:
            log.warning('Could not retrieve file {} from server: Code {}'.format(path_to_file, e.code))
            return False
        except URLError as e:
            log.warning('Could not retrieve file {} from server: Code {}'.format(path_to_file, e.args))
            return False

        return True

    def get_build_info(self, builds, wanted_products, wanted_platform=None):
        ret_val = OrderedDict()

        for platform,build_info in builds.items():
            if wanted_platform:
                if platform != wanted_platform:
                    continue

            for product, files_info in build_info.items():
                if product in wanted_products:
                    if product == 'rootfs':
                        files = OrderedDict()
                        for type, fs in files_info.items():
                            for f in fs:
                                if self.is_file_available('rootfs/{}/{}'.format(type, f)):
                                    if files.get(type):
                                        files[type].append(f)
                                    else:
                                        files.update({type: [f]})
                    else:
                        files = [e for e in files_info if self.is_file_available('{}/{}/{}'.format(product, platform, e))]

                    if ret_val.get(platform):
                        ret_val[platform].update({
                            product:files
                        })
                    else:
                        ret_val.update({
                            platform: OrderedDict({
                                product:files
                            })
                        })

        return ret_val

    def get_builds_info(self, force_new=False):
        '''
        Get all built software.
        '''

        def get_json(buildername, build_num):
            json_path = 'json/builders/{}/builds/{}'.format(buildername, build_num)
            return self.__get_json_data(json_path)

        def get_from_flatten_list(flatten_list, what):
            for item in flatten_list:
                if item == what:
                    return flatten_list[flatten_list.index(item) + 1]

        class builds_info_helper():
            def __init__(self):
                self.builds = OrderedDict()

            def append_to_builds(self, platform, product, files):
                if platform and product and files:
                    if self.builds.get(platform):
                        if self.builds[platform].get(product):
                            self.builds[platform][product].extend(files)
                        else:
                            self.builds[platform].update({product: files})
                    else:
                        self.builds.update({platform: OrderedDict({product: files})})

            def append_to_rfsbuilds(self, platform, file_type, files):
                if platform and file_type and files:
                    if self.builds.get(platform):
                        if self.builds[platform].get('rootfs'):
                            if self.builds[platform]['rootfs'].get(file_type):
                                self.builds[platform]['rootfs'][file_type].extend(files)
                            else:
                                self.builds[platform]['rootfs'].update({file_type: files})
                        else:
                            self.builds[platform].update({
                                'rootfs': OrderedDict({file_type: files})
                            })
                    else:
                        self.builds.update({
                            platform: OrderedDict({
                                'rootfs': OrderedDict({
                                    file_type: files
                                })
                            })
                        })

        platforms = self.info['platforms']

        if not force_new:
            if self.info['builds']:
                return self.info['builds']

        if not platforms or force_new:
            platforms = self.get_platforms_info(force_new)

        builds = builds_info_helper()

        # get architectures from platforms and iterate through them
        for platform, arch in platforms:
            # Get all builders which contain the string of arch in it
            builders = ((x[0], x[1]['last_build']) for x in (
                    e for e in self.info['builders'] if arch == e[0]
            ))
            # get build information from builders
            for buildername, last_build in builders:
                for build_num in range(0,last_build + 1):
                    builds_info = get_json(buildername, build_num)

                    # only deal with build which are built succesfully
                    if builds_info.get('text') and builds_info['text'][0] == 'build' and builds_info['text'][1] == 'successful':
                        # flatten properties to a list with strings
                        props = [x for y in builds_info['properties'] for x in y]
                        cfg_platform = get_from_flatten_list(props, 'platform')

                        if cfg_platform in self.valid_platforms:
                            product = get_from_flatten_list(props, 'product')
                            files = get_from_flatten_list(props, 'upload_files')

                            builds.append_to_builds(platform, product, files)


            rootfs_builders = list(map(lambda x: (x[0], x[1]['last_build']),
                filter(lambda e: 'rootfs_{}'.format(arch) == e[0], self.info['builders'])
            ))

            for buildername, last_build in rootfs_builders:
                for build_num in range(0, last_build + 1):
                    builds_info = get_json(buildername, build_num)

                    # only deal with build which are built succesfully
                    if builds_info.get('text') and builds_info['text'][0] == 'build' and builds_info['text'][1] == 'successful':
                        # flatten properties to a list with strings
                        props = [x for y in builds_info['properties'] for x in y]
                        rootfs_name = get_from_flatten_list(props, 'platform')
                        files = get_from_flatten_list(props,  'upload_files')
                        builds.append_to_rfsbuilds(platform, rootfs_name, files)

        self.info['builds'] = builds.builds

        return builds.builds

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
                lambda x: (x, entry[0]),
                filter(
                    lambda p: p in self.configured_platforms,
                    entry[1]['schedulers']
                )
            )

            platforms.extend(result)

        self.info['platforms'] = platforms

        if self.dest:
            for arch, platform in platforms:
                if not self.local_platform_info.get(platform):
                    self.local_platform_info[platform] = arch

            json.dump(self.local_platform_info, open(self.json_file, 'w'))

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
        retVal = (info['basedir'], {'last_build': None, 'schedulers': []})

        for entry in info['schedulers']:
            splited_string = entry.split(' / ')
            if len(splited_string) == 3:
                if splited_string[0] == 'default':
                    scheduler = splited_string[2].split(': ')[1].strip('\'').strip('.*')
                    if scheduler in self.valid_platforms:
                        retVal[1]['schedulers'].append(scheduler)
                elif splited_string[0] == 'rootfs':
                    scheduler = splited_string[1].split(': ')[1]
                    retVal[1]['schedulers'].append(scheduler)

        if retVal[1]['schedulers']:
            arch = retVal[0]
            # get number of last build
            json_path = 'json/builders/{}/builds/-1'.format(arch)
            json_data = self.__get_json_data(json_path)
            retVal[1]['last_build'] = json_data['number']
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
            raise BuildserverConnectionError(
                'Can\'t get json data from server.' + Fore.RED + ' Info: {}'.format(e.message))

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

class LocalBuildsError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

class LocalBuilds():
    def __init__(self, path, configured_platforms):
        '''
        Interface for all builds at a given path.

        :param path: Local path where product builds are .
        '''
        path = path.rstrip('/')

        self.path = path

        self.configured_platforms = configured_platforms

        if not os.path.isdir(path):
            raise LocalBuildsError('Local directory "{}" does not exist.'.format(path))

        log.debug('Local directory path "{}" is valid.'.format(self.path))


    def get_builds_info(self, wanted_products, wanted_platform=None, force_new=False):
        # TODO: adapt to directory structure of buildbot server

        builds = OrderedDict()

        try:
            products = filter(lambda f: f in ['linux', 'misc', 'uboot'], next(os.walk(self.path))[1])
            rootfs = filter(lambda f: f in ['rootfs'], next(os.walk(self.path))[1])
            local_platform_info = json.load(open('{}/.platforms'.format(self.path)))
        except:
            print('An error occured while retrieving file from {}/.platforms'.format(self.path))
            raise

        for product in products:
            platforms = filter(lambda f: '.' not in f[0] and f in self.configured_platforms,
                               next(os.walk('{}/{}'.format(self.path, product)))[1])

            for platform in platforms:
                files = filter(lambda f: '.' not in f[0],
                               next(os.walk('{}/{}/{}'.format(self.path, product, platform)))[2])
                if builds.get(platform):
                    if builds[platform].get(product):
                        builds[platform][product].extend(files)
                    else:
                        builds[platform].update({product: files})
                else:
                    builds.update(
                        {platform: OrderedDict({product: files})}
                    )

        for r in rootfs:
            #TODO: go through directory structur
            pass