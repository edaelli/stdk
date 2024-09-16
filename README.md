# <img src="./doc/icon_logo.png" width=70 align='center'>&emsp;lone

# A Stand-aLONE Storage Development Kit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Introduction

lone is a set of tools and libraries primarily written in Python (with C extensions) which grants a user full control of a storage device. It uses similar concepts as [SPDK](https://www.spdk.io), but where SPDK focuses on performance, lone focuses on testability and control.

The software takes advantage of modern IO Virtualization Hardware such as Intel VT-d and AMD VI to allow full control of a storage device in userspace using Python.

lone aims to be the basis for writing both extremely simple and extremely complex test cases.

## Quick Start on Linux

- Prepare a system with ubuntu 20.04+, python3.5+ and pip3, running hardware with an IOMMU

- Install [docker](https://docs.docker.com/engine/install/ubuntu/) and [docker-compose](https://docs.docker.com/compose/install/)

- Optional/Developer : Install virtualenv & Activate
    ```
    # For Ubuntu
    $ sudo apt install python3-venv

    # For other distributions
    $ python3 -m pip install --user virtualenv

    # Activate venv
    $ source .venv/bin/activate
    ```

- Clone the lone repo, cd into it, and install python3 requirements for lone_setup.py
    ```
    $ pip3 install -r python3/requirements.txt
    ```

- Optional/Developer : Build & install the hugepages module (if not installed from pip)
    ```
    $ (cd ./python3/ && python3 ./setup.py install)
    ```

- Configure HugePages (may not be necessary)
    ```
    # Temporary
    $ echo 1024 | sudo tee /proc/sys/vm/nr_hugepages

    # Persistent
    $ vim /etc/sysctl.conf
    vm.nr_hugepages = 1024
    ```

- List available devices and expose one to the lone user (uid = 1000) in the docker container:
    ```
    $ python3 python3/lone_setup.py list
      PciUserspaceDevice devices:
      slot              vid:did        driver        owner   info
      0000:3a:00.0     10EC:5763         nvme                Realtek Semiconductor Co., Ltd. Device 5763 (rev 01)

    $ sudo python3 python3/lone_setup.py expose 0000:3a:00.0 1000
      SUCESS: 0000:3a:00.0 is now usable by 1000 in userspace as /dev/vfio/19
    ```

- Build and enter docker lone environment
    ```
    $ docker compose build lone_env

    # -OR- If proxy required, pass as arguments
    $ docker compose build lone_env --build-arg https_proxy=http://proxy.mycompany.com:9012 \
        --build-arg http_proxy=http://proxy.mycompany.com:9011
    ...

    $ docker compose run lone_env
    lone_user@e1337ced27c4:/$
    ```

- Run an example (lone_list mimics the nvme-cli list command)
    ```
    $ python3 python3/lone_setup.py list
    PciUserspaceDevice devices:
    slot                vid:did          driver        owner   info
    nvsim             60672:55809         nvsim         user   NVSim simulator
    ```


## Motivation

lone was conceived as an alternative to current storage test tools, initially focusing on the NVMe Specification.

The driving factor for this development kit is to make storage testing straightforward by building Python objects on top of userspace PCI & NVMe register and memory access; then combining those basic building blocks into complex tasks, all while giving a user the full power of the Python language in a storage test infrastructure.

## Theory of Operation

An NVMe device is interacted with by using a combination of 3 different access mechanisms:
1. Configuration Space or PCI registers
2. Memory mapped NVMe registers
3. Operating System Memory

A very simple view of how an NVMe device operates is that a host system (or developer, or test engineer, test infrastructure, etc) changes values in PCI and NVMe registers which affect how the device behaves. In some cases, the host system allocates buffers for the device to access and communicates those buffers addresses to the device.

lone uses IO Virtualization technology to present the 3 access mechanisms above to a userspace process. This allows the development kit to create Python objects that make testing straightforward, enables combining the basic building blocks into complex tasks, and gives a user the full power of the Python language:

    # Import NVMeDevice
    >>> from lone.nvme.device import NVMeDevice

    # Create object, using the simulator for demonstration
    >>> nvme_device = NVMeDevice('nvsim')

    # Access PCIe registers
	>>> hex(nvme_device.pcie_regs.ID.VID)
    '0xedda'
	>>> hex(nvme_device.pcie_regs.ID.DID)
    '0xe111'

    # Acccess NVMe registers
    >>> hex(nvme_device.nvme_regs.VS.MJR)
    '0x2'
    >>> hex(nvme_device.nvme_regs.VS.MNR)
    '0x1'

    # Init/enable/disable

    # Check that the device is disabled
    >>> hex(nvme_device.nvme_regs.CSTS.RDY)
    '0x0'

    # Initialize admin queues
    >>> nvme_device.init_admin_queues()

    # Set CC.EN = 1 to enable it, verify CSTS.RDY = 1
    >>> nvme_device.cc_enable()
    >>> hex(nvme_device.nvme_regs.CSTS.RDY)
    '0x1'

    # Send a command

    # Import identify controller command structure
    >>> from lone.nvme.spec.commands.admin.identify import IdentifyController

    # Create the command object
    >>> id_ctrl = IdentifyController()

    # Send it to the drive, wait for response, check response status
    >>> nvme_device.sync_cmd(id_ctrl)

    # Check some returned values in data_in
    >>> id_ctrl.data_in.MN
    b'nvsim_0.1'
    >>> id_ctrl.data_in.SN
    b'EDDAE771'
    >>> id_ctrl.data_in.FR
    b'0.001'

    # Disable, verify CSTS.RDY = 0
    >>> nvme_device.cc_disable()
    >>> hex(nvme_device.nvme_regs.CSTS.RDY)
    '0x0'

## Design

### System Interface
A System Interface class sits at the lowest level of the lone stack. This interface abstracts operating system and hardware access to the rest of the stack. It has the following interfaces:

1. Pci - Implements an interface into the Pci subsystem of the OS/Hardware running lone applications. For example, it allows code to rescan the devices in the Pci bus for a system

2. PciDevice - Implements an interface into each Pci device in a system. For example, it allows code to check if a device at a certain slot exists

3. PciUserspace - Implements an interface into a system to interact with the userspace exposed functions of that system. For example, it can query the system for a list of userspace-exposed devices

4. PciUserspaceDevice - Implements an interface into each userspace-exposed device. For example, it exposes the device's registers in a system independent way

5. Memory - Implements an interface into the system running lone applications to allocate pinned memory (special memory pages that cannot be paged out by an OS's memory management system)

### Layered Architecture
lone software layers are organized as:

<img src=doc/lone_layers.png width=600 align=center>

### Hardware
lone relies on a systems IOMMU hardware to safely allow userspace access of storage devices. The system must have Intel Vt-d, AMD Vi, etc for lone to work.

### Software

#### Linux
- python3.5+
- Ubuntu 20.04+
- Hugepages enabled and available
- libhugetlbfs-dev
- docker, if using the provided container

## System Setup

### Linux
lone is meant to be run in userspace without root privileges. However, root privileges are required to expose a vfio device to a certain user. lone provides a script (lone_setup.py) to accomplish that. Once all requirements are met in the target system, it can be run by:

    cd <lone_path>
    python3 python3/lone_setup.py list  # Lists all available NVMe devices that can be exposed to userspace
    sudo python python3/lone_setup.py expose pci_slot_string user  # Exposes the device at the provided pci slot to the provided user
    sudo python python3/lone_setup.py reclaim pci_slot_string driver # Reclaims the device at the provided pci slot and binds it to the provided driver

## Installation
### Linux
lone provides a docker container and docker-compose configuration file that allows a system to quickly start running. After installing [docker](https://docs.docker.com/engine/install/ubuntu/) and [docker-compose](https://docs.docker.com/compose/install/), run the following commands:

    cd <lone_path>
    docker compose build lone_env
    docker compose run lone_env


## Examples

Please take a look at the repository for [examples](https://github.com/edaelli/lone/tree/main/python3/lone/examples). The examples folder contains a functioning demo NVMe driver that can be used to send commands to a device.

## Development
lone is in early development. The vision is that developers and leaders in the storage industry see its value and help develop it into a sophisticated test framework.

### Questions, comments, ideas: https://github.com/edaelli/lone/discussions
### Interesting things to help with: https://github.com/edaelli/lone/issues`
