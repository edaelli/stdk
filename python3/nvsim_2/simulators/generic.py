import ctypes
import traceback

from nvsim_2.simulators import NVSimInterface
from lone.nvme.device import NVMeDeviceCommon
from nvsim_2.cmd_handlers import NVSimCommandNotSupported
from lone.nvme.spec.registers.pcie_regs import PCIeRegistersDirect
from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect
from nvsim_2.simulators.nvsim_thread import NVSimThread
from nvsim_2.reg_handlers.pcie import PCIeRegChangeHandler
from nvsim_2.reg_handlers.nvme import NVMeRegChangeHandler
from nvsim_2.memory import SimMemMgr
from lone.nvme.spec.queues import QueueMgr, NVMeSubmissionQueue, NVMeCompletionQueue
from lone.system import MemoryLocation
from lone.nvme.spec.commands.admin.identify import (IdentifyNamespaceData,
                                                    IdentifyControllerData,
                                                    IdentifyNamespaceListData,
                                                    IdentifyUUIDListData)
from lone.nvme.spec.structures import Generic
from nvsim_2.cmd_handlers.admin import NVSimIdentify

from lone.util.logging import log_init
logger = log_init()


class GenericNVMeNVSimConfig:
    @staticmethod
    def init_pcie_capabilities(pcie_regs):
        # Initialize pcie capabilities we support

        # Power management interface capability
        cap_power_mgmt_ifc = pcie_regs.PCICapPowerManagementInterface()

        # MSI capability
        cap_msi = pcie_regs.PCICapMSI()

        # PCICap capability
        cap_express = pcie_regs.PCICapExpress()

        # MSIX capability
        cap_msix = pcie_regs.PCICapMSIX()

        # Extended AER capability
        cap_ext_aer = pcie_regs.PCICapExtendedAer()

        # Extended SN capability
        cap_ext_sn = pcie_regs.PCICapExtendeDeviceSerialNumber()

        # Now arrange them into the CAP registers as a linked list
        pcie_regs.CAP.CP = type(pcie_regs).CAPS.offset
        next_ptr = pcie_regs.CAP.CP
        next_addr = ctypes.addressof(pcie_regs) + next_ptr

        for cap in [cap_power_mgmt_ifc,
                    cap_msi,
                    cap_express,
                    cap_msix]:
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

        # Terminate the list
        c.NEXT_PTR = 0

        # Now the extended ones starting at offset 0x100
        next_ptr = 0x100
        for cap in [cap_ext_aer,
                    cap_ext_sn]:

            # Make sure it is a generic capability
            assert pcie_regs.PCICapabilityExt in type(cap).__bases__

            # First copy the cap to the register location
            ctypes.memmove(next_addr, ctypes.addressof(cap), ctypes.sizeof(cap))

            # Then get a ctypes object at that address
            c = type(cap).from_address(next_addr)
            c.CAP_ID = cap._cap_id_

            # Finally set next ptr and next addr
            next_ptr += ctypes.sizeof(cap)
            next_addr += ctypes.sizeof(cap)
            c.NEXT_PTR = next_ptr

        # Terminate the list
        c.NEXT_PTR = 0

        # Read our capabilities into a list of capabilities so we can easily
        #  access them when needed
        pcie_regs.init_capabilities()

    @staticmethod
    def init_pcie_regs(pcie_regs):
        pcie_regs.ID.VID = 0xEDDA
        pcie_regs.ID.DID = 0xE771

    @staticmethod
    def init_nvme_regs(nvme_regs):
        nvme_regs.CAP.CSS = 0x40
        nvme_regs.VS.MJR = 0x02
        nvme_regs.VS.MNR = 0x01

    @staticmethod
    def init_id_ctrl_data():
        id_ctrl_data = IdentifyControllerData()

        id_ctrl_data.MN = b'nvsim_0.1'
        id_ctrl_data.SN = b'EDDAE771'
        id_ctrl_data.FR = b'0.001'

        # Power states
        id_ctrl_data.NPSS = 5
        id_ctrl_data.PSDS[0].MXPS = 0
        id_ctrl_data.PSDS[0].MP = 2500
        id_ctrl_data.PSDS[1].MXPS = 0
        id_ctrl_data.PSDS[1].MP = 2200
        id_ctrl_data.PSDS[2].MXPS = 0
        id_ctrl_data.PSDS[2].MP = 2000
        id_ctrl_data.PSDS[3].MXPS = 0
        id_ctrl_data.PSDS[3].MP = 1500
        id_ctrl_data.PSDS[4].MXPS = 0
        id_ctrl_data.PSDS[4].MP = 1000

        return id_ctrl_data

    @staticmethod
    def admin_cmd_handlers():
        # Start with nothing supported
        handlers = [NVSimCommandNotSupported()] * 255

        # Override the ones this simulator supports

        # Return list of handlers, OPC for index
        handlers[NVSimIdentify.OPC] = NVSimIdentify()
        return handlers

    @staticmethod
    def nvm_cmd_handlers():
        # Start with nothing supported
        handlers = [NVSimCommandNotSupported()] * 255

        # Override the ones this simulator supports

        # Return list of handlers, OPC for index
        return handlers

class GenericNVMeNVSim(NVSimInterface):

    def __init__(self, config=GenericNVMeNVSimConfig):
        # Save our config
        self.config = config

        # Create the object to access PCIe registers, and init cababilities
        self.pcie_regs = PCIeRegistersDirect()

        # Create the object to access NVMe registers
        self.nvme_regs = NVMeRegistersDirect()

        # Set our MPS
        self.mps = 4096

        # Initialize internal states for the simulated device
        self.initialize_internal_state()

        # Set our callable handlers
        self.pcie_handler = PCIeRegChangeHandler(self)
        self.nvme_handler = NVMeRegChangeHandler(self)

        # Create our thread, but dont start it until requested
        self.thread = NVSimThread(self)
        self.thread.daemon = True

    def start(self):
        # Start the simulator thread, it will check the handlers
        #  and call our interfaces
        self.thread.start()

    def initialize_internal_state(self):
        # Clear registers
        ctypes.memset(ctypes.addressof(self.pcie_regs), 0, ctypes.sizeof(self.pcie_regs))
        ctypes.memset(ctypes.addressof(self.nvme_regs), 0, ctypes.sizeof(self.nvme_regs))

        # Initialize our pcie capabilities
        self.config.init_pcie_capabilities(self.pcie_regs)

        # Initialize pcie registers
        self.config.init_pcie_regs(self.pcie_regs)

        # Initialize nvme registers
        self.config.init_nvme_regs(self.nvme_regs)

        # Initialize identify structures
        self.id_ctrl_data = self.config.init_id_ctrl_data()

        # Keep a QueueMgr object to track our internal queues
        self.queue_mgr = QueueMgr()

        # Completion queues are added here until a submission queue uses it (the queue
        #   manager takes in pairs of queues, so we have to wait for the create submission
        #   queue command to come in to add it).
        self.completion_queues = []

        # Simulated command handlers
        self.admin_cmd_handlers = self.config.admin_cmd_handlers()
        self.nvm_cmd_handlers = self.config.nvm_cmd_handlers()

    ###############################################################################################
    # NVSimInterface implementation for this device
    ###############################################################################################
    def nvsim_pcie_handler(self):
        self.pcie_handler()

    def nvsim_nvme_handler(self):
        self.nvme_handler()

    def nvsim_exception_handler(self, exception):
        print('Simulator thread raised the following exception exited:')
        print(traceback.format_exc())

        # Set CFS on simulator exceptions so calling code can stop early
        self.nvme_regs.CSTS.CFS = 1

    def nvsim_pcie_regs_changed(self, old_pcie_regs, new_pcie_regs):
        # PCIe register changes handled here

        # First check capabilitiers changed
        for old_cap, new_cap in zip(old_pcie_regs.capabilities, new_pcie_regs.capabilities):
            if old_cap != new_cap:
                if type(new_cap) == new_pcie_regs.PCICapExpress:
                    if old_cap.PXDC.IFLR == 0 and new_cap.PXDC.IFLR == 1:
                        print('Initiate FLR requested!')

        # Then check all other registers
        #  Nothing here yet!

    def nvsim_nvme_regs_changed(self, old_nvme_regs, new_nvme_regs):
        # Nvme register changes handled here

        # Did we just transition from not enabled to enabled?
        if (old_nvme_regs.CC.EN == 0 and new_nvme_regs.CC.EN == 1):
            # Call nvsim_enable simulator interface
            self.enable()

        # Did we just transition from enabled to not enabled?
        if (old_nvme_regs.CC.EN == 1 and
                new_nvme_regs.CC.EN == 0):
            # Call nvsim_disable simulator interface
            self.disable()

        # If we are ready and any of the doorbell sq tails are different
        old_dbs = bytearray(old_nvme_regs.SQNDBS)
        new_dbs = bytearray(new_nvme_regs.SQNDBS)
        if new_nvme_regs.CSTS.RDY == 1 and old_dbs != new_dbs:
            # Check for commands
            self.check_commands()

    @staticmethod
    def check_mem_access(mem):
        ''' Tries to access mem. If this is not successful, then you will see a segfault
        '''
        logger.info('Trying to access 0x{:x} size: {}'.format(mem.vaddr, mem.size))

        data = (ctypes.c_uint8 * (mem.size)).from_address(mem.vaddr)
        data[0] = 0xFF
        data[-1] = 0xFF

        logger.debug('Able to access all memory!')

    def disable(self):
        self.nvme_regs.CSTS.RDY = 0

    def enable(self):
        logger.info('CC.EN 0 -> 1')

        # Log Admin queues addresses and sizes
        logger.debug(f'ASQS   {self.nvme_regs.AQA.ASQS}')
        logger.debug(f'ASQB 0x{self.nvme_regs.ASQ.ASQB:08x}')
        logger.debug(f'ACQS   {self.nvme_regs.AQA.ACQS}')
        logger.debug(f'ACQB 0x{self.nvme_regs.ACQ.ACQB:08x}')

        # Create and check queue memory address
        asq_mem = MemoryLocation(self.nvme_regs.ASQ.ASQB,
                                 self.nvme_regs.ASQ.ASQB,
                                 ((self.nvme_regs.AQA.ASQS + 1) * 64),
                                 'nvsim_asq')
        self.check_mem_access(asq_mem)

        acq_mem = MemoryLocation(self.nvme_regs.ACQ.ACQB,
                                 self.nvme_regs.ACQ.ACQB,
                                 ((self.nvme_regs.AQA.ACQS + 1) * 16),
                                 'nvsim_acq')
        self.check_mem_access(acq_mem)

        # Add ADMIN queue to queue_mgr
        self.queue_mgr.add(
            NVMeSubmissionQueue(
                asq_mem,
                self.nvme_regs.AQA.ASQS + 1,
                64,
                0,
                ctypes.addressof(self.nvme_regs.SQNDBS[0])),
            NVMeCompletionQueue(
                acq_mem,
                self.nvme_regs.AQA.ACQS + 1,
                16,
                0,
                ctypes.addressof(self.nvme_regs.SQNDBS[0]) + 4))

        # Ok, looks like the addresses add up, setting ourselves to ready!
        self.nvme_regs.CSTS.RDY = 1
        logger.info('GenericNVMeNVSimDevice ready (CSTS.RDY = 1)!')


    def check_commands(self):
        # Find all the queues we should look at for commands
        busy_sqs = [(sq, cq) for k, (sq, cq) in
                    self.queue_mgr.nvme_queues.items() if
                    sq is not None and sq.num_entries() > 0]

        # Go through all of them round robin style
        # TODO: Change this around so we drain the ADMIN queue first
        for sq, cq in busy_sqs:
            for sq_index in range(sq.num_entries()):

                # No point in starting a new command if the cq for it is full
                #  This may end up asserting in a legitimate case, but if that happens
                #  we should take a look to see if we can avoid it
                assert cq.is_full() is False, (
                    'CQ id: {} is full, asserting to debug'.format(cq.qid))

                # Get the command
                command = sq.get_command()

                # Handle the command
                if sq.qid == 0:
                    self.admin_cmd_handlers[command.OPC](self, command, sq, cq)
                else:
                    self.nvm_cmd_handlers[command.OPC](self, command, sq, cq)


class GenericNVMeNVSimDevice(NVMeDeviceCommon):
    def __init__(self, pcie_regs, nvme_regs):
        mem_mgr = SimMemMgr(4096)
        super().__init__('GenericNVMeNVSimDevice',
                         pcie_regs,
                         nvme_regs,
                         mem_mgr)


if __name__ == '__main__':

    from lone.nvme.spec.commands.admin.identify import IdentifyController

    # This changes and reacts to register/memory changes as a device
    n = GenericNVMeNVSim()
    n.start()

    # This changes and reacts to register/memory changes as a host
    d = GenericNVMeNVSimDevice(n.pcie_regs, n.nvme_regs)

    for i in range(10):
        if n.thread.is_alive() is False:
            print('thread dead')
            break
        import time
        if i == 1:
            d.init_admin_queues(16, 16)
            d.cc_enable()
        if i == 2:
            id_cmd = IdentifyController()
            d.alloc(id_cmd)
            d.sync_cmd(id_cmd)
            print(id_cmd.data_in.SN, id_cmd.data_in.MN)
        if i == 3:
            d.initiate_flr()
        if i == 9:
            d.cc_disable()
        print('tick')
        time.sleep(1)
        #d.nvme_regs.SQNDBS[0].SQTAIL += 1

