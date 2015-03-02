__author__ = 'mahieke'

from flashtool.setup.recipe import Recipe
from flashtool.setup.recipe import Load
from flashtool.setup.recipe import RecipeContentException
import flashtool.utility as util
from flashtool.setup.constants import mkfs_support

import _ped
import re



class MMC(Recipe):
    attr = ['partitions', 'partition_table', 'load']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        parts = []
        names = []
        has_max_size = False
        for elem in attributes['partitions']:
            if elem['size'] == max:
                if attributes['partitions'].index(elem) != len(attributes['partitions']) - 1:
                    raise RecipeContentException('Only the last partition can state the max flag for size.')
                has_max_size = True

            part = Partition(elem)
            if part.name not in names:
                names.append(part.name)
            else:
                raise RecipeContentException('Name of a partition must be unique!')
            parts.append(part)

        attributes['partitions'] = parts
        attributes['load'] = Load(attributes['load'])
        self.check_attributes(attributes)
        self.__check_partition_table(attributes['partition_table'])
        Recipe.__init__(self, attributes)


    def __check_partition_table(self, part_table):
        try:
            _ped.disk_type_get(part_table)
        except _ped.UnknownTypeException:
            raise RecipeContentException('Partition table {} stated in document is not supported!'.format(part_table))


class Partition(Recipe):
    attr = ['name', 'size', 'fs_type', 'mount_point', 'mount_opts', 'flags']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        if attributes['size'] != 'max':
            attributes['size'] = self.__to_byte(attributes['size'])
        attributes['name'] = attributes['name'].upper().strip()

        if attributes['name'] == '':
            raise RecipeContentException('Partition must contain a name.')

        Recipe.__init__(self, attributes)

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
                    if _ped.partition_flag_get_by_name(flag) == 0:
                        raise RecipeContentException('Flag {} for partition {} is not valid.'.format(flag, self.name))
            else:
                if _ped.partition_flag_get_by_name(flags) == 0:
                    raise RecipeContentException('Flag {} for partition {} is not valid.'.format(flags, self.name))


    def __to_byte(self, string):
        types = {re.compile('[0-9]+%$'): 0.01,
                 re.compile('[0-9]+$'): 1,
                 re.compile('[0-9]+(kb|kB|KB|Kb)$'): 1024,
                 re.compile('[0-9]+(mb|mB|MB|Mb)$'): 1024 * 1024,
                 re.compile('[0-9]+(gb|gB|GB|Gb)$'): 1024 * 1024 * 1024,
                 re.compile('[0-9]+(tb|tB|TB|Tb)$'): 1024 * 1024 * 1024 * 1024
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

__entry__ = MMC