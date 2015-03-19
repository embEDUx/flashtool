__author__ = 'mahieke'


import sys
sys.path.extend('..')

from flashtool.setup.recipe import RecipeContentException, Load, Product

valid_input_load = {
    'Rootfs_Rootfs': {'device': '1'},
    'Rootfs_Portage': {'device': '1'},
    'Linux_Root': {'device': '1'},
    'Linux_Boot': {'device': '1'},
    'Linux_Config': {'command': 'abc def'},
    'Uboot': {'device': '2'},
    'Misc_Root': {'device': '3'},
    'Misc_Boot': {'device': '4'},
}

def test_product_instance_device():
    prod1 = Product('Rootfs_Rootfs', {'device': '2'})

    assert prod1.name == 'Rootfs_Rootfs'
    assert prod1.device == 2
    assert prod1.command == None

def test_product_instance_command():
    prod2 = Product('Rootfs_Rootfs', {'command': 'echo \'abc\' | grep abc'})

    assert prod2.name == 'Rootfs_Rootfs'
    assert prod2.command == ['echo', '\'abc\' | grep abc']
    assert prod2.device == None


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

