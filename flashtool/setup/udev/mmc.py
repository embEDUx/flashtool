import re
from colorama import Fore
from flashtool import utility as util

__author__ = 'mahieke'

import logging as log
import flashtool.utility as util
from functools import partial
from pyudev import Context
from pyudev import Device
from pyudev import Monitor
from collections import OrderedDict

def get_info(dev, indent=0):
    form = '{:' + str(indent) + '}{} = {}'
    for key in dev:
        print(form.format('', key, dev.get(key)))

    print('')


def get_active_mmc_info():
    '''
    Tries to get information about a plugged in mmc device. The user
    receives instructions to plug in the mmc device when the tool is ready
    for recognition.

    :return: Information for Block devices
    '''
    def get_childs_info(udev_device):
        info = {}

        for child in udev_device.children:
            info[child.sys_name] = {
                'path': child.device_node,
                'size': util.get_size_block_dev(udev_device.sys_name, child.sys_name),
                'fs_type': child.get('ID_FS_TYPE'),
                'fs_version': child.get('ID_FS_VERSION')
            }

        return OrderedDict(sorted(info.items()))

    info = OrderedDict()

    util.user_prompt('Please remove the Flash Card first', 'Done?')

    print('Searching for Flash Card. Please insert Flash Card...')

    while True:
        guessed_devices = MMCProfiler().guess()
        guessed_devices = _get_real_block_devices(guessed_devices)

        if guessed_devices:
            break

    log.debug('GET ALL PARTITIONS OF DEVICES {}'.format(', '.join(guessed_devices)))

    for device in guessed_devices:
        udev_device = Device.from_name(Context(), 'block', device)
        info[device] = OrderedDict({
            'path': udev_device.device_node,
            'part_table': udev_device.get('ID_PART_TABLE_TYPE'),
            'size': util.get_size_block_dev(udev_device.sys_name),
            'partitions': OrderedDict()
        })
        info[device]['partitions'].update(get_childs_info(udev_device))

    return info

def _get_real_block_devices(guessed_devices):
    '''
    Filters entries in the list with possible block devices
    when they are not a block device.

    :param guessed_devices: list of possible block devices
    :return: list with valid block devices
    '''
    real_block_device = []
    for dev in guessed_devices:
        if util.get_size_block_dev(dev) != 0:
            log.debug('DEVICE {} SHOULD BE A BLOCK DEVICE!'.format(dev))
            real_block_device.append(dev)

    return real_block_device

def get_partition_information(devices):
    '''
    Retrieves important information about the partitions of
    a block device.

    Information:
        path: path to /dev device of the partition
        size: size of the partition
        fs_type: filesystem type of a partition
        fs_version: filesystem version
        name: partition label
        uuid: uuid of the partition

    :param devices: list of block devices
    :return: List with information for a device
    '''
    info = []

    for dev in devices:
        udev_device = Device.from_name(Context(), 'block', dev)
        info.append({
                'path': udev_device.device_node,
                'size': util.get_size_block_dev(udev_device.parent.sys_name, udev_device.sys_name),
                'fs_type': udev_device.get('ID_FS_TYPE'),
                'fs_version': udev_device.get('ID_FS_VERSION'),
                'name': udev_device.get('ID_FS_LABEL', None),
                'uuid': udev_device.get('ID_FS_UUID', None)
        })

    return info

def get_mmc_device(auto=False):
    '''
    Function which tries to get the device information of a mmc device.
    If the system recognize multiple mmc devices the user is prompted to chose
    a device.

    :param auto: decide if user should be asked for continuing the setup process
    :return: Returns a triple with device dev-path, size of device and list with
             all dev-paths of the partitions
    '''
    memory_cards_info = get_active_mmc_info()

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
            exit(0)

    util.check_permissions(devices[selection][0]['path'])
    ensure_unmounted([child['path'] for child in devices[selection][1]])

    return devices[selection]

def ensure_unmounted(devs):
    '''
    Unmount the partitions which are given by in parameter devs.
    The function will call the umount command as often as the device
    is listed in /proc/mounts.

    :param devs: list with /dev paths of partitions
    :return: None
    '''
    for path in devs:
        for line in open("/proc/mounts"):
            if path in line:
                print('Device {} was mounted:'.format(path))
                util.os_call(['umount', path])
                print(' --> umount')

class MMCProfiler(object):
    def __init__(self):
        '''
        Class which is able to guess the right *mmc* device when plugged in.
        '''
        context = Context()
        monitor_mmc = Monitor.from_netlink(context)
        monitor_mmc.filter_by(subsystem='block', device_type='disk')

        self.__cnt = {'add':{}, 'change':{}}

        for action, device in monitor_mmc:
            if action in ['add', 'change']:
                self.__count(action, device)
                break

        for device in iter(partial(monitor_mmc.poll, 1), None):
            if action in ['add', 'change']:
                self.__count(action,device)



    def __count(self, action, device):
        if device.sys_name in self.__cnt[action]:
            self.__cnt[action][device.sys_name] += 1
        else:
            self.__cnt[action][device.sys_name] = 1

    def guess(self):
        '''
        Method which guesses the mmc device due to the recorded udev events.

        :return: a list with all possible mmc devices
        '''
        devname = list()

        log.debug('STATISTIC OF CHANGE AND ADD EVENTS: {}'.format(self.__cnt))

        if self.__cnt['add'] == {}: # Use-Case 1
            devname = list(self.__cnt['change'].keys())
        elif self.__cnt['change'] == {}: # Use-Case 4
            devname = list(self.__cnt['add'].keys())
        elif list(self.__cnt['add'].values())[1:] == list(self.__cnt['add'].values())[:-1]:
            diff = set(list(self.__cnt['add'].keys())) - set(list(self.__cnt['change'].keys()))
            if  diff == set([]): # Use-Case 2
                maximum = max(self.__cnt['add'].values())
                devname = [k for k,v in self.__cnt.items() if v == maximum]
            else: # Use-Case 3
                devname = diff
        else:
            devname = set(list(self.__cnt['add'].keys())) * set(list(self.__cnt['change'].keys()))
            log.critical('EVENTS DO NOT MEET HEURISTIC INFORMATION, FALLBACK MODE CHECK ALL DEVICES WHICH CREATED AN EVENT!!')

        log.debug('GUESSING FOLLOWING DEVICES BY HEURISTICS: {}'.format(', '.join(devname)))

        return devname


