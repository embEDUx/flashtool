# embEDUx Flash Tool

TODO ...Describtion...

## Requirements

__System:__

- python3
- python3-dev
- virtualenv
- libudev >= 151
- libparted
- git

__Python packages:__

-colorama
-pyudev
-argcomplete
-PyYAML
-requests
-jinja2
-pyparted


## Installation

### Required Packages

__Installation Ubuntu/Debian:__

```sh
$> apt-get install python3python3-dev python-virtualenvironment libudev-dev libparted git
```

__Installation Arch Linux:__

```sh
$> pacman -S ... // TO BE CONTINUED
```

__Installation Fedora Linux:__

```sh
$> yum -S ... // TO BE CONTINUED
```

__Installation Python:__


* Virtualenv:

```sh
# Creating an virtual environment for python (python version must be >=3)
$> virtualenv -p python3  {path/for/virtualenv}  # python3 can also be python3.x

# "go" into the virtual environment. All packages installed via pipwill only
# be installed at the location of the virtual environment ({path/for/virtual-env})

$> source {path/for/virtualenv}/bin/activate

# All python related packages will now be executed from virtual environement path
# The python installation of the system will be untouched.


# working in virtual environment ...


# leave virtual environement
$> deactivate

```

* Installation of python packages via pip

```sh
$> source {path/to/virtualenv}/bin/activate  # go into virtualenv
# Required python packages which can be installed via PyPI
$> pip install colorama pyudev argcomplete PyYAML requests jinja2
# Required package which must be retrived from github
$> pip install git+https://github.com/dcantrell/pyparted.git@pyparted-3.10.2#eg=pyparted
```


## Testing:

The tool was developed on an Arch Linux system. Production tests were made on
a native Arch Linux System, virtual Ubuntu Linux, virtual Arch Linux and 
virtual Fedora Linux.