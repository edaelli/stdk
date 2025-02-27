''' OS Independent interfaces
'''
import sys
import platform
import abc
import ctypes
import importlib.util
from enum import Enum

from lone.util.hexdump import hexdump_print

# Always import and enable faulthandler
import faulthandler
faulthandler.enable()


class SysPci(metaclass=abc.ABCMeta):
    ''' Interface to access the PCI subsystem within an Operating System
    '''
    @abc.abstractmethod
    def rescan(self):
        ''' Rescans the PCI bus
        '''
        raise NotImplementedError


class SysPciDevice(metaclass=abc.ABCMeta):
    ''' Interface to access one PCI device within an Operating System
    '''
    def __init__(self, pci_slot):
        self.pci_slot = pci_slot

    @abc.abstractmethod
    def exists(self):
        ''' Returns true if this device exists in the OS, false otherwise
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def remove(self):
        ''' Remove the device from the OS
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def expose(self, user):
        ''' Exposes the device to a user in userspace
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def reclaim(self, driver):
        ''' Reclaims the device from a user in userspace and
            tries to bind it to the requested driver
        '''
        raise NotImplementedError


class SysPciUserspace(metaclass=abc.ABCMeta):
    ''' Interface to interact to an Operating System's PCI userspace access
        Implemented with VFIO in Linux
    '''
    @abc.abstractmethod
    def devices(self):
        ''' List available devices
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def exposed_devices(self):
        ''' List available devices that have been exposed to a user in userspace
        '''
        raise NotImplementedError


class SysPciUserspaceDevice(metaclass=abc.ABCMeta):
    ''' Interface to access a Pci device from userspace, generally through
        the system's IOMMU for secure access
        Implemented with VFIO in Linux
    '''
    def __init__(self, pci_slot, pci_vid=None, pci_did=None,
                 driver=None, owner=None, info_string=None):
        self.pci_slot = pci_slot
        self.pci_vid = pci_vid
        self.pci_did = pci_did
        self.driver = driver
        self.owner = owner
        self.info_string = info_string

    @abc.abstractmethod
    def pci_regs(self):
        ''' Returns an object with the pci registers for the device
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def nvme_regs(self):
        ''' Returns an object with the nvme registers for the device
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def map_dma_region_read(self, vaddr, iova, size):
        ''' Map a DMA region for READ ONLY
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def map_dma_region_write(self, vaddr, iova, size):
        ''' Map a DMA region for WRITE ONLY
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def map_dma_region_rw(self, vaddr, iova, size):
        ''' Map a DMA region for WRITE ONLY
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def unmap_dma_region(self, iova, size):
        ''' Unmap DMA region
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def reset(self):
        ''' Reset the device
        '''
        raise NotImplementedError


class DMADirection(Enum):
    ''' DMA directions for memory transfer and mapping
    '''
    HOST_TO_DEVICE = 1
    DEVICE_TO_HOST = 2
    BIDIRECTIONAL = 3


class MemoryLocation:
    ''' Generic memory location object
    '''
    def __init__(self, vaddr, iova, size, client):
        self.vaddr = vaddr
        self.size = size
        self.iova = iova
        self.client = client
        self.in_use = False
        self.iova_mapped = False
        self.iova_direction = None

        # List of addresses that are linked (wrt being allocated or not to this memory)
        self.linked_mem = []


class DevMemMgr(metaclass=abc.ABCMeta):
    ''' Base DevMemMgr interface object
    '''
    def __init__(self, page_size):
        ''' Initializes a DevMemMgr manager
        '''
        self.page_size = page_size

    @abc.abstractmethod
    def malloc(self, size, direction, client=None):
        ''' Allocates low level system memory
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def free(self, memory):
        ''' Frees previoulsy allocated memory
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def free_all(self):
        ''' Free all memory we previously allocated
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def allocated_mem_list(self):
        ''' Returns a list of all allocated memory
        '''
        raise NotImplementedError

    def __str__(self):
        ret = ''
        if len(self.allocated_mem_list()):
            ret = '{:<50} {:>18}   {:>10}     {:>8}  {:4}  {:4}  {}\n'.format(
                'client', 'vaddr', 'iova', 'size', 'in_use', 'iova_mapped', 'direction')
            for m in self.allocated_mem_list():
                ret += (f'{m.client:<50} 0x{m.vaddr:016X}   0x{m.iova:08X}   0x{m.size:08X}  '
                        f'{m.in_use:>6}  {m.iova_mapped:>11}  {m.iova_direction}\n')
        return ret

    def dump(self, dumper=print):
        for m in self.allocated_mem_list():
            data = (ctypes.c_uint8 * m.size).from_address(m.vaddr)

            dumper(f'client:         {m.client}')
            dumper(f'vaddr:          0x{m.vaddr:X}')
            dumper(f'iova:           0x{m.iova:X}')
            dumper(f'size:           0x{m.size:X}')
            dumper(f'in_use:         {m.in_use}')
            dumper(f'iova_mapped:    {m.iova_mapped}')
            dumper(f'iova_direction: {m.iova_direction}')
            hexdump_print(data, printer=dumper)
            dumper()


# Now for each supported OS, pick the objects that implement the
#  interfaces above
if platform.system() == 'Linux':
    from lone.system.linux import pci, vfio
    syspci = pci.LinuxSysPci
    syspci_device = pci.LinuxSysPciDevice
    syspci_userspace = vfio.SysVfio
    syspci_userspace_device = vfio.SysVfioIfc

    # If the user is calling this before installing lone
    #   hugepages will not be there. We don't want to fail
    #   here so just leave the DevMemMgr empty
    # Using importlib to be able to test it in unittests
    mem_mgr = None
    hp_spec = importlib.util.find_spec('lone.system.linux.hugepages_mgr')
    if hp_spec is not None:
        try:
            hp_module = importlib.util.module_from_spec(hp_spec)
            sys.modules['hugepages_mgr'] = hp_module
            hp_spec.loader.exec_module(hp_module)
            mem_mgr = hp_module.HugePagesMemoryMgr
        except ModuleNotFoundError:
            mem_mgr = None
else:
    raise NotImplementedError


class System:
    Pci = syspci
    PciDevice = syspci_device
    PciUserspace = syspci_userspace
    PciUserspaceDevice = syspci_userspace_device
    DevMemMgr = mem_mgr
