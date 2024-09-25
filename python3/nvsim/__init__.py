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

    def stop(self):
        self.stop_event.set()

    def run(self):

        while True:
            try:
                # Check for changes to pcie registers and act on them
                self.nvme_device.pcie_handler()
                self.nvme_device.nvme_handler()
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

        del self.nvme_device


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


class NVMeSimulator(NVMeDeviceCommon):
    ''' Implementation that uses a simulator thread to simulate a NVMe device
    '''
    def add_caps(self, pcie_regs, cap_list):
        pcie_regs.CAP.CP = type(pcie_regs).CAPS.offset
        next_ptr = pcie_regs.CAP.CP
        next_addr = ctypes.addressof(pcie_regs) + next_ptr

        # Combine generic and extended into their own lists
        gen_caps = [cap for cap in cap_list if
                    pcie_regs.PCICapability in type(cap).__bases__]
        ext_caps = [cap for cap in cap_list if
                    pcie_regs.PCICapabilityExt in type(cap).__bases__]

        for cap in gen_caps:
            # Make sure it is a generic capability
            assert pcie_regs.PCICapability in type(cap).__bases__

            # First copy the cap to the register location
            ctypes.memmove(next_addr, ctypes.addressof(cap), ctypes.sizeof(cap))

            # Then get a ctypes object at that address
            c = type(cap).from_address(next_addr)
            c.CAP_ID = cap._cap_id_

            # Finally set next ptr and next addr
            next_ptr += ctypes.sizeof(cap)
            next_addr += ctypes.sizeof(cap)
            c.NEXT_PTR = next_ptr

        c.NEXT_PTR = 0

        # Now the extended ones starting at offset 0x100
        next_ptr = 0x100
        next_addr = ctypes.addressof(pcie_regs) + next_ptr

        for cap in ext_caps:
            # Make sure it is a generic capability
            assert pcie_regs.PCICapabilityExt in type(cap).__bases__

            # First copy the cap to the register location
            ctypes.memmove(next_addr, ctypes.addressof(cap), ctypes.sizeof(cap))

            # Then get a ctypes object at that address
            c = type(cap).from_address(next_addr)
            c.CAP_ID = cap._cap_id_

            # Finally set next ptr and next addr
            next_ptr += ctypes.sizeof(c)
            next_addr += ctypes.sizeof(c)
            c.NEXT_PTR = next_ptr

        c.NEXT_PTR = 0

    def __init__(self):
        self.sim_thread_started = False

        # Create the object to access PCIe registers, and init cababilities
        pcie_regs = PCIeRegistersDirect()
        self.initialize_pcie_caps(pcie_regs)
        pcie_regs.init_capabilities()

        # Create the object to access NVMe registers
        nvme_regs = NVMeRegistersDirect()

        # Create our memory manager
        self.mps = 4096
        mem_mgr = SimMemMgr(self.mps)

        # Initialize NVMeDeviceCommon
        super().__init__('nvsim',
                         None,
                         pcie_regs,
                         nvme_regs,
                         mem_mgr)

    def start_sim_thread(self):
        # Start the simulator thread
        self.sim_thread = NVSimThread(self)
        self.sim_thread.daemon = True
        self.sim_thread.start()
        logger.info('NVSimThread started')

    def __del__(self):
        # Stop and join the thread when the nvsim object goes out of scope (and eventually
        #   gets gc'd because at that point it should stop accessing any memory!
        if self.sim_thread_started:
            self.sim_thread.stop()
            self.sim_thread.join()


class NVMeSimulatorGenericNVM(NVMeSimulator):
    def __init__(self):
        super().__init__()

        self.nvsim_state = NVSimState(self)
        self.pcie_handler = PCIeRegChangeHandler(self.nvsim_state)
        self.nvme_handler = NVMeRegChangeHandler(self.nvsim_state)

        from nvsim.cmd_handlers.admin import admin_handlers
        from nvsim.cmd_handlers.nvm import nvm_handlers
        self.admin_cmd_handlers = admin_handlers

        self.start_sim_thread()

    def initialize_pcie_caps(self, pcie_regs):
        caps = []
        cap_power_mgmt_ifc = pcie_regs.PCICapPowerManagementInterface()
        caps.append(cap_power_mgmt_ifc)

        cap_msi = pcie_regs.PCICapMSI()
        caps.append(cap_msi)

        cap_express = pcie_regs.PCICapExpress()
        caps.append(cap_express)

        cap_msix = pcie_regs.PCICapMSIX()
        caps.append(cap_msix)

        cap_ext_aer = pcie_regs.PCICapExtendedAer()
        caps.append(cap_ext_aer)

        cap_ext_sn = pcie_regs.PCICapExtendeDeviceSerialNumber()
        caps.append(cap_ext_sn)

        self.add_caps(pcie_regs, caps)
