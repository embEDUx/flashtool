__author__ = 'mahieke'

import sys
import pytest

sys.path.extend('..')

from flashtool.setup.recipe import YAML, RecipeContentException, Load
from flashtool.setup.recipe.mmc import MMC, Partition


def test_byte_to_byte():
    assert Partition.to_byte('300') == 300


def test_kb_to_byte():
    assert Partition.to_byte('300kb') == 300 * 1024
    assert Partition.to_byte('300kB') == 300 * 1024
    assert Partition.to_byte('300KB') == 300 * 1024
    assert Partition.to_byte('300Kb') == 300 * 1024


def test_mb_to_byte():
    assert Partition.to_byte('300mb') == 300 * 1024 * 1024
    assert Partition.to_byte('300mB') == 300 * 1024 * 1024
    assert Partition.to_byte('300MB') == 300 * 1024 * 1024
    assert Partition.to_byte('300Mb') == 300 * 1024 * 1024


def test_gb_to_byte():
    assert Partition.to_byte('300gb') == 300 * 1024 * 1024 * 1024
    assert Partition.to_byte('300GB') == 300 * 1024 * 1024 * 1024
    assert Partition.to_byte('300GB') == 300 * 1024 * 1024 * 1024
    assert Partition.to_byte('300Gb') == 300 * 1024 * 1024 * 1024


def test_tb_to_byte():
    assert Partition.to_byte('300tb') == 300 * 1024 * 1024 * 1024 * 1024
    assert Partition.to_byte('300tB') == 300 * 1024 * 1024 * 1024 * 1024
    assert Partition.to_byte('300TB') == 300 * 1024 * 1024 * 1024 * 1024
    assert Partition.to_byte('300Tb') == 300 * 1024 * 1024 * 1024 * 1024


@pytest.mark.parametrize("input", [
    'fat32',
    'vfat',
    'ext4',
    'ext3',
    'ext2',
    'btrfs',
])
def test_fs_supported(input):
    try:
        Partition.check_fs_type(input)
    except:
        assert False

    assert True


def test_partition():
    part_values = {
        'name': 'boot',
        'size': '300 mb',
        'fs_type': 'fat32',
        'mount_point': '/boot',
        'mount_opts': '',
        'flags': 'boot, lba',
    }

    part = Partition(part_values)

    assert issubclass(Partition, YAML)

    assert part.name == part_values['name']
    assert part.size == part_values['size']
    assert part.fs_type == part_values['fs_type']
    assert part.mount_point == part_values['mount_point']
    assert part.mount_opts == part_values['mount_opts']
    assert part.flags == part_values['flags']


def test_partition_missing_attributes():
    part_values = {
        'name': 'boot',
    }

    with pytest.raises(RecipeContentException):
        part = Partition(part_values)


def test_recipe_mmc():
    input_dict = {
        'partition_table': 'msdos',
        'partitions': [
            {
                'name': 'boot',
                'size': '300 mb',
                'fs_type': 'fat32',
                'mount_point': '/boot',
                'mount_opts': '',
                'flags': 'boot, lba',
            },
            {
                'name': 'root',
                'size': 'max',
                'fs_type': 'ext4',
                'mount_point': '/',
                'mount_opts': '',
                'flags': '',
            },
        ],
        'load': {
            'Uboot': {
                'command': 'dd if=${file} of=${device} bs=1K skip=1 seek=1 oflag=dsync',
            },
            'Linux_Boot': {
                'device': '0',
            },
            'Linux_Root': {
                'device': '1',
            },
            'Linux_Config': {
                'device': '1',
            },
            'Rootfs_Rootfs': {
                'device': '1',
            },
            'Rootfs_Portage': {
                'device': '1',
            },
            'Misc_Boot': {
                'device': '0',
            },
            'Misc_Root': {
                'device': '1',
            },
        },
    }

    mmc = MMC(input_dict)

    assert mmc.partition_table == input_dict['partition_table']
    assert len(mmc.partitions) == 2
    assert isinstance(mmc.partitions[0], Partition)
    assert isinstance(mmc.partitions[1], Partition)
    assert isinstance(mmc.load, Load)

