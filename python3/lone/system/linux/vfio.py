''' Interact with the VFIO driver to use devices in userspace
'''
import ctypes
import os
import fcntl
import subprocess
import pathlib
import pyudev
import mmap

from lone.system import SysPciUserspace, SysPciUserspaceDevice
from lone.nvme.spec.registers.pcie_regs import (PCIeRegisters,
                                                PCIeAccessData,
                                                pcie_reg_struct_factory)
from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect

import logging
logger = logging.getLogger('vfio')


class VfioIoctl(ctypes.Structure):
    ''' Object used to send IOCTLs to an vfio container/device
        Definitions from: https://elixir.bootlin.com/linux/latest/source/include/uapi/linux/vfio.h
    '''
    VFIO_IOCTL_TYPE = ord(';')
    VFIO_IOCTL_BASE = 100
    VFIO_API_VERSION = 0
    VFIO_TYPE1_IOMMU = 1
    VFIO_GROUP_FLAGS_VIABLE = (1 << 0)
    VFIO_GROUP_FLAGS_CONTAINER_SET = (1 << 1)

    VFIO_PCI_CONFIG_REGION = 7
    VFIO_BAR0_REGION = 0

    VFIO_PCI_BAR0_REGION_INDEX = 0
    VFIO_PCI_BAR1_REGION_INDEX = 1
    VFIO_PCI_BAR2_REGION_INDEX = 2
    VFIO_PCI_BAR3_REGION_INDEX = 3
    VFIO_PCI_BAR4_REGION_INDEX = 4
    VFIO_PCI_BAR5_REGION_INDEX = 5
    VFIO_PCI_ROM_REGION_INDEX = 6
    VFIO_PCI_CONFIG_REGION_INDEX = 7

    VFIO_PCI_INTX_IRQ_INDEX = 0
    VFIO_PCI_MSI_IRQ_INDEX = 1
    VFIO_PCI_MSIX_IRQ_INDEX = 2
    VFIO_PCI_ERR_IRQ_INDEX = 3
    VFIO_PCI_REQ_IRQ_INDEX = 4
    VFIO_PCI_NUM_IRQS = 5

    VFIO_IRQ_SET_DATA_EVENTFD = (1 << 2)
    VFIO_IRQ_SET_ACTION_TRIGGER = (1 << 5)

    # Pack to 1 byte
    _pack_ = 1

    def ioctl(self, device_fd, ioctl_arg=None):
        ''' Sends an IOCTL to a vfio container/device
        '''
        from ioctl_opt import IO

        ioctl_number = IO(VfioIoctl.VFIO_IOCTL_TYPE, VfioIoctl.VFIO_IOCTL_BASE + self._ioctl_)
        self.argsz = ctypes.sizeof(self)
        if ioctl_arg is not None:
            return fcntl.ioctl(device_fd, ioctl_number, ioctl_arg)
        else:
            return fcntl.ioctl(device_fd, ioctl_number, self)

    def get_data(self):
        ''' Returns the data buffer for an IOCTL
        '''
        return self


class VfioGetApiVersion(VfioIoctl):
    _ioctl_ = 0


class VfioCheckExtension(VfioIoctl):
    _ioctl_ = 1


class VfioSetIoMmu(VfioIoctl):
    _ioctl_ = 2


class VfioGroupGetStatus(VfioIoctl):
    _ioctl_ = 3
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
    ]


class VfioGroupSetContainer(VfioIoctl):
    _ioctl_ = 4
    _fields_ = [
        ('cont_fd', ctypes.c_uint32),
    ]


class VfioGroupUnsetContainer(VfioIoctl):
    _ioctl_ = 5


class VfioGetDeviceFd(VfioIoctl):
    _ioctl_ = 6
    _fields_ = [
        ('string', ctypes.c_char * 12),
    ]


class VfioDeviceGetInfo(VfioIoctl):
    _ioctl_ = 7
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('num_regions', ctypes.c_uint32),
        ('num_irqs', ctypes.c_uint32),
    ]


class vfioGetRegionInfo(VfioIoctl):
    _ioctl_ = 8
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('resv', ctypes.c_uint32),
        ('size', ctypes.c_uint64),
        ('offset', ctypes.c_uint64),
    ]


class vfioDeviceReset(VfioIoctl):
    _ioctl_ = 11


class VfioCapHeader(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_uint16),
        ('version', ctypes.c_uint16),
        ('next', ctypes.c_uint32),
    ]


class VfioIovaRange(ctypes.Structure):
    _fields_ = [
        ('start', ctypes.c_uint64),
        ('end', ctypes.c_uint64),
    ]


class VfioCapIovaRanges(ctypes.Structure):
    _fields_ = [
        ('header', VfioCapHeader),
        ('nr_iovas', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32),
        ('ranges', 5 * VfioIovaRange),
    ]


class VfioIommuGetInfo(VfioIoctl):
    _ioctl_ = 12

    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('iova_pgsizes', ctypes.c_uint64),
        ('cap_offset', ctypes.c_uint32),
        ('pad', ctypes.c_uint32),
        ('caps', 1024 * ctypes.c_uint8),
    ]
    caps_offset = 24


class vfioMmuMapDma(VfioIoctl):
    _ioctl_ = 13
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('vaddr', ctypes.c_uint64),
        ('iova', ctypes.c_uint64),
        ('size', ctypes.c_uint64),
    ]
    DMA_MAP_FLAG_READ = (1 << 0)
    DMA_MAP_FLAG_WRITE = (1 << 1)
    DMA_MAP_FLAG_RW = DMA_MAP_FLAG_READ | DMA_MAP_FLAG_WRITE


class vfioMmuUnmapDma(VfioIoctl):
    _ioctl_ = 14
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('iova', ctypes.c_uint64),
        ('size', ctypes.c_uint64),
    ]


class vfioGetIRQInfo(VfioIoctl):
    _ioctl_ = 9
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('count', ctypes.c_uint32),
    ]


class vfioSetIRQs(VfioIoctl):
    _ioctl_ = 10
    _fields_ = [
        ('argsz', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('start', ctypes.c_uint32),
        ('count', ctypes.c_uint32),
        ('data', ctypes.c_int32 * 4096),
    ]


class SysVfioIfc(SysPciUserspaceDevice):
    ''' Vfio class to interact with a vfio container/device
    '''
    def __init__(self, pci_slot, iommu_group=None, device_path=None,
                 init=True,
                 pci_vid=None, pci_did=None,
                 driver=None, owner=None, info_string=None):
        assert type(pci_slot) is str, 'pci_slot type must be string!'

        super().__init__(pci_slot, pci_vid, pci_did, driver, owner, info_string)

        self.iommu_group = iommu_group
        self.device_path = device_path
        self.eventfds = []

        if init:
            self.initialize()

    def initialize(self):
        ''' Initialize the object by following the instructions at:
            https://01.org/linuxgraphics/gfx-docs/drm/driver-api/vfio.html
            pci_slot is the string representation of the PCIe slot to work with
            in this format: 0000:00:00.0
        '''
        self.container_path = '/dev/vfio/vfio'

        # Get the device's iommu_group from sysfs
        iommu_group_path = '/sys/bus/pci/devices/{}/iommu_group'.format(self.pci_slot)
        ret = os.readlink(iommu_group_path)
        self.iommu_group = os.path.basename(ret)

        # Open the container
        self.container_fd = os.open(self.container_path, os.O_RDWR)
        self.group_fd_path = '/dev/vfio/{}'.format(self.iommu_group)
        if not os.path.exists(self.group_fd_path):
            raise Exception('Device does not exist')
        self.group_fd = os.open(self.group_fd_path, os.O_RDWR)

        # Check the API version support
        api_version = VfioGetApiVersion().ioctl(self.container_fd)
        assert api_version == VfioIoctl.VFIO_API_VERSION, (
               'API {} supported by the host, need {}'.format(
                   api_version, VfioIoctl.VFIO_API_VERSION))

        # Check extenstion supoprt
        check_extension = VfioCheckExtension().ioctl(self.container_fd, VfioIoctl.VFIO_TYPE1_IOMMU)
        assert check_extension != 0, (
               'Return: {} Extension {} NOT supported by the host'.format(
                   check_extension, VfioIoctl.VFIO_TYPE1_IOMMU))

        # Check if the group is viable
        g_status = VfioGroupGetStatus()
        g_status.ioctl(self.group_fd)
        status = g_status.get_data()
        assert status.flags & VfioIoctl.VFIO_GROUP_FLAGS_VIABLE

        # Set the container for the group
        s_cont = VfioGroupSetContainer(cont_fd=self.container_fd)
        s_cont.ioctl(self.group_fd)

        # Make sure it took
        g_status = VfioGroupGetStatus()
        g_status.ioctl(self.group_fd)
        status = g_status.get_data()
        assert status.flags & VfioIoctl.VFIO_GROUP_FLAGS_VIABLE
        assert status.flags & VfioIoctl.VFIO_GROUP_FLAGS_CONTAINER_SET

        # Set IOMMU status
        VfioSetIoMmu().ioctl(self.container_fd, VfioIoctl.VFIO_TYPE1_IOMMU)

        # Get IOMMU info
        iommu_get_info = VfioIommuGetInfo()
        iommu_get_info.ioctl(self.container_fd)
        iommu_get_info_data = iommu_get_info.get_data()

        # Save page sizes
        self.iova_pgsizes = iommu_get_info_data.iova_pgsizes

        # Figure out capabilities, only interested in iova ranges for now
        self.iova_ranges = []
        next_cap_offset = iommu_get_info_data.cap_offset
        loops = 0
        while next_cap_offset != 0:
            cap_bytes = bytearray(
                iommu_get_info_data.caps[next_cap_offset - VfioIommuGetInfo.caps_offset:])
            cap = VfioCapHeader.from_buffer(cap_bytes)
            if cap.id == 0x01:
                ranges = VfioCapIovaRanges.from_buffer(cap_bytes)
                for i in range(ranges.nr_iovas):
                    self.iova_ranges.append((ranges.ranges[i].start, ranges.ranges[i].end))
            next_cap_offset = cap.next
            loops += 1
            assert loops < 1000, 'Stopping us from looping forever'

        # Get the device's fd
        dev_fd = VfioGetDeviceFd(string=self.pci_slot.encode())
        self.device_fd = dev_fd.ioctl(self.group_fd)
        assert self.device_fd != 0

        dev_info = VfioDeviceGetInfo()
        dev_info.ioctl(self.device_fd)
        info = dev_info.get_data()
        assert info.num_regions >= 8

        # Get BAR information
        num_bars = 6
        self.bars = [0] * num_bars
        for bar in range(6):
            req = vfioGetRegionInfo(index=bar)
            req.ioctl(self.device_fd)
            self.bars[bar] = {'size': req.size, 'offset': req.offset, 'flags': req.flags}

        # Get PCI config region information
        req = vfioGetRegionInfo(index=VfioIoctl.VFIO_PCI_CONFIG_REGION)
        req.ioctl(self.device_fd)
        self.pci_region = {'size': req.size, 'offset': req.offset, 'flags': req.flags}

        # Get ROM information
        req = vfioGetRegionInfo(index=VfioIoctl.VFIO_PCI_ROM_REGION_INDEX)
        req.ioctl(self.device_fd)
        self.rom_region = {'size': req.size, 'offset': req.offset, 'flags': req.flags}

    def get_irq_info(self, index=0):
        irq_info = vfioGetIRQInfo()
        irq_info.index = index
        irq_info.ioctl(self.device_fd)
        irq_info.get_data()
        return irq_info

    def enable_msix(self, num_vectors, start_vector):
        req = vfioSetIRQs()
        req.count = num_vectors
        req.flags = (VfioIoctl.VFIO_IRQ_SET_DATA_EVENTFD | VfioIoctl.VFIO_IRQ_SET_ACTION_TRIGGER)
        req.index = VfioIoctl.VFIO_PCI_MSIX_IRQ_INDEX
        req.start = start_vector

        for i in range(num_vectors):
            eventfd = os.eventfd(0, flags=os.EFD_NONBLOCK)
            req.data[i] = eventfd
            self.eventfds.append(eventfd)

        req.ioctl(self.device_fd)

    def get_msix_vector_pending_count(self, vector):
        try:
            count = int.from_bytes(os.read(self.eventfds[vector], 8), 'little')
        except BlockingIOError:
            count = 0
        return count

    def pcie_get(self, offset):
        data = os.pread(self.device_fd, 1, self.pci_region['offset'] + offset)
        return int.from_bytes(data, 'little')

    def pcie_set(self, offset, value):
        assert os.pwrite(self.device_fd,
                         value.to_bytes(1, 'little'),
                         self.pci_region['offset'] + offset)

    def pci_regs(self):

        class PCIeRegistersVFIO(pcie_reg_struct_factory(PCIeAccessData(self.pcie_get,
                                                                       self.pcie_set,
                                                                       None,
                                                                       None)),
                                PCIeRegisters):
            direct = False

        return PCIeRegistersVFIO()

    def nvme_regs(self):
        self.nvme_mmap = mmap.mmap(self.device_fd,
                                   length=self.bars[0]['size'],
                                   offset=self.bars[0]['offset'])
        self.nvme_registers = NVMeRegistersDirect.from_buffer(self.nvme_mmap)
        return self.nvme_registers

    def map_dma_region(self, vaddr, iova, size, flags):
        ''' Map a DMA region to be used by the device
        '''
        req = vfioMmuMapDma(flags=flags, vaddr=vaddr, iova=iova, size=size)
        req.ioctl(self.container_fd)

    def map_dma_region_read(self, vaddr, iova, size):
        ''' Map a DMA region for READ ONLY
        '''
        self.map_dma_region(vaddr, iova, size, vfioMmuMapDma.DMA_MAP_FLAG_READ)

    def map_dma_region_write(self, vaddr, iova, size):
        ''' Map a DMA region for WRITE ONLY
        '''
        self.map_dma_region(vaddr, iova, size, vfioMmuMapDma.DMA_MAP_FLAG_WRITE)

    def map_dma_region_rw(self, vaddr, iova, size):
        ''' Map a DMA region for WRITE ONLY
        '''
        self.map_dma_region(vaddr, iova, size, vfioMmuMapDma.DMA_MAP_FLAG_RW)

    def unmap_dma_region(self, iova, size):
        ''' Unmap DMA region
        '''
        req = vfioMmuUnmapDma(iova=iova, size=size)
        req.ioctl(self.container_fd)

    def reset(self):
        ''' Reset the device
        '''
        vfioDeviceReset().ioctl(self.device_fd)

    def clean(self):
        ''' Cleanup (close container, and group)
        '''

        # Cleanup the mmaped registers
        del self.nvme_registers
        self.nvme_mmap.close()

        # Close the device fd and unset the container
        os.close(self.device_fd)
        VfioGroupUnsetContainer().ioctl(self.group_fd)

        # Close the container and group fds
        os.close(self.container_fd)
        os.close(self.group_fd)


class SysVfio(SysPciUserspace):

    def exposed_devices(self):
        return [d for d in self.devices() if d.driver == 'vfio_pci']

    def devices(self):
        # Available devices get put in this list
        available_devices = []

        # IOMMU group list
        try:
            iommu_groups = subprocess.check_output(
                ['find', '/sys/kernel/iommu_groups/', '-type', 'l'],
                stderr=subprocess.PIPE).decode('utf-8').splitlines()
        except subprocess.CalledProcessError:
            # No iommu groups, no devices
            return available_devices

        # List of mounted devices
        mounted_devices = subprocess.check_output(['mount']).decode('utf-8')

        # List of lspci devices
        lspci_devices = subprocess.check_output(['lspci', '-D']).decode('utf-8')

        # Find the devices we can use
        context = pyudev.Context()
        for device in context.list_devices():

            # Filter out everything but NVMe devices
            if (device.get('SUBSYSTEM') == 'pci' and
                    device.get('PCI_CLASS') == '10802'):

                # dev_class = device.get('PCI_CLASS')
                slot = device.get('PCI_SLOT_NAME')
                dev_pci_id = device.get('PCI_ID')
                dev_pci_vid, dev_pci_did = dev_pci_id.split(':')

                # Get the lspci info for the device
                lspci_info = [
                    line for line in lspci_devices.splitlines() if slot in line][0].split(': ')[1]

                # Get the iommu_group for the device
                iommu_group = None
                for g in iommu_groups:
                    if slot in g:
                        _, _, _, _, iommu_group, _, iommu_slot = g.split('/')

                # Check if it is mounted
                dev_name = device.get('DEVNAME')
                if dev_name:
                    mounted = True if dev_name in mounted_devices else False
                else:
                    mounted = False

                # Find the driver it is bound to
                module_path = '/sys/bus/pci/devices/{}/driver/module'.format(slot)
                if os.path.exists(module_path):
                    ret = os.readlink(module_path)
                    driver = os.path.basename(ret)
                else:
                    driver = 'none'

                # Find the vfio device path
                if driver == 'vfio_pci':
                    device_path = '/dev/vfio/{}'.format(iommu_group)
                    device_owner = pathlib.Path(device_path).owner()
                else:
                    device_path = ''
                    device_owner = ''

                # Only devices that are not mounted show up in the list of available devices
                if not mounted:
                    vfio_dev = SysVfioIfc(slot,
                                          iommu_group,
                                          device_path,
                                          init=False,
                                          pci_vid=dev_pci_vid,
                                          pci_did=dev_pci_did,
                                          driver=driver,
                                          owner=device_owner,
                                          info_string=lspci_info)

                    # Add it to the list
                    available_devices.append(vfio_dev)
                else:
                    logger.warning('Device {} ({}) is not available because it is mounted!'.format(
                        dev_name, slot))

        return available_devices
