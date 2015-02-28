# -*- coding: utf-8 -*-
__author__ = 'mahieke'

from jinja2 import Environment, PackageLoader
from colorama import Fore

def generate_fstab(info, destination):
    print(Fore.YELLOW + '   Generate fstab for device:')
    env = Environment(loader=PackageLoader('flashtool', 'templates'))
    template = env.get_template('fstab')
    stream = template.stream(info=info)
    file = '{}/etc/fstab'.format(destination.rstrip('/'))
    stream.dump(file)
    print(Fore.GREEN + '      Copied to /etc/fstab')

def get_fstab_fstype(typ):
    if typ == 'fat32':
        return 'vfat'
    else:
        return typ


class fstab_info(object):
    def __init__(self):
        self.objects = []

    def __iter__(self):
        return iter(self.objects)

    def append(self, kwargs):
        self.objects.append(fstab_object(kwargs))


class fstab_object(object):
    args = ['uuid', 'mountpoint', 'type', 'dump', 'pas', 'options']

    def __init__(self, kwargs):
        #uuid, mountpoint, fstype, dump, pas, options='defaults')
        for key in kwargs.keys():
            if key in self.args:
                self.__dict__[key] = kwargs[key]

    def __getattr__(self, at):
        return self[at]


