__author__ = 'mahieke'
from colorama import Fore
import hashlib

def get_products_by_recipe_user_input(recipe, actions, builds, platform, auto):
    '''
    Returns a dictionary with information for each product. The information
    provides product types, load instruction of the yaml file, file url and size
    of the file.

    :param recipe:   load part of a recipe
    :param actions:  user actions (dictionary)
    :param builds:   Instance of the Buildserver class
    :param platform: name of the platform
    :param auto:     flag, for automatic mode
    :return:
    '''
    yaml_info = merge_load_recipe_with_user_input(recipe, actions)
    load_cfg = {}

    build_info = builds.get_builds_info()

    load_order = ['rootfs', 'uboot', 'linux', 'misc']
    for product in load_order:
        if product not in yaml_info.keys():
            continue

        value = yaml_info[product]
        file_info = builds.get_build_info(build_info, [product], platform)
        file_types = [i for i in value.keys() if i != 'r_name']
        reg_name = value['r_name']

        a = max(len(product), len(reg_name), len(', '.join(file_types)))

        print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))
        for s in [('product',product), ('reg_name', reg_name), ('file_types', ', '.join(file_types))]:
            st = '   | {:12}'.format(s[0] + ':') + '{:<' + str(a) + '} |'
            print(Fore.YELLOW + st.format(s[1]))

        print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))

        files = builds.get_files_path(file_info, reg_name, [(product, file_types)], auto)[0][1]

        load_cfg[product] = []
        for f_type, file in files:
            load_cfg[product].append({
                'f_type': f_type,
                'yaml': value[f_type],
                'file': file,
                'size': int(builds.get_file_size(file))
            })
        print('')

    return load_cfg


def merge_load_recipe_with_user_input(load_recipe, user_actions):
    '''
    Merges the load info with the user input.

    Example:
        load_recipe: {
                        'Linux_boot' : { 'device' : 0 },
                        'Linux_root' : { 'device' : 1 },
                        'Uboot'      : { 'device' : 0 },
                     }
        user_input:  { 'linux' : '', 'uboot' : 'rc1.4' }

        return:      {
                        'linux' : {
                            'r_name' : ''
                            'boot'   : { 'device' : 0 },
                            'root'   : { 'device' : 1 },
                        },
                        'uboot' : {
                            'r_name' : 'rc1.4',
                             'uboot' : { 'device' : 0 }
                        }
                     }


    :param load_recipe: parsed load recipe. see flashtool.setup.recipe.Load
    :param user_actions: arguments of user. Dictionary {product : regex, product : regex, ...}
    :return: Returns a dictionary.
    '''
    yaml_info = {}
    # extract information for loading products to platform
    for product_name, values in load_recipe:

        prod = product_name.lower().split('_')
        product = prod[0]

        if product in user_actions:
            name = ''
            if len(prod) == 1:
                name = product
            elif len(prod) == 2:
                name = prod[1]

            reg_name = user_actions[product]
            content = {}

            if yaml_info.get(product):
                yaml_info[product].update({
                    name: values
                })
            else:
                yaml_info.update({
                    product : {
                        'r_name': reg_name,
                        name: values
                    }
                })
    return yaml_info


import crypt
import getpass
import subprocess
import os
from Crypto.Random import get_random_bytes
import datetime

def set_root_password(path_to_rootfs):
    '''
    User can set a root password for the linux system.
    The entry will be saved at /etc/shadow of the root
    filesystem.

    :param path_to_rootfs: path to the rootfs
    :return:
    '''
    path = '{}/etc/shadow'.format(path_to_rootfs.rstrip('/'))
    if not os.path.exists(path):
        raise FileNotFoundError('Could not find {}'.format(path))

    print('')
    print('Please set a root password for the system or press enter for default password [default \'toor\']:')
    pw = getpass.getpass()

    if pw == '':
        pw = 'toor'

    subprocess.call(['sed', '-i', '1d', path])

    # salt will be generated automatically
    encrypted_pw = crypt.crypt(pw)

    epoch = datetime.datetime.utcfromtimestamp(0)
    today = datetime.datetime.today()
    days = (today - epoch).days

    shadow_string = 'root:{}:{}:::::\n'.format(encrypted_pw, days)

    with open(path, 'a') as shadow:
        shadow.write(shadow_string)

