# embEDUx Flash Tool

TODO ...Describtion...

## Installation

### System Requirements

- python
- virtualenv
- libudev >= 151
- git
- python-parted / pyparted

- maybe use blivet:
    * git+https://github.com/dcantrell/pyparted.git
    * git+https://github.com/dwlehman/blivet.git (pip)
    * git+https://github.com/clumens/pykickstart.git (pip)
    * git+https://git.fedorahosted.org/git/python-cryptsetup.git
    * libselinux (system package manager)
    * pyudev

pip install -egit+https://GIT-URL#egg=pyrsync


## Supported Platforms

This configuration affects kernel, flatten-device-tree files and u-boot.

 - Colibri T20 
   - Iris Board
   - ARMrider

 - Raspberry Pi

 - Quemu-arm
 
 - Beaglebone (in process)


## Supported Labs

This configuration affects rootFS and config partition (see below).

 - BASE (light-weight rootFS)
 - SYSO (Systemsoftware)
 - BSYS (Betriebssysteme)

You can find a list of all contained software packages in
chapter Software Packages.


## Software Packages

Lists with packages per rootFS configuration:

_BASE:_
 - ...


_SYSO:_
 - ...


_BSYS:_
 - ...


# Development (Brainstorming)

__pyrsync:__

 Kann nicht über das normale pip prozedere installiert werden (siehe [Issue](https://github.com/isislovecruft/pyrsync/issues/3)).
 Folgendes Kommando muss ausgeführt werden:

  
