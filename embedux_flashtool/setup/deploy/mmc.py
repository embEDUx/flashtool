from __future__ import unicode_literals
from __future__ import print_function

__author__ = 'mahieke'

import embedux_flashtool.setup.udev.mmc as udev
from embedux_flashtool.setup.deploy import Deploy
from embedux_flashtool.setup.deploy import Load
from embedux_flashtool.setup.deploy import Prepare
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
import sys
import shutil

class MMCPrepare(Deploy, Prepare):
    def __init__(self, recipe):
        self.recipe = recipe
        self.new_partitions = []

    def run(self):
        device = self.get_device()

        print('')
        print('New Layout: ')
        i = 1
        for part in self.recipe.partitions:
            print('  partition {}: name: {}: (size: {}, fs: {})'.format(i, part.name, part.size, part.fs_type))
            i += 1

        print('')
        answer = util.user_prompt('Do you want to continue? This will overwrite the whole mmc device', 'Answer', "YyNn")

        if re.match("[Nn]", answer):
            print(Fore.RED + 'ABORT!')
            exit(0)

        util.check_permissions(device[0])

        self.__check_disk(device[0])

        self.__partition(device[0])

        partitions = parted.newDisk(parted.getDevice(device[0])).partitions

        for index in range(0, len(partitions)):
            self.new_partitions[index]['path'] = partitions[index].path

        self.__format()

        return self.get_load_info([part.path.strip('/dev/') for part in partitions])


    def __check_disk(self, device):
        print('Checking first MB of setup for errors...')
        file_size = 1024 * 1024
        data_chunk_builder = [0] * file_size

        print(Fore.YELLOW + 'Generating 1 MB Data: ', end="")
        start = timer()
        for t in range(0, file_size, 256):
            random.seed(t)
            data_chunk_builder[t] = random.randint(0, 255)

        data_chunk = bytearray((ctypes.c_ubyte * file_size)(*data_chunk_builder))

        hash = hashlib.md5(data_chunk)

        end = timer()
        print('{} seconds'.format(end - start))

        print(Fore.YELLOW + 'Writing 1MB of data to beginning of setup: ', end="")
        start = timer()
        fd = os.open(device, os.O_SYNC | os.O_WRONLY)
        os.write(fd, data_chunk)
        os.close(fd)
        end = timer()
        print('{} seconds'.format(end - start))

        read_data_chunk = ''
        print(Fore.YELLOW + 'Reading 1MB of data from setup: ', end="")
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
            print(Fore.RED + '{} seems to be broken'.format(device))
            print(Fore.RED + 'ABORT.')
            # TODO: raise Exception
            exit(1)
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
        _disk = parted.freshDisk(_dev, self.recipe.partition_table)

        _disk.deleteAllPartitions()

        # TODO: FIX LOGS DO NOT WORK WITH DYNAMIC IMPORT
        # log.info('Delete partitions from {}.'.format(dev))

        # log.info('Set partition table "{}"'.format(self.mmc.partition_table))

        name_feature_avail = _disk.getPedDisk().type.check_feature(_ped.DISK_TYPE_PARTITION_NAME)

        last_sector = _dev.length
        one_mb = 1024 * 1024
        sector_size = _dev.physicalSectorSize
        grain_size = int((1.0 / sector_size) * one_mb)  # 1 MB alignment

        align = parted.Alignment(offset=0, grainSize=grain_size)

        #log.info('Build partitions')
        for part_info in self.recipe.partitions:
            self.new_partitions.append({'path': part_info, 'fs_type': part_info.fs_type, 'name': part_info.name})

            free = self.__get_free_regions(_disk, align)[0]

            if part_info.size == 'max':
                _part = self.__add_partition(_disk, free)
            elif isinstance(part_info.size, float):
                sectors = int((free.end - free.start + 1) * part_info.size)
                _part = self.__add_partition(_disk, free, align, sectors, fs_type=part_info.fs_type)
            else:
                sectors = int(part_info.size / sector_size)
                _part = self.__add_partition(_disk, free, align, sectors, fs_type=part_info.fs_type)

            if name_feature_avail:
                _pedPart = _part.getPedPartition()
                _pedPart.set_name(part_info.name)

            if part_info.flags:
                if isinstance(part_info.flags, list):
                    for flag in part_info.flags:
                        pedPartFlag = _ped.partition_flag_get_by_name(part_info.flags)
                        _part.setFlag(pedPartFlag)
                else:
                    pedPartFlag = _ped.partition_flag_get_by_name(part_info.flags)
                    _part.setFlag(pedPartFlag)

        _disk.commit()


    def __format(self):
        for part_info in self.new_partitions:
            cmd = ['sudo'] + mkfs_support[part_info['fs_type']][0:-1]
            if part_info['name']:
                cmd = cmd + [mkfs_support[part_info['fs_type']][-1] + '{}'.format(part_info['name'])]

            cmd = cmd + [part_info['path']]

            subprocess.call(cmd)


    @staticmethod
    def get_device():
        memory_cards_info = udev.get_active_mmc_info()

        print('Found these devices:')

        devices = []
        dev_partitions = []

        for k, v in memory_cards_info.items():
            print(' {}:'.format(k))
            print('    size: {} MB'.format(v['size'] / (1024 * 1024)))
            print('    part_table: {}'.format(v['part_table']))
            print('    partitions:')
            for kk, vv in v['partitions'].items():
                print('      {} ({}, {} MB)'.format(kk, vv['fs_type'], vv['size'] / (1024 * 1024)))
                dev_partitions.append(vv)

            devices.append(v['path'])

        if len(devices) > 1:
            device = util.user_prompt('Please select a device to continue:', 'device', devices)
        else:
            device = devices[0]

        return device, [part['path'] for part in dev_partitions]

    @staticmethod
    def get_load_info(partitions):
        parts = [part.strip('/dev/') for part in partitions]
        return udev.get_information(parts)


class MMCLoad(Deploy, Load):
    def __init__(self, load_info, builds, platform, auto=False):
        '''
        Loads products to a platform
        :param load_info: contains all information where to put which product
        :param builds: object to get information about all built products
        :return: None
        '''
        self.devices = []
        self.sizes = []
        self.info = {}
        for k1,v1 in load_info.items():
            self.info[k1] = {
                'r_name': v1['r_name'],
                'files' : []
            }
            for k2,v2 in v1.items():
                if 'path' in v2:
                    if v2['path'] not in self.devices:
                        self.devices.append(v2['path'])
                    if v2['size'] not in self.sizes:
                        self.sizes.append(v2['size'])

                    self.info[k1]['files'].append({
                        'file_type': k2,
                        'device' : list(self.devices).index(v2['path'])
                    })

        for dev in self.devices:
            util.check_permissions(dev)

        self.builds = builds
        self.auto = auto
        self.platform = platform


    def run(self):
        '''

        :return:
        TODO: Check space on device with, size of partitions before all files were loaded.
        '''

        mounted_devs = {}

        def delete_files():
            for k,v in mounted_devs.items():
                target = v[0]
                files = os.listdir(target)
                print('   Delete extracted files from {}:'.format(target))
                for f in files:
                    file = '{}/{}'.format(target,f)
                    try:
                        if (os.path.isfile(file)):
                            os.remove(file)
                        else:
                            shutil.rmtree(file)
                    except KeyboardInterrupt:
                        print(Fore.RED + '   Abort deletion of files at {}'.format(target))
                        break
                    except Exception as e:
                        print(Fore.RED + '   Could not remove {}'.format(file))
                        print(Fore.RED + '   {}'.format(str(e)))
                        print('')


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

        def get_files(product, file_info):
            reg_name = self.info[product]['r_name']
            file_types = [i['file_type'] for i in self.info[product]['files']]

            a = max(len(product),len(reg_name),len(', '.join(file_types)))

            print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))
            for s in [('product',product), ('reg_name', reg_name), ('file_types', ', '.join(file_types))]:
                st = '   | {:12}'.format(s[0] + ':') + '{:<' + str(a) + '} |'
                print(Fore.YELLOW + st.format(s[1]))

            print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))
            print('')

            done = False

            while not done:
                files = self.builds.get_files_path(file_info, reg_name, [(product, file_types)], self.auto)
                done = True
                try:
                    loaded_files = self.builds.get_files(files)
                except Exception as e:
                    loaded_files = []
                    print(Fore.YELLOW + '   Error during Download process.')
                    print(Fore.RED    + '   {}'.format(repr(e)))
                    answer = util.user_prompt('   Do you want to retry the Download process?', '   Answer', 'YyNn')
                    if re.match('Y|y', answer):
                        done = False

            return loaded_files

        def load(product, build_info):
            file_info = self.builds.get_build_info(build_info, [product], self.platform)
            files = get_files(product, file_info)
            sys.stdout.flush()

            print('')
            load_info = [i for i in self.info[product]['files']]
            for info in load_info:
                file_source, file_size = next(((item[1], item[2]) for item in files if item[0] == info['file_type']))
                to_mount = self.devices[info['device']]
                dev_size = self.sizes[info['device']]
                dest_mount_point = '/tmp/flashtool/{}'.format(to_mount.split('/')[-1])

                if not mounted_devs.get(to_mount):
                    mount(to_mount, dest_mount_point)
                    mounted_devs.update({
                        to_mount: [dest_mount_point, dev_size - file_size]
                    })
                else:
                    mounted_devs[to_mount][1] -= file_size
                    if not mounted_devs[to_mount][1] >= 0:  # enough free space on partition
                        print(Fore.RED + '   There is not enough space on partition {}.'.format(to_mount))
                        print(Fore.RED + '   ROLLBACK:')
                        delete_files()
                        umount()
                        # TODO: raise exception
                        exit(1)

                #load file on partition
                if tarfile.is_tarfile(file_source):
                    print('   Extracting tar file {}'.format(file_source))
                    util.untar(file_source, dest_mount_point)
                elif zipfile.is_zipfile(file_source):
                    print('   Extracting zip file {}'.format(file_source))
                else:
                    print('   Copy file {} to mmc'.format(file_source))
                    subprocess.call(['cp', file_source, dest_mount_point])


        configure_chain = self.info.keys()
        print('GET BUILD FILES {} FOR PLATFORM {}'.format(', '.join(configure_chain), self.platform).upper())
        print('')

        build_info = self.builds.get_builds_info()

        load_order = ['rootfs', 'uboot', 'linux', 'misc']

        def rollback():
            delete_files()
            subprocess.call('sync')
            try:
                umount()
            except Exception as e:
                print(Fore.RED + '   {}'.format(e.message))


        try:
            for product in load_order:
                if product in configure_chain:
                    load(product, build_info)
                    print('')
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



__classes__ = MMCPrepare, MMCLoad