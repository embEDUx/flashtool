__author__ = 'mahieke'

import logging as log
import embedux_flashtool.utility as util
from functools import partial
from colorama import Fore
from pyudev import Device
from pyudev import MonitorObserver
from pyudev import Context
from pyudev import Monitor


class MMC():
    '''

    '''

    def __init__(self):
        '''

        '''
        # FEATURE: Set logging priority of pyudev
        self.__context = Context()
        self.__monitor = Monitor.from_netlink(self.__context)
        self.__info = {}


    def get_mmc(self):
        '''

        :return:
        '''
        util.user_prompt('Please remove all sd cards from your Flash station', 'Done?')

        print('Ok, lets move on...')
        while True:
            guessed_devices = MMCProfiler().guess()
            for dev in guessed_devices:
                if util.get_size_block_dev(dev) == 0:
                    guessed_devices.pop(0)

            if guessed_devices != []:
                break

        print('Found following devices: ' + Fore.YELLOW + '{}'.format(', '.join(guessed_devices)))


    def __save_info(self, device):
        '''

        :param device:
        :return:
        '''
        if device.get('ID_DRIVE_FLASH_SD') == '1':
            # parent device
            if device.get('DEVTYPE') == 'disk':
                dev_name = device.sys_name
                self.__info[dev_name] = {'childs': {}}
                for child in device.children:
                    child_name = child.sys_name
                    self.__info[dev_name]['childs'][child_name] = {}

            # partitions of parent device
            if device.get('DEVTYPE') == 'partition':
                partition_name = device.sys_name
                parent_name = device.parent.sys_name
                if parent_name not in self.__info.keys():
                    self.__info[parent_name] = {'childs': {partition_name: {}}}

                self.__info[parent_name]['childs'][partition_name] = {
                    'path': device.get('DEVNAME'),
                    'fs_type': device.get('ID_FS_TYPE')
                }


class MMCProfiler(object):
    '''
        'ext_plgd': {
            'description': 'external reader already plugged in, waiting for sd card to be plugged in',
            'add': {},
            'change': '1'
        },
        'ext_no_plgd': {
            'description': 'waiting for external reader to be plugged in, then waiting for sd card to be plugged in',
            'add': 'equal',
            'change': 'highest'
        },
        'ext_no_plgd_sd': {
            'description': 'waiting for external reader to be plugged in, sd card is already plugged in',
            'add': 'equal',
            'change': 'difference'
        },
        'intern': {
            'description': 'waiting for sd card to be plugged in internal reader',
            'add': '1',
            'change': {}
        }

    '''

    def __init__(self):
        context = Context()
        monitor_mmc = Monitor.from_netlink(context)
        monitor_mmc.filter_by(subsystem='block')

        self.__cnt = {'add':{}, 'change':{}}

        for action, device in monitor_mmc:
            if action in ['add', 'change']:
                self.__count(action, device)
                break

        for device in iter(partial(monitor_mmc.poll, 1), None):
            if action in ['add', 'change']:
                self.__count(action,device)



    def __count(self, action, device):
        if self.__cnt[action].has_key(device.sys_name):
            self.__cnt[action][device.sys_name] = self.__cnt[action][device.sys_name] + 1
        else:
            self.__cnt[action][device.sys_name] = 1

    def guess(self):
        devname = list()

        log.debug('STATISTIC OF CHANGE AND ADD EVENTS: {}'.format(self.__cnt))

        if self.__cnt['add'] == {}: # Use-Case 1
            devname = list(self.__cnt['change'].keys())
        elif self.__cnt['change'] == {}: # Use-Case 4
            devname = list(self.__cnt['change'].keys())
        elif list(self.__cnt['add'].values())[1:] == list(self.__cnt['add'].values())[:-1]:
            diff = set(list(self.__cnt['add'].keys())) - set(list(self.__cnt['change'].keys()))
            if  diff == set([]): # Use-Case 2
                maximum = max(self.__cnt['add'].values())
                devname = [k for k,v in self.__cnt.iteritems() if v == maximum]
            else: # Use-Case 3
                devname = diff
        else:
            devname = set(list(self.__cnt['add'].keys())) * set(list(self.__cnt['change'].keys()))
            log.critical('EVENTS DO NOT MEET HEURISTIC INFORMATION!!')

        log.debug('GUESSING FOLLOWING DEVICES BY HEURISTICS: {}'.format(', '.join(devname)))

        return devname
