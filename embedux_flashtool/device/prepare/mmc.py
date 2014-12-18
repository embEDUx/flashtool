from __future__ import unicode_literals
from __future__ import print_function

__author__ = 'mahieke'

from embedux_flashtool.device.udev.mmc import MMC
from embedux_flashtool.device.prepare import recipe
from embedux_flashtool.device.prepare import runnable
from embedux_flashtool.device.prepare import RecipeContentException
import embedux_flashtool.utility as util

import re
from logging import log
from colorama import Fore
import parted
import _ped
import subprocess
import random
import ctypes
import hashlib
import os
from timeit import default_timer as timer

LINUX_PARTITION = 131

mkfs_support = {
    'fat32': ['mkfs.fat', '-F32', '-n '],
    'ext4': ['mkfs.ext4', '-F', '-L '],
    'ext2': ['mkfs.ext2', '-F', '-L '],
    'btrfs': ['mkfs.btrfs', '-f', '-L ']
}

class mmc(recipe, runnable):
    attr = ['partitions', 'partition_table']

    def __init__(self, attributes):
        parts = []
        has_max_size = False
        for elem in attributes['partitions']:
            part = partition(elem)
            if part.size == max:
                if has_max_size:
                    raise RecipeContentException('Only one partition can set the max flag for size.')
                has_max_size = True

            parts.append(part)

        # Only the last partition is allowed to state the max flag for the size
        if has_max_size:
            if parts[-1].size != max:
                raise RecipeContentException('Only the last partition can state the max flag for size.')

        attributes['partitions'] = parts
        self.check_attributes(attributes)
        recipe.__init__(self, attributes)
        self.__check_partition_table(self.partition_table)


    def run(self):
        memory_cards_info = MMC().get_mmc_info()

        print('Found these devices:')

        self.devices = []
        self.dev_partitions = []
        self.new_partitions = []

        for k, v in memory_cards_info.items():
            print(' {}:'.format(k))
            print('    size: {} MB'.format(v['size'] / (1024 * 1024)))
            print('    part_table: {}'.format(v['part_table']))
            print('    partitions:')
            for kk, vv in v['partitions'].items():
                print('      {} ({}, {} MB)'.format(kk, vv['fs_type'], vv['size'] / (1024 * 1024)))
                self.dev_partitions.append(vv)

            self.devices.append(v['path'])

        if len(self.devices) > 1:
            device = util.user_prompt('Please select a device to continue:', 'device', self.devices)
        else:
            device = self.devices[0]

        print('')
        print('New Layout: ')
        i = 1
        for part in self.partitions:
            print('  partition {}: name: {}: (size: {}, fs: {})'.format(i, part.name, part.size, part.fs_type))
            i += 1

        answer = util.user_prompt('Do you want to continue? This will overwrite the whole mmc device', 'Answer', "YyNn")

        if re.match("[Nn]", answer):
            print(Fore.RED + 'ABORT!')
            return

        util.check_permissions(device)

        self.__check_disk(device)

        self.__partition(device)

        partitions = parted.newDisk(parted.getDevice(device)).partitions

        for index in range(0, len(partitions)):
            self.new_partitions[index]['path'] = partitions[index].path

        self.__format()

        memory_cards_info = MMC().get_information([part.path.strip('/dev/') for part in partitions])

        return memory_cards_info

    def __check_disk(self, device):
        print('Checking first MB of device for errors...')
        file_size = 1024*1024
        data_chunk_builder = [0]*file_size

        print(Fore.YELLOW + 'Generating 1 MB Data: ', end="")
        start = timer()
        for t in range(0, file_size, 256):
            random.seed(t)
            data_chunk_builder[t] = random.randint(0,255)

        data_chunk = bytearray((ctypes.c_ubyte*file_size)(*data_chunk_builder))

        hash = hashlib.md5(data_chunk)

        end = timer()
        print('{} seconds'.format(end-start))


        print(Fore.YELLOW + 'Writing 1MB of data to beginning of device: ', end="")
        start = timer()
        fd = os.open(device, os.O_SYNC | os.O_WRONLY)
        os.write(fd, data_chunk)
        os.close(fd)
        end = timer()
        print('{} seconds'.format(end-start))

        read_data_chunk = ''
        print(Fore.YELLOW + 'Reading 1MB of data from device: ', end="")
        start = timer()
        fd = os.open(device, os.O_SYNC | os.O_RDONLY)
        read_data_chunk = os.read(fd,file_size)
        os.close(fd)
        end = timer()
        print('{} seconds'.format(end-start))

        read_hash = hashlib.md5(read_data_chunk)

        cleaner = bytearray((ctypes.c_ubyte*file_size)(*[0]*file_size))

        fd = os.open(device,os.O_WRONLY)
        os.write(fd, cleaner)
        os.close(fd)

        if hash.hexdigest() != read_hash.hexdigest():
            print(Fore.RED + '{} seems to be broken'.format(device))
            print(Fore.RED + 'ABORT.')
        else:
            print(Fore.GREEN + 'Everything seems fine!')


    def __get_free_regions(self, disk, align):
        """
        Source: https://gist.github.com/kergoth/4388948
        Get a filtered list of free regions, excluding the gaps due to partition alignment
        :param disk:
        :param align:

        """
        regions = disk.getFreeSpaceRegions()
        new_regions = []
        for region in regions:
            if region.length > align.grainSize:
                new_regions.append(region)

        return new_regions

    def __add_partition(self, disk, free, align=None, length=None, fs_type=None, type=parted.PARTITION_NORMAL):
        """
        Source: https://gist.github.com/kergoth/4388948
        :param disk:
        :param free:
        :param align:
        :param length:
        :param fs_type:
        :param type:
        :return:
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


    def __partition(self, dev):
        _dev = parted.getDevice(dev)
        _disk = parted.freshDisk(_dev, self.partition_table)

        _disk.deleteAllPartitions()

        #TODO: FIX LOGS DO NOT WORK WITH DYNAMIC IMPORT
        #log.info('Delete partitions from {}.'.format(dev))

        #log.info('Set partition table "{}"'.format(self.partition_table))

        name_feature_avail = _disk.getPedDisk().type.check_feature(_ped.DISK_TYPE_PARTITION_NAME)

        last_sector = _dev.length
        one_mb = 1024 * 1024
        sector_size = _dev.physicalSectorSize
        grain_size = int((1.0 / sector_size) * one_mb)  # 1 MB alignment

        align = parted.Alignment(offset=0, grainSize=grain_size)

        #log.info('Build partitions')
        for part_info in self.partitions:
            self.new_partitions.append({'path': part_info, 'fs_type': part_info.fs_type, 'name': part_info.name})

            free = self.__get_free_regions(_disk, align)[0]

            if part_info.size == 'max':
                _part = self.__add_partition(_disk, free)
            elif isinstance(part_info.size, float):
                sectors = int((free.end - free.start + 1) * part_info.size)
                _part = self.__add_partition(_disk, free, align, sectors, fs_type=part_info.fs_type)
            else:
                sectors = part_info.size / sector_size
                _part = self.__add_partition(_disk, free, align, sectors, fs_type=part_info.fs_type)

            if name_feature_avail:
                _pedPart = _part.getPedPartition()
                _pedPart.set_name(part_info.name)

            if part_info.flags:
                try:
                    if isinstance(part_info.flags, list):
                        for flag in part_info.flags:
                            pedPartFlag = _ped.partition_flag_get_by_name(part_info.flags)
                            _part.setFlag(pedPartFlag)
                    else:
                        pedPartFlag = _ped.partition_flag_get_by_name(part_info.flags)
                        _part.setFlag(pedPartFlag)
                except _ped.PartitionException as e:
                    raise RecipeContentException('Could not set flag "{}" for partition {}:\nmsg: {}'.
                                                 format(_ped.partition_flag_get_name(pedPartFlag), part_info.name,
                                                        e.message))

        _disk.commit()

    def __format(self):
        for part_info in self.new_partitions:
            cmd = ['sudo'] + mkfs_support[part_info['fs_type']][0:-1]
            if part_info['name']:
                cmd = cmd + [ mkfs_support[part_info['fs_type']][-1] + '{}'.format(part_info['name']) ]

            cmd = cmd + [part_info['path']]

            subprocess.call(cmd)

    def __check_partition_table(self, part_table):
        try:
            _ped.disk_type_get(part_table)
        except _ped.UnknownTypeException:
            raise RecipeContentException('Partition table {} stated in document is not supported!'.format(part_table))


class partition(recipe):
    attr = ['name', 'size', 'fs_type', 'mount_point', 'mount_opts', 'flags']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        if attributes['size'] != 'max':
            attributes['size'] = self.__to_byte(attributes['size'])
        attributes['name'] = attributes['name'].upper()

        recipe.__init__(self, attributes)
        self.__check_fs_type(self.fs_type)
        self.__check_partition_flag(self.flags)

    def __check_fs_type(self, fs_type):
        try:
            if not util.shutil_which(mkfs_support[fs_type][0]):
                raise RecipeContentException(
                    'Filesystem type {0} is not supported on your system. (mkfs.{0} needed)'.format(fs_type))
        except KeyError:
            raise RecipeContentException(
                    'Filesystem type {0} is not supported.'.format(fs_type))

    def __check_partition_flag(self, flags):
        if flags:
            if isinstance(flags, list):
                for flag in flags:
                    if _ped.partition_flag_get_by_name(flag) == 0L:
                        raise RecipeContentException('Flag {} for partition {} is not valid.'.format(flag, self.name))
            else:
                if _ped.partition_flag_get_by_name(flags) == 0L:
                    raise RecipeContentException('Flag {} for partition {} is not valid.'.format(flags, self.name))


    def __to_byte(self, string):
        types = {re.compile('[0-9]+%$'): 0.01,
                 re.compile('[0-9]+$'): 1L,
                 re.compile('[0-9]+(kb|kB|KB|Kb)$'): 1024L,
                 re.compile('[0-9]+(mb|mB|MB|Mb)$'): 1024L * 1024L,
                 re.compile('[0-9]+(gb|gB|GB|Gb)$'): 1024L * 1024L * 1024L,
                 re.compile('[0-9]+(tb|tB|TB|Tb)$'): 1024L * 1024L * 1024L * 1024L
        }

        value = 0

        for k, v in types.items():
            if k.match(string):
                value = v * int(re.findall('[0-9]+', string)[0])
                break

        if value != 0:
            if isinstance(value, float) and value > 1.0:
                raise  RecipeContentException(
                'Partition size is not valid. Percentage must range between 1% to 100%. Given value: "{}"'.format(string))
            return value
        else:
            raise RecipeContentException(
                'Partition size is not valid. Given value: "{}", Allowed: #num( ,%,kb,mb,gb,tb)'.format(string))

__entry__ = mmc