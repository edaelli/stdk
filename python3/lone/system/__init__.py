''' OS Independent interfaces
'''
import sys
import platform
import abc
import ctypes
import importlib.util
from enum import Enum

from lone.util.hexdump import hexdump_print


class SysRequirements(metaclass=abc.ABCMeta):
    ''' Checks that the running hardware meets lone requirements
    '''
    @abc.abstractmethod
    def check_requirements(self):
        raise NotImplementedError


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


class IovaMgr:
    ''' This class manages how IOVAs are assigned to memory
        NOTE: Limits it to 2M requests
    '''
    def __init__(self, iova_base):
        self.iova_base = iova_base
        self.max_iovas = 40000
        self.increment = (2 * 1024 * 1024)
        self.reset()

    def reset(self):
        self.free_iovas = []
        next_available_iova = self.iova_base

        for i in range(self.max_iovas):
            self.free_iovas.append(next_available_iova)
            next_available_iova += self.increment

    def num_allocated_iovas(self):
        return self.max_iovas - len(self.free_iovas)

    def get(self, size):
        assert size < self.increment, f'IOVA max size is {self.increment}, requested {size}'
        return self.free_iovas.pop(0)

    def free(self, iova):
        self.free_iovas.append(iova)

    def used(self, iova):
        self.free_iovas.remove(iova)


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
    def __init__(self, device):
        ''' Initializes a DevMemMgr manager
        '''
        self.device = device
        self.page_size = device.mps
        self.iova_mgr = IovaMgr(0x0ED00000)

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
            ret = '{:<45} {:>18}   {:>10}   {:>10}  {:4}  {:4}  {}\n'.format(
                'client', 'vaddr', 'iova', 'size', 'in_use', 'iova_mapped', 'direction')
            for m in self.allocated_mem_list():
                ret += (f'{m.client:<45} 0x{m.vaddr:016X}   0x{m.iova:08X}'
                        f'0x{m.size:08X}  {m.in_use:>6}  {m.iova_mapped:>11}  {m.iova_direction}\n')
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
    from lone.system.linux import pci, vfio, requirements
    requirements = requirements.LinuxRequirements
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
    Requirements = requirements
    Pci = syspci
    PciDevice = syspci_device
    PciUserspace = syspci_userspace
    PciUserspaceDevice = syspci_userspace_device
    DevMemMgr = mem_mgr
