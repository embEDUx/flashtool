# embEDUx Flash Tool

TODO ...Describtion...

## Installation

### System Requirements

- python
- virtualenv
- libudev >= 151


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

  pip install -egit+https://github.com/isislovecruft/pyrsync#egg=pyrsync

 TODO: Wie muss ein paket angegeben werden, damit es automatisch angezogen wird.

