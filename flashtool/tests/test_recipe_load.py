__author__ = 'mahieke'


import sys
sys.path.extend('..')

from flashtool.setup.recipe import RecipeContentException, Load, Product

valid_input_load = {
    'Rootfs_Rootfs': {'device': '0'},
    'Rootfs_Portage': {'device': '1'},
    'Linux_Root': {'device': '0'},
    'Linux_Boot': {'device': '1'},
    'Linux_Config': {'device': '2'},
    'Uboot': {'device': '0'},
    'Misc_Root': {'device': '1'},
    'Misc_Boot': {'device': '0'},
}

def test_product_instance_device():
    prod1 = Product('Rootfs_Rootfs', {'device': '1'})

    assert prod1.name == 'Rootfs_Rootfs'
    assert prod1.device == 2
    assert not prod1.command

def test_product_instance_command():
    prod2 = Product('Rootfs_Rootfs', {'command': 'echo \'abc\' | grep abc'})

    assert prod2.name == 'Rootfs_Rootfs'
    assert prod2.command == ['echo', '\'abc\' | grep abc']
    assert not prod2.device


def test_load_instance():
    load = Load(valid_input_load)

    assert isinstance(load.Rootfs_Rootfs, Product)
    assert isinstance(load.Rootfs_Portage, Product)
    assert isinstance(load.Linux_Root, Product)
    assert isinstance(load.Linux_Boot, Product)
    assert isinstance(load.Linux_Config, Product)
    assert isinstance(load.Uboot, Product)
    assert isinstance(load.Misc_Root, Product)
    assert isinstance(load.Misc_Boot, Product)
