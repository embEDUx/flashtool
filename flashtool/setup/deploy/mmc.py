from __future__ import unicode_literals
from __future__ import print_function
from flashtool.setup.partition.blockdev import _partition, _check_disk, _format

__author__ = 'mahieke'

import flashtool.setup.udev.mmc as udev
from flashtool.setup.deploy import Deploy
import flashtool.utility as util
from flashtool.setup.deploy.load import get_products_by_recipe_user_input
from flashtool.setup.deploy.load import set_root_password
from flashtool.setup.deploy.templateloader import fstab_info
from flashtool.setup.deploy.templateloader import generate_fstab
from flashtool.setup.deploy.templateloader import get_fstab_fstype

import re
from colorama import Fore
import parted
import subprocess
import os
import tarfile

class MMCNotEnoughSpaceError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class MMCRecipeMatchError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class MMCDeploy(Deploy):
    '''
    This class represents all needed steps setting up a mmc device.
    '''
    def __init__(self, recipe, actions, builds, platform, auto):
        # get information from recipe
        self.recipe = {
            'partition_table': recipe.partition_table,
            'partitions': recipe.partitions
        }

        self.platform = platform
        self.builds = builds
        self.auto = auto
        self.__udev = udev.get_device()
        self.__partition_info = None
        self.__mounted_devs = {}

        self.load_cfg = get_products_by_recipe_user_input(recipe.load, actions, builds, platform, auto)

        sizes = [1024*1024]
        for entry in self.recipe['partitions']:
            if entry.size != 'max':
                sizes.append(int(entry.size))
            else:
                sizes.append(int(self.__udev[0]['size']) - sum(sizes))

        # do file size check
        for product, values in self.load_cfg.items():
            for item in values:
                if item['yaml'].device is not None:
                    sizes[item['yaml'].device + 1] -= item['size']
                elif item['yaml'].command is not None:
                    t_str = item['yaml'].command[1]
                    num = t_str.split('device')[1][0]
                    if isinstance(num, int):
                        sizes[int(num) + 1] -= item['size']
                    else:
                        sizes[0] -= item['size']

        not_enough_space = False
        i = 0
        for size in sizes:
            if size < 0:
                not_enough_space = True
                print(Fore.RED + 'There is not enough space on partition {}'.format(i))
            i += 1

        if not_enough_space:
            raise MMCNotEnoughSpaceError()
            exit(0)

    def prepare(self):
        '''
        Method will prepare the mmc device by following the recipe.
        :return: A list with information about the paritions.
        '''

        print(Fore.YELLOW + '   +-{}-+'.format('-'*(11)))
        print(Fore.YELLOW + '   | {} |'.format('PREPARE MMC'))
        print(Fore.YELLOW + '   +-{}-+'.format('-'*(11)))
        print('')

        device = self.__udev

        print('New Layout: ')
        i = 1
        for part in self.recipe['partitions']:
            print('  partition {}: name: {}: (size: {}, fs: {})'.format(i, part.name, part.size, part.fs_type))
            i += 1

        print('')
        answer = util.user_prompt('Do you want to continue? This will overwrite the whole mmc device', 'Answer', "YyNn")

        if re.match("[Nn]", answer):
            print(Fore.RED + 'ABORT!')
            exit(0)

        _check_disk(device[0]['path'])

        new_partitions = _partition(device[0]['path'], self.recipe['partition_table'], self.recipe['partitions'])

        partitions = parted.newDisk(parted.getDevice(device[0]['path'])).partitions

        for index in range(0, len(partitions)):
            new_partitions[index]['path'] = partitions[index].path

        print(Fore.YELLOW + '   Format partitions {}:'.format(', '.join([p['path'] for p in new_partitions])))
        _format(new_partitions)

        self.__partition_info = device[0]['path'], get_load_info([part.path for part in partitions])

        print('')

    def load(self):
        '''
        Loads all needed files with the builds object and copies
        the files to the partitions of the mmc-device
        :return:
        '''
        print(Fore.YELLOW + '   +-{}-+'.format('-'*17))
        print(Fore.YELLOW + '   | {} |'.format('LOAD FILES ON MMC'))
        print(Fore.YELLOW + '   +-{}-+'.format('-'*17))
        print('')

        if not self.__partition_info:
            self.__partition_info = self.__udev[0]['path'], get_load_info([part['path'] for part in self.__udev[1]])

        # check if existing partitions match with recipe
        if len(self.__partition_info[1]) != len(self.recipe['partitions']):
            raise MMCRecipeMatchError('Number of existing partitions does not meet with recipe configuration.')
        try:
            self.__do_load()
            self.finish_deployment()
        except KeyboardInterrupt:
            print('')
            print(Fore.YELLOW + '   User interrupt procedure.')
            print(Fore.YELLOW + '   Rollback:')
            self.__rollback()
            raise
        except Exception as e:
            print('')
            print(Fore.RED + '   An error occured:')
            print(Fore.RED + '   {}'.format(str(e)))
            self.__rollback()
            raise

    def __do_load(self):
        fstab = fstab_info()

        for parts in self.recipe['partitions']:
            name = parts.name
            for item in self.__partition_info[1]:
                fs_type = get_fstab_fstype(parts.fs_type)
                item_name = item['name']
                if item_name == name or item_name == name.upper():
                    fstab.append({
                        'uuid': 'UUID={}'.format(item['uuid']),
                        'mountpoint': parts.mount_point,
                        'type': fs_type,
                        'options': parts.mount_opts,
                        'dump': 0,
                        'pas': 0
                    })

        configure_chain = self.load_cfg.keys()
        print('GET BUILD FILES {} FOR PLATFORM {}'.format(', '.join(configure_chain), self.platform).upper())
        print('')

        load_order = ['rootfs', 'uboot', 'linux', 'misc']

        for product in load_order:
            if product in configure_chain:
                print(Fore.YELLOW + '  [{}]:'.format(product))
                for f_info in self.load_cfg[product]:
                    done = False
                    while not done:
                        try:
                            src, size = self.builds.get_file(f_info['file'])
                        except Exception as e:
                            print(Fore.YELLOW + '   Error during Download process.')
                            print(Fore.RED    + '   {}'.format(repr(e)))
                            answer = util.user_prompt('   Do you want to retry the Download process?', '   Answer', 'YyNn')
                            if re.match('Y|y', answer):
                                done = False
                            else:
                                raise

                        if size == f_info['size']:
                            done = True
                        else:
                            print(Fore.YELLOW + '   File was not downloaded correctly')
                            answer = util.user_prompt('   Do you want to retry the Download process?', '   Answer', 'YyNn')
                            if re.match('Y|y', answer):
                                done = False
                            else:
                                raise KeyboardInterrupt

                    print('')

                    if f_info['yaml'].device is not None:
                        to_mount = self.__partition_info[1][f_info['yaml'].device]['path']
                        dest = '/tmp/flashtool/{}'.format(to_mount.split('/')[-1])

                        if not self.__mounted_devs.get(to_mount):
                            self.__mount(to_mount, dest)
                            self.__mounted_devs.update({
                                to_mount: dest
                            })

                        # load file on partition
                        if tarfile.is_tarfile(src):
                            print('   Extracting tar file {}'.format(src))
                            util.untar(src, dest)
                        else:
                            print('   Copy file {} to mmc'.format(src))
                            subprocess.call(['cp', src, dest])

                        if product == 'rootfs':
                            tab_dev = to_mount
                    else: # there is a command specified
                        from string import Template
                        dest = '/tmp/flashtool'
                        if tarfile.is_tarfile(src):
                            tar = tarfile.open(src, 'r')
                            if len(list(tar.getmembers())) != 1:
                                print(Fore.Red + '   Tar file has not exactly one member. Can\'t decide which file should be'
                                      'loaded via dd command')
                                raise Exception('   Requirements were not met.')
                            file_name = '{}/{}'.format(dest, tar.getmembers()[0].name)
                            tar.close()
                            print('   Extracting tar file {}'.format(src))
                            util.untar(src, dest)
                        else:
                            file_name = src

                        t_str = f_info['yaml'].command[1]
                        num = t_str.split('device')[1][0]
                        if isinstance(num, int):
                            dev = self.__partition_info[1][int(num)]['path']
                            t_str = re.sub('device[0-9]+', 'device', f_info['yaml'].command[1])
                        else:
                            dev = self.__partition_info[0]

                        cmd = [f_info['yaml'].command[0]] + Template(t_str).safe_substitute(file=file_name, device=dev).split()
                        print('   Execute command: {}'.format(' '.join(cmd)))
                        subprocess.call(cmd)
                        os.remove(file_name)
                        if product == 'rootfs':
                            tab_dev = dev

                    print('')

        if tab_dev:
            tab_dest = '/tmp/flashtool/{}'.format(tab_dev.split('/')[-1])
            if not self.__mounted_devs.get(tab_dev):
                self.__mount(tab_dev, tab_dest)
                self.__mounted_devs.update({
                    tab_dev: tab_dest
                })

            generate_fstab(fstab, tab_dest)

        set_root_password('/tmp/flashtool/{}'.format(tab_dev.split('/')[-1]))

    def finish_deployment(self):
        print(Fore.YELLOW + '   Nearly finished. Syncing device...')
        subprocess.call('sync')
        print(Fore.YELLOW + '   Ready to umount devices...')
        self.__umount()
        print(Fore.GREEN + '   MMC setup DONE!')

    def __mount(self, to_mount, dest_mount_point):
        # if device is not mounted, mount it
        try:
            os.makedirs(dest_mount_point)
        except OSError as e:
            pass
        print('   Mount {} to {}'.format(to_mount, dest_mount_point))
        util.os_call(['mount', to_mount, dest_mount_point], timeout=15)

    def __umount(self):
        if self.__mounted_devs:
            for k,v in self.__mounted_devs.items():
                print('   Umount {}'.format(k))
                try:
                    util.os_call(['umount', k], allow_user_interrupt=False)
                except Exception as e:
                    print(Fore.RED + '   {}'.format(e.message))
                    raise

    def __rollback(self):
        print(Fore.YELLOW + '   Syncing devices...')
        subprocess.call('sync')
        try:
            self.__umount()
        except Exception as e:
            print(Fore.RED + '   {}'.format(e.message))



def get_load_info(partitions):
    '''
    Returns important information about the partitions for load step.
    :param partitions: list with dev-paths of the partitions
    :return: list with important information about partitions
    '''
    parts = [part.strip('/dev/') for part in partitions]
    return udev.get_information(parts)

__entry__ = MMCDeploy