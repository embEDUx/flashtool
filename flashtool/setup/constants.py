__author__ = 'mahieke'

LINUX_PARTITION = 131

mkfs_support = {
    'fat32': ['mkfs.fat', '-F32', '-n'],
    'ext4': ['mkfs.ext4', '-F', '-L'],
    'ext3': ['mkfs.ext3', '-F', '-L'],
    'ext2': ['mkfs.ext2', '-F', '-L'],
    'btrfs': ['mkfs.btrfs', '-f', '-L']
}

mkfs_check = {
    'vfat':  ['mkfs.vfat', '-v'],
    'btrfs': ['btrfs', 'check'],
    'ext4':  ['mkfs.ext4', '-v'],
    'ext3':  ['mkfs.ext3', '-v'],
    'ext2':  ['mkfs.ext2', '-v']
}