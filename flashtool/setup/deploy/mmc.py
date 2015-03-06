from __future__ import unicode_literals
from __future__ import print_function
from flashtool.setup.udev.mmc import get_device

__author__ = 'mahieke'

import flashtool.setup.udev.mmc as udev
from flashtool.setup.deploy import Deploy
import flashtool.utility as util
from flashtool.setup.constants import mkfs_support
from flashtool.setup.deploy.load import get_products_by_recipe_user_input
from flashtool.setup.deploy.load import set_root_password
from flashtool.setup.deploy.templateloader import fstab_info
from flashtool.setup.deploy.templateloader import generate_fstab
from flashtool.setup.deploy.templateloader import get_fstab_fstype

import re
from colorama import Fore
import parted
import _ped
import subprocess
import random
import ctypes
import hashlib
import os
from timeit import default_timer as timer
import tarfile

class MMCNotEnoughSpaceError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class MMCSectorsTestError(Exception):
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

        self.load_cfg = get_products_by_recipe_user_input(recipe, actions, builds, platform, auto)

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


def _check_disk(device):
    '''
    Does a check on the firs 1MB of the mmc device. This check must pass to make
    sure that the first 1MB of the device are valid.
    :param device: /dev path for the mmc device
    :return:
    '''
    print('Checking first MB of setup for errors...')
    file_size = 1024 * 1024
    data_chunk_builder = [0] * file_size

    print(Fore.YELLOW + '   Generating 1 MB Data: ', end="")
    start = timer()
    for t in range(0, file_size, 256):
        random.seed(t)
        data_chunk_builder[t] = random.randint(0, 255)

    data_chunk = bytearray((ctypes.c_ubyte * file_size)(*data_chunk_builder))

    hash = hashlib.md5(data_chunk)

    end = timer()
    print('{} seconds'.format(end - start))

    print(Fore.YELLOW + '   Writing 1MB of data to beginning of setup: ', end="")
    start = timer()
    fd = os.open(device, os.O_SYNC | os.O_WRONLY)
    os.write(fd, data_chunk)
    os.close(fd)
    end = timer()
    print('{} seconds'.format(end - start))

    read_data_chunk = ''
    print(Fore.YELLOW + '   Reading 1MB of data from setup: ', end="")
    start = timer()
    fd = os.open(device, os.O_SYNC | os.O_RDONLY)
    read_data_chunk = os.read(fd, file_size)
    os.close(fd)
    end = timer()
    print('{} seconds'.format(end - start))

    read_hash = hashlib.md5(read_data_chunk)

    cleaner = bytearray((ctypes.c_ubyte * file_size)(*[0] * file_size))

    fd = os.open(device, os.O_WRONLY)
    os.write(fd, cleaner)
    os.close(fd)

    if hash.hexdigest() != read_hash.hexdigest():
        raise MMCSectorsTestError('First Byte of {} seems to be broken'.format(device))
    else:
        print(Fore.GREEN + '   Everything seems fine!')

    print('')

def _get_free_regions(disk, align):
    """
    Source: https://gist.github.com/kergoth/4388948
    Get a filtered list of free regions, excluding the gaps due to partition alignment
    :param disk: parted disk object
    :param align: parted align object

    """
    regions = disk.getFreeSpaceRegions()
    new_regions = []
    for region in regions:
        if region.length > align.grainSize:
            new_regions.append(region)

    return new_regions

def _add_partition(disk, free, align=None, length=None, fs_type=None, type=parted.PARTITION_NORMAL):
    """
    Source: https://gist.github.com/kergoth/4388948
    :param disk: parted disk object
    :param free: list with parted geometry object which represent free coherent sectors
    :param align: parted alignment object
    :param length: length in sectors for the partition
    :param fs_type: file system type
    :param type: parted partition type
    :return: parted partition object for the created partition
    """
    start = free.start
    if length:
        end = start + length - 1
    else:
        end = free.end
        length = free.end - start + 1

    if not align:
        align = disk.partitionAlignment.intersect(disk.device.optimumAlignment)

    if not align.isAligned(free, start):
        start = align.alignNearest(free, start)

    end_align = parted.Alignment(offset=align.offset - 1, grainSize=align.grainSize)

    if not end_align.isAligned(free, end):
        end = end_align.alignNearest(free, end)

    geometry = parted.Geometry(disk.device, start=start, end=end)
    if fs_type:
        fs = parted.FileSystem(type=fs_type, geometry=geometry)
    else:
        fs = None

    partition = parted.Partition(disk, type=type, geometry=geometry, fs=fs)
    constraint = parted.Constraint(exactGeom=partition.geometry)
    disk.addPartition(partition, constraint)

    return partition

def _partition(dev, partition_table, partitions):
    '''
    Creates all partitions on a device which are defined in the recipe object
    :param dev: /dev path of the mmc device
    :return: data about the new partitions
    '''
    _dev = parted.getDevice(dev)
    _disk = parted.freshDisk(_dev, partition_table)

    _disk.deleteAllPartitions()

    print(Fore.YELLOW + '   Delete partitions from {}.'.format(dev))

    print(Fore.YELLOW + '   Set partition table to "{}"'.format(partition_table))

    name_feature_avail = _disk.getPedDisk().type.check_feature(_ped.DISK_TYPE_PARTITION_NAME)

    last_sector = _dev.length
    one_mb = 1024 * 1024
    sector_size = _dev.physicalSectorSize
    grain_size = int((1.0 / sector_size) * one_mb)  # 1 MB alignment

    align = parted.Alignment(offset=0, grainSize=grain_size)

    new_partitions = []
    print(Fore.YELLOW + '   Build partitions')
    for part_info in partitions:
        new_partitions.append({'path': part_info, 'fs_type': part_info.fs_type, 'name': part_info.name})

        free = _get_free_regions(_disk, align)[0]

        if part_info.size == 'max':
            _part = _add_partition(_disk, free)
        elif isinstance(part_info.size, float):
            sectors = int((free.end - free.start + 1) * part_info.size)
            _part = _add_partition(_disk, free, align, sectors, fs_type=part_info.fs_type)
        else:
            sectors = int(part_info.size / sector_size)
            _part = _add_partition(_disk, free, align, sectors, fs_type=part_info.fs_type)

        if name_feature_avail:
            _pedPart = _part.getPedPartition()
            _pedPart.set_name(part_info.name)

        if part_info.flags:
            if isinstance(part_info.flags, list):
                for flag in part_info.flags:
                    pedPartFlag = _ped.partition_flag_get_by_name(flag)
                    _part.setFlag(pedPartFlag)
            else:
                pedPartFlag = _ped.partition_flag_get_by_name(part_info.flags)
                _part.setFlag(pedPartFlag)

    _disk.commit()

    return new_partitions

def _format(partitions):
    '''
    Formats the new crated partition with the filesystem type which is specified in the recipe.
    :return: None
    '''
    for part_info in partitions:
        cmd = mkfs_support[part_info['fs_type']][0:-1]
        if part_info['name']:
            cmd = cmd + [mkfs_support[part_info['fs_type']][-1] + '{}'.format(part_info['name'])]

        cmd = cmd + [part_info['path']]
        print(Fore.YELLOW + '   Format command: {}'.format(' '.join(cmd)))
        util.os_call(cmd, allow_user_interrupt=False)

def get_load_info(partitions):
    '''
    Returns important information about the partitions for load step.
    :param partitions: list with dev-paths of the partitions
    :return: list with important information about partitions
    '''
    parts = [part.strip('/dev/') for part in partitions]
    return udev.get_information(parts)

__entry__ = MMCDeploy