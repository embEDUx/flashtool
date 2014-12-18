__author__ = 'mahieke'

from embedux_flashtool.setup.prepare import recipe
from embedux_flashtool.setup.prepare import runnable
from embedux_flashtool.setup.prepare import RecipeContentException

class components_config(recipe):
    attr = ['uboot', 'linux', 'rootfs', 'misc']

    def __init__(self, attributes, rec):
        self.check_attributes(attributes)

        # set attributes specified in attr with corresponding objects
        new_attributes = {}
        for k,v in attributes.iteritems():
            new_attributes[k] = eval(k)(v)

        self.check_attributes(new_attributes)

        recipe.__init__(self, new_attributes)


class linux(recipe):
    attr = ['module', 'kernel_dest', 'modules_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        recipe.__init__(self, attributes)


class uboot(recipe):
    attr = ['module', 'uboot_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        recipe.__init__(self, attributes)

class rootfs(recipe):
    attr = ['module', 'rootfs_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        recipe.__init__(self, attributes)

class misc(recipe):
    attr = ['module', 'boot_dest', 'root_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        recipe.__init__(self, attributes)


__entry__ = components_config