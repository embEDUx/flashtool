from __future__ import unicode_literals
from __future__ import print_function

__author__ = 'mahieke'

import embedux_flashtool.setup.udev.mmc as udev
from embedux_flashtool.setup.deploy import Deploy
import embedux_flashtool.utility as util
from embedux_flashtool.setup.constants import mkfs_support

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
import zipfile
import shutil
import signal

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
        self.auto = auto
        self.builds = builds
        self.udev = _get_device()
        self.partition_info = None

        util.check_permissions(self.udev[0]['path'])
        build_info = self.builds.get_builds_info()
        yaml_info = {}
        self.load_cfg = {}

        # extract information for loading products to platform
        for product_name, values in recipe.load:
            if values.device:
                device_index = values.device

            prod = product_name.lower().split('_')
            product = prod[0]

            if product in actions:
                name = ''
                if len(prod) == 1:
                    name = product
                elif len(prod) == 2:
                    name = prod[1]

                reg_name = actions[product]

                if yaml_info.get(product):
                    yaml_info[product].update({
                        name: device_index
                    })
                else:
                    yaml_info.update({
                        product : {
                            'r_name': reg_name,
                            name: device_index
                        }
                    })

        load_order = ['rootfs', 'uboot', 'linux', 'misc']
        for product in load_order:
            if product not in yaml_info.keys():
                continue

            value = yaml_info[product]
            file_info = self.builds.get_build_info(build_info, [product], self.platform)
            file_types = [i for i in value.keys() if i != 'r_name']

            a = max(len(product),len(reg_name),len(', '.join(file_types)))

            print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))
            for s in [('product',product), ('reg_name', reg_name), ('file_types', ', '.join(file_types))]:
                st = '   | {:12}'.format(s[0] + ':') + '{:<' + str(a) + '} |'
                print(Fore.YELLOW + st.format(s[1]))

            print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))
            print('')

            files = self.builds.get_files_path(file_info, reg_name, [(product, file_types)], self.auto)[0][1]

            self.load_cfg[product] = []
            for f_type, file in files:
                self.load_cfg[product].append({
                    'f_type': f_type,
                    'device_index': value[f_type],
                    'file': file,
                    'size': int(self.builds.get_file_size(file))
                })

        sizes = []
        for entry in self.recipe['partitions']:
            if entry.size != 'max':
                sizes.append(int(entry.size))
            else:
                sizes.append(int(self.udev[0]['size']) - sum(sizes))

        # do file size check
        for product, values in self.load_cfg.items():
            for item in values:
                sizes[item['device_index']] -= item['size']

        not_enough_space = False
        i = 0
        for size in sizes:
            if size < 0:
                not_enough_space = True
                print(Fore.RED + 'There is not enough space on partition {}'.format(i))
            i += 1

        if not_enough_space:
            #TODO: raise an exception
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

        device = self.udev

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

        self.partition_info = _get_load_info([part.path.strip('/dev/') for part in partitions])

        print('')

    def load(self):
        '''
        Loads all needed files with the builds object and copies
        the files to the partitions of the mmc-device
        :return:
        '''
        print(Fore.YELLOW + '   +-{}-+'.format('-'*(17)))
        print(Fore.YELLOW + '   | {} |'.format('LOAD FILES ON MMC'))
        print(Fore.YELLOW + '   +-{}-+'.format('-'*(17)))
        print('')

        if not self.partition_info:
            self.partition_info = _get_load_info(self.info['udev'][1])

        # check if existing partitions match with recipe
        if len(self.partition_info) != len(self.recipe['partitions']):
            print(Fore.RED + 'Number of existing partitions does not meet with recipe configuration.')
            #TODO: raise a Exception
            exit(1)

        def mount(to_mount, dest_mount_point):
            # if device is not mounted, mount it
            try:
                os.makedirs(dest_mount_point)
            except OSError as e:
                pass
            print('   Mount {} to {}'.format(to_mount, dest_mount_point))
            util.os_call(['mount', to_mount, dest_mount_point], timeout=3)

        def umount():
            if mounted_devs:
                for k,v in mounted_devs.items():
                    print('   Umount {}'.format(k))
                    try:
                        util.os_call(['umount', k], allow_user_interrupt=False)
                    except Exception as e:
                        print(Fore.RED + '   {}'.format(e.message))
                        raise

        def load():
            configure_chain = self.load_cfg.keys()
            print('GET BUILD FILES {} FOR PLATFORM {}'.format(', '.join(configure_chain), self.platform).upper())
            print('')

            load_order = ['rootfs', 'uboot', 'linux', 'misc']

            for product in load_order:
                if product in configure_chain:
                    print(Fore.YELLOW + '  [{}]:'.format(product))
                    for f_info in self.load_cfg[product]:
                        done = False
                        while(not done):
                            try:
                                dest, size = self.builds.get_file(f_info['file'])
                            except Exception as e:
                                print(Fore.YELLOW + '   Error during Download process.')
                                print(Fore.RED    + '   {}'.format(repr(e)))
                                answer = util.user_prompt('   Do you want to retry the Download process?', '   Answer', 'YyNn')
                                if re.match('Y|y', answer):
                                    done = False
                                    os.remove(dest)
                                else:
                                    raise

                            if size == f_info['size']:
                                done = True
                            else:
                                print(Fore.YELLOW + '   File was not downloaded correctly')
                                answer = util.user_prompt('   Do you want to retry the Download process?', '   Answer', 'YyNn')
                                if re.match('Y|y', answer):
                                    done = False
                                    os.remove(dest)
                                else:
                                    raise KeyboardInterrupt

                        print('')

                        to_mount = self.partition_info[f_info['device_index']]['path']
                        dest_mount_point = '/tmp/flashtool/{}'.format(to_mount.split('/')[-1])

                        if not mounted_devs.get(to_mount):
                            mount(to_mount, dest_mount_point)
                            mounted_devs.update({
                                to_mount: dest_mount_point
                            })

                        #load file on partition
                        if tarfile.is_tarfile(dest):
                            print('   Extracting tar file {}'.format(dest))
                            util.untar(dest, dest_mount_point)
                        elif zipfile.is_zipfile(dest):
                            print('   Extracting zip file {}'.format(dest))
                        else:
                            print('   Copy file {} to mmc'.format(dest))
                            subprocess.call(['cp', dest, dest_mount_point])

        def rollback():
            subprocess.call('sync')
            try:
                umount()
            except Exception as e:
                print(Fore.RED + '   {}'.format(e.message))

        mounted_devs = {}
        try:
            load()
        except KeyboardInterrupt:
            print('')
            print(Fore.YELLOW + '   User interrupt procedure.')
            print(Fore.YELLOW + '   Rollback:')
            rollback()
            raise
        except Exception as e:
            print('')
            print(Fore.RED + '   An error occured:')
            print(Fore.RED + '   {}'.format(repr(e)))
            rollback()
            raise

        # umount
        print(Fore.YELLOW + '   Nearly finished. Syncing device...')
        subprocess.call('sync')
        print(Fore.YELLOW + '   Ready to umount devices...')
        umount()
        print(Fore.GREEN +  '   MMC setup DONE!')


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
        print(Fore.RED + '   {} seems to be broken'.format(device))
        print(Fore.RED + 'ABORT.')
        # TODO: raise Exception
        exit(1)
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
    def warn(a, b):
        print(Fore.RED + '   Interrupting format procedure is restricted!')

    for part_info in partitions:
        cmd = mkfs_support[part_info['fs_type']][0:-1]
        if part_info['name']:
            cmd = cmd + [mkfs_support[part_info['fs_type']][-1] + '{}'.format(part_info['name'])]

        cmd = cmd + [part_info['path']]
        print(Fore.YELLOW + '   Format command: {}'.format(' '.join(cmd)))

        s = signal.signal(signal.SIGINT, warn)
        process = subprocess.Popen(cmd, shell=False)
        process.wait()
        signal.signal(signal.SIGINT, s)

def _get_device(auto=False):
    '''
    Static method which tries to get the device information of a mmc device.
    If the system recognize multiple mmc devices the user is prompted to chose
    a device.
    :return: Returns a triple with device dev-path, size of device and list with
             all dev-path of the partitions
    '''
    memory_cards_info = udev.get_active_mmc_info()

    print('Found these devices:')

    devices = []

    i = 0
    for k, v in memory_cards_info.items():
        print('{}: {}'.format(i, k))
        print('    size: {} MB'.format(v['size'] / (1024 * 1024)))
        print('    part_table: {}'.format(v['part_table']))
        print('    partitions:')
        dev_partitions = []
        for kk, vv in v['partitions'].items():
            print('      {} ({}, {} MB)'.format(kk, vv['fs_type'], vv['size'] / (1024 * 1024)))
            dev_partitions.append(vv)

        devices.append(({'path': v['path'], 'size': v['size']}, dev_partitions))
        i += 1

    print('')

    selection = 0

    if len(devices) > 1:
        selection = int(util.user_select('Please select a device to continue:', 0, i))
        print('')

    if not auto:
        answer = util.user_prompt('Do you want to continue with setup process?', 'Answer', 'YyNn')
        if re.match('N|n', answer):
            print(Fore.GREEN + 'USER ABORTED SETUP PROCESS')
            #TODO: raise Exception
            exit(0)



    return devices[selection]

def _get_load_info(partitions):
    '''
    Returns important information about the partitions for load step.
    :param partitions: list with dev-paths of the partitions
    :return: list with important information about partitions
    '''
    parts = [part.strip('/dev/') for part in partitions]
    return udev.get_information(parts)

__entry__ = MMCDeploy