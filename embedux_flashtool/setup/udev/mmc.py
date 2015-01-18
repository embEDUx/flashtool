__author__ = 'mahieke'

import logging as log
import embedux_flashtool.utility as util
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

    guessed_devices = guess_devices()

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
    real_block_device = []
    for dev in guessed_devices:
        if util.get_size_block_dev(dev) != 0:
            log.debug('DEVICE {} SHOULD BE A BLOCK DEVICE!'.format(dev))
            real_block_device.append(dev)

    return real_block_device


def guess_devices():
    while True:
        guessed_devices = MMCProfiler().guess()
        guessed_devices = _get_real_block_devices(guessed_devices)

        if guessed_devices:
            break

    return guessed_devices


def get_information(devices):
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


class MMCProfiler(object):
    def __init__(self):
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
            self.__cnt[action][device.sys_name] = self.__cnt[action][device.sys_name] + 1
        else:
            self.__cnt[action][device.sys_name] = 1

    def guess(self):
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
