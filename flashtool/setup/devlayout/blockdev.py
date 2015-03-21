import _ped
import ctypes
import hashlib
import os
import random
from timeit import default_timer as timer
from colorama import Fore
import parted
from flashtool import utility as util
from flashtool.setup.constants import mkfs_support

__author__ = 'mahieke'


class BlockDevSectorsTestError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

def partition(dev, partition_table, partitions):
    '''
    Creates all partitions on a device which are defined in the recipe object
    :param dev: /dev path of the mmc device
    :return: data about the new partitions
    '''
    _dev = parted.getDevice(dev)
    _disk = parted.freshDisk(_dev, partition_table)

    _disk.deleteAllPartitions()

    print(Fore.YELLOW + '   Delete partitions from {}.'.format(dev))

    print(Fore.YELLOW + '   Set devlayout table to "{}"'.format(partition_table))

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


def check_disk(device):
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
        raise BlockDevSectorsTestError('First Byte of {} seems to be broken'.format(device))
    else:
        print(Fore.GREEN + '   Everything seems fine!')

    print('')


def _get_free_regions(disk, align):
    """
    Source: https://gist.github.com/kergoth/4388948
    Get a filtered list of free regions, excluding the gaps due to devlayout alignment
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
    :param length: length in sectors for the devlayout
    :param fs_type: file system type
    :param type: parted devlayout type
    :return: parted devlayout object for the created devlayout
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


def format(partitions):
    '''
    Formats the new crated devlayout with the filesystem type which is specified in the recipe.
    :return: None
    '''
    for part_info in partitions:
        cmd = mkfs_support[part_info['fs_type']][0:-1]
        if part_info['name']:
            cmd = cmd + [mkfs_support[part_info['fs_type']][-1] + '{}'.format(part_info['name'])]

        cmd = cmd + [part_info['path']]
        print(Fore.YELLOW + '   Format command: {}'.format(' '.join(cmd)))
        util.os_call(cmd, allow_user_interrupt=False)