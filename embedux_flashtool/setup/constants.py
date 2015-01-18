__author__ = 'mahieke'

LINUX_PARTITION = 131

mkfs_support = {
    'fat32': ['mkfs.fat', '-F32', '-n '],
    'ext4': ['mkfs.ext4', '-F', '-L '],
    'ext2': ['mkfs.ext2', '-F', '-L '],
    'btrfs': ['mkfs.btrfs', '-f', '-L ']
}