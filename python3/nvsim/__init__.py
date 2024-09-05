import time
import ctypes
import threading

from types import SimpleNamespace

from lone.nvme.device import NVMeDeviceCommon
from lone.system import DevMemMgr, MemoryLocation
from lone.nvme.spec.registers.pcie_regs import PCIeRegistersDirect
from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect
from nvsim.state import NVSimState
from nvsim.reg_handlers.pcie import PCIeRegChangeHandler
from nvsim.reg_handlers.nvme import NVMeRegChangeHandler

import logging
logger = logging.getLogger('nvsim_thread')


class NVSimThread(threading.Thread):
    def __init__(self, nvme_device):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.exception = None

        self.nvme_device = nvme_device
        self.nvsim_state = NVSimState(nvme_device)
        self.pcie_handler = PCIeRegChangeHandler(self.nvsim_state)
        self.nvme_handler = NVMeRegChangeHandler(self.nvsim_state)

    def stop(self):
        self.stop_event.set()

    def run(self):

        while True:
            try:
                # Check for changes to pcie registers and act on them
                self.pcie_handler()
                self.nvme_handler()
            except Exception as e:
                logger.exception('NVSimThread EXCEPTION!')
                self.exception = e
                self.nvme_device.nvme_regs.CSTS.CFS = 1
                break

            # Exit if the main thread is not alive anymore
            if not threading.main_thread().is_alive():
                break

            # Check if we were asked to stop
            if self.stop_event.is_set():
                break

            # Briefly yield so other tasks can run
            time.sleep(1 / 1000000)

        del self.nvsim_state
        del self.pcie_handler
        del self.nvme_handler


class NVMeSimulator(NVMeDeviceCommon):
    ''' Implementation that uses a simulator thread to simulate a NVMe device
    '''

    class SimMemMgr(DevMemMgr):
        ''' Simulated memory implemenation
        '''
        def __init__(self, page_size):
            ''' Initializes a memory manager
            '''
            self.page_size = page_size
            self._allocated_mem_list = []

            # TODO: Clean this up
            self.iova_mgr = SimpleNamespace(reset=lambda: True)

        def malloc(self, size, direction, client=None):
            memory_obj = (ctypes.c_uint8 * size)()

            # Append to our list so it stays allocated until we choose to free it
            vaddr = ctypes.addressof(memory_obj)

            # Create the memory location object from the allocated memory above
            mem = MemoryLocation(vaddr, vaddr, size, client)
            mem.mem_obj = memory_obj
            self._allocated_mem_list.append(mem)

            return mem

        def malloc_pages(self, num_pages, client=None):
            pages = []
            for page_idx in range(num_pages):
                pages.append(self.malloc(self.page_size))
            return pages

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, exc_traceback):
            pass

        def free(self, memory):
            for m in self._allocated_mem_list:
                if m == memory:
                    self._allocated_mem_list.remove(m)

        def free_all(self):
            self._allocated_mem_list = []

        def allocated_mem_list(self):
            return self._allocated_mem_list

    def initialize_pcie_caps(self, pcie_regs):
        pcie_regs.CAP.CP = type(pcie_regs).CAPS.offset
        next_ptr = pcie_regs.CAP.CP
        next_addr = ctypes.addressof(pcie_regs) + next_ptr

        # Make one of every cap we know of for the simulator
        for t in [pcie_regs.PCICapPowerManagementInterface,
                  pcie_regs.PCICapMSI,
                  pcie_regs.PCICapExpress,
                  pcie_regs.PCICapMSIX,
                  pcie_regs.PCICapabilityUnknown]:
            c = t.from_address(next_addr)
            c.CAP_ID = type(c)._cap_id_
            next_ptr += ctypes.sizeof(c)
            next_addr += ctypes.sizeof(c)
            if type(c) is pcie_regs.PCICapabilityUnknown:
                c.NEXT_PTR = 0
            else:
                c.NEXT_PTR = next_ptr

        next_ptr = 0x100
        next_addr = ctypes.addressof(pcie_regs) + next_ptr

        # Now for extended caps
        for t in [pcie_regs.PCICapExtendedAer,
                  pcie_regs.PCICapExtendeDeviceSerialNumber,
                  pcie_regs.PCICapabilityExtUnknown]:
            c = t.from_address(next_addr)
            c.CAP_ID = type(c)._cap_id_
            next_ptr += ctypes.sizeof(c)
            next_addr += ctypes.sizeof(c)
            if type(c) is pcie_regs.PCICapabilityExtUnknown:
                c.NEXT_PTR = 0
            else:
                c.NEXT_PTR = next_ptr

    def __init__(self, pci_slot):
        assert pci_slot == 'nvsim', (
            'Trying to instantiate simulator with {} for pci_slot'.format(pci_slot))
        self.sim_thread_started = False

        # Create the object to access PCIe registers, and init cababilities
        pcie_regs = PCIeRegistersDirect()
        self.initialize_pcie_caps(pcie_regs)
        pcie_regs.init_capabilities()

        # Create the object to access NVMe registers
        nvme_regs = NVMeRegistersDirect()

        # Create our memory manager
        self.mps = 4096
        mem_mgr = NVMeSimulator.SimMemMgr(self.mps)

        # Initialize NVMeDeviceCommon
        super().__init__(pci_slot,
                         None,
                         pcie_regs,
                         nvme_regs,
                         mem_mgr)

        # Start the simulator thread
        self.sim_thread = NVSimThread(self)
        self.sim_thread.daemon = True
        self.sim_thread.start()
        logger.info('NVSimThread started')

    def malloc_and_map_iova(self, num_bytes, direction, client='malloc_and_map_iova'):
        # Allocate memory
        mem = self.mem_mgr.malloc(num_bytes, client=client)

        # Save off the direction so that the simulator can use it
        mem.direction = direction

        # Return it
        return mem

    def free_and_unmap_iova(self, memory):
        # Free memory
        self.mem_mgr.free(memory)

    def __del__(self):
        # Stop and join the thread when the nvsim object goes out of scope (and eventually
        #   gets gc'd because at that point it should stop accessing any memory!
        if self.sim_thread_started:
            self.sim_thread.stop()
            self.sim_thread.join()
