import ctypes
import mmap

from lone.system import MemoryLocation
from lone.nvme.device import NVMeDeviceCommon
from lone.nvme.spec.registers.pcie_regs import PCIeRegistersDirect
from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect
from lone.nvme.spec.queues import QueueMgr, NVMeSubmissionQueue, NVMeCompletionQueue
from lone.nvme.spec.commands.admin.identify import (IdentifyNamespaceData,
                                                    IdentifyControllerData,
                                                    IdentifyNamespaceListData,
                                                    IdentifyUUIDListData)
from nvsim.simulators import NVSimInterface
from nvsim.simulators.nvsim_thread import NVSimThread
from nvsim.reg_handlers.pcie import PCIeRegChangeHandler
from nvsim.reg_handlers.nvme import NVMeRegChangeHandler
from nvsim.memory import SimMemMgr
from nvsim.cmd_handlers import NVSimCommandNotSupported
from nvsim.cmd_handlers.admin import (NVSimIdentify,
                                      NVSimCreateIOCompletionQueue,
                                      NVSimCreateIOSubmissionQueue,
                                      NVSimDeleteIOCompletionQueue,
                                      NVSimDeleteIOSubmissionQueue,
                                      NVSimGetLogPage,
                                      NVSimFormat,
                                      NVSimGetFeature,
                                      NVSimSetFeature)

from nvsim.cmd_handlers.nvm import (NVSimWrite,
                                    NVSimRead,
                                    NVSimFlush)

from lone.util.logging import log_init
logger = log_init()


class GenericNVMeNVSimNamespace:

    def __init__(self, num_gbs, block_size, path='/tmp/nvsim.dat'):
        self.num_gbs = num_gbs
        self.block_size = block_size
        self.path = path

        if self.block_size == 512:
            self.num_lbas = int(97696368 + (1953504 * (int(num_gbs) - 50.0)))
        elif self.block_size == 4096:
            self.num_lbas = int(12212046 + (244188 * (int(num_gbs) - 50.0)))
        else:
            assert False, '{} block size not supported'.format(self.block_size)

        self.init_storage()

    def init_storage(self):
        # Create the file
        self.fh = open(self.path, 'w+b')
        self.fh.seek((self.num_lbas * self.block_size) - 1)
        self.fh.write(b'\0')
        self.fh.flush()

        # Mmap so we can easily access
        self.mm = mmap.mmap(self.fh.fileno(), 0)

    def idema_size_512(self, num_gbs):
        return int(97696368 + (1953504 * (int(num_gbs) - 50.0)))

    def idema_size_4096(self, num_gbs):
        return int(12212046 + (244188 * (int(num_gbs) - 50.0)))

    def read(self, lba, num_blocks, prp):
        start_byte = (lba * self.block_size)
        end_byte = start_byte + (num_blocks * self.block_size)
        prp.set_data_buffer(self.mm[start_byte:end_byte])

    def write(self, lba, num_blocks, prp):
        start_byte = (lba * self.block_size)
        end_byte = start_byte + (num_blocks * self.block_size)
        self.mm[start_byte:end_byte] = prp.get_data_buffer()[:(self.block_size * num_blocks)]

    def __del__(self):
        self.mm.close()
        self.fh.close()


class GenericNVMeNVSimConfig:

    def __init__(self, pcie_regs, nvme_regs):
        self.pcie_regs = pcie_regs
        self.nvme_regs = nvme_regs

        # Clear registers
        ctypes.memset(ctypes.addressof(self.pcie_regs), 0, ctypes.sizeof(self.pcie_regs))
        ctypes.memset(ctypes.addressof(self.nvme_regs), 0, ctypes.sizeof(self.nvme_regs))

        # Initialize ourselves
        self.init_pcie_capabilities()
        self.init_pcie_regs()
        self.init_nvme_regs()
        self.init_identify_controller()
        self.init_namespaces()
        self.init_cmd_handlers()

        # Keep a QueueMgr object to track our internal queues
        self.queue_mgr = QueueMgr()

        # Completion queues are added here until a submission queue uses it (the queue
        #   manager takes in pairs of queues, so we have to wait for the create submission
        #   queue command to come in to add it).
        self.completion_queues = []

    def init_pcie_capabilities(self):
        # Initialize pcie capabilities we support

        # Power management interface capability
        cap_power_mgmt_ifc = self.pcie_regs.PCICapPowerManagementInterface()

        # MSI capability
        cap_msi = self.pcie_regs.PCICapMSI()

        # PCICap capability
        cap_express = self.pcie_regs.PCICapExpress()

        # MSIX capability
        cap_msix = self.pcie_regs.PCICapMSIX()

        # Extended AER capability
        cap_ext_aer = self.pcie_regs.PCICapExtendedAer()

        # Extended SN capability
        cap_ext_sn = self.pcie_regs.PCICapExtendeDeviceSerialNumber()

        # Now arrange them into the CAP registers as a linked list
        self.pcie_regs.CAP.CP = type(self.pcie_regs).CAPS.offset
        next_ptr = self.pcie_regs.CAP.CP
        next_addr = ctypes.addressof(self.pcie_regs) + next_ptr

        for cap in [cap_power_mgmt_ifc,
                    cap_msi,
                    cap_express,
                    cap_msix]:
            # Make sure it is a generic capability
            assert self.pcie_regs.PCICapability in type(cap).__bases__

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
            assert self.pcie_regs.PCICapabilityExt in type(cap).__bases__

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
        self.pcie_regs.init_capabilities()

    def init_pcie_regs(self):
        self.pcie_regs.ID.VID = 0xEDDA
        self.pcie_regs.ID.DID = 0xE771

    def init_nvme_regs(self):
        self.nvme_regs.CAP.CSS = 0x40
        self.nvme_regs.VS.MJR = 0x02
        self.nvme_regs.VS.MNR = 0x01

        self.nvme_regs.CC.MPS = 0
        self.mps = 4096

    def init_identify_controller(self):
        self.id_ctrl_data = IdentifyControllerData()

        self.id_ctrl_data.MN = b'nvsim_0.1'
        self.id_ctrl_data.SN = b'EDDAE771'
        self.id_ctrl_data.FR = b'0.001'

        # Current power state, start with 0
        self.power_state = 0

        # Power states supported
        self.id_ctrl_data.NPSS = 5
        self.id_ctrl_data.PSDS[0].MXPS = 0
        self.id_ctrl_data.PSDS[0].MP = 2500
        self.id_ctrl_data.PSDS[1].MXPS = 0
        self.id_ctrl_data.PSDS[1].MP = 2200
        self.id_ctrl_data.PSDS[2].MXPS = 0
        self.id_ctrl_data.PSDS[2].MP = 2000
        self.id_ctrl_data.PSDS[3].MXPS = 0
        self.id_ctrl_data.PSDS[3].MP = 1500
        self.id_ctrl_data.PSDS[4].MXPS = 0
        self.id_ctrl_data.PSDS[4].MP = 1000

    def init_namespaces(self):

        # Initialize our namespaces
        self.namespaces = [
            None,  # Namespace 0 is never valid
            GenericNVMeNVSimNamespace(512, 4096, '/tmp/ns1.dat'),
            GenericNVMeNVSimNamespace(960, 4096, '/tmp/ns2.dat'),
        ]
        self.init_namespaces_data()

    def init_namespaces_data(self):

        # Intialize IdentifyNamespaceData for each namespace
        self.id_ns_data = [None]

        for ns in self.namespaces[1:]:
            data = IdentifyNamespaceData()

            data.NSZE = ns.num_lbas
            data.NCAP = ns.num_lbas
            data.NUSE = 0
            data.NSFEAT = 0
            data.NLBAF = 2
            data.FLBAS = 0 if ns.block_size == 512 else 1
            data.MC = 0
            data.DPC = 0
            data.DPS = 0
            data.NMIC = 0
            data.RESCAP = 0
            data.FPI = 0
            data.DLFEAT = 0
            data.NAWUN = 0

            # 2 supported 0 for 512, 1 for 4096
            data.LBAF_TBL[0].MS = 0
            data.LBAF_TBL[0].LBADS = 9
            data.LBAF_TBL[0].RP = 0

            data.LBAF_TBL[1].MS = 0
            data.LBAF_TBL[1].LBADS = 12
            data.LBAF_TBL[1].RP = 0

            self.id_ns_data.append(data)

        # Identify Namespace List Data
        self.id_ns_list_data = IdentifyNamespaceListData()

        # Add every namespace in self.namespaces to the list
        #  0 is not a valid ns, so skip it.
        for ns_id, ns in enumerate(self.namespaces[1:]):
            self.id_ns_list_data.Identifiers[ns_id] = ns_id + 1

        # Identify UUID List Data
        self.id_uuid_list_data = IdentifyUUIDListData()

        self.id_uuid_list_data.UUIDS[0].UUID[0] = 1
        self.id_uuid_list_data.UUIDS[1].UUID[0] = 2
        self.id_uuid_list_data.UUIDS[2].UUID[0] = 3
        self.id_uuid_list_data.UUIDS[3].UUID[0] = 4
        self.id_uuid_list_data.UUIDS[4].UUID[0] = 5
        self.id_uuid_list_data.UUIDS[5].UUID[0] = 6
        self.id_uuid_list_data.UUIDS[6].UUID[0] = 7
        self.id_uuid_list_data.UUIDS[7].UUID[0] = 8
        self.id_uuid_list_data.UUIDS[8].UUID[0] = 9
        self.id_uuid_list_data.UUIDS[9].UUID[0] = 10
        self.id_uuid_list_data.UUIDS[10].UUID[0] = 11
        self.id_uuid_list_data.UUIDS[11].UUID[0] = 12
        self.id_uuid_list_data.UUIDS[12].UUID[0] = 13
        self.id_uuid_list_data.UUIDS[13].UUID[0] = 14
        self.id_uuid_list_data.UUIDS[14].UUID[0] = 15
        self.id_uuid_list_data.UUIDS[15].UUID[0] = 16

    def init_cmd_handlers(self):

        # ADMIN Commands
        self.admin_cmd_handlers = [NVSimCommandNotSupported()] * 256
        for cmd in [NVSimIdentify(),
                    NVSimCreateIOCompletionQueue(),
                    NVSimCreateIOSubmissionQueue(),
                    NVSimDeleteIOCompletionQueue(),
                    NVSimDeleteIOSubmissionQueue(),
                    NVSimGetLogPage(),
                    NVSimFormat(),
                    NVSimGetFeature(),
                    NVSimSetFeature(),
                    ]:
            self.admin_cmd_handlers[cmd.OPC] = cmd

        # NVM Commands
        self.nvm_cmd_handlers = [NVSimCommandNotSupported()] * 256
        for cmd in [NVSimWrite(),
                    NVSimRead(),
                    NVSimFlush()]:
            self.nvm_cmd_handlers[cmd.OPC] = cmd


class GenericNVMeNVSim(NVSimInterface):

    def __init__(self, config_type=GenericNVMeNVSimConfig):
        # Save config
        self.config_type = config_type

        # Create the object to access PCIe registers
        self.pcie_regs = PCIeRegistersDirect()

        # Create the object to access NVMe registers
        self.nvme_regs = NVMeRegistersDirect()

        # Initialize config (and internal states) for the simulated device
        self.config = self.config_type(self.pcie_regs, self.nvme_regs)

        # Set our handlers for the simulation thread
        self.pcie_handler = PCIeRegChangeHandler(self)
        self.nvme_handler = NVMeRegChangeHandler(self)

        # Create our thread, but dont start it until requested
        self.thread = NVSimThread(self)

        # Clear reset flag
        self.reset = False

    def start(self):
        # Start the simulator thread, it will check the handlers
        #  and call our interfaces
        self.thread.start()

    def stop(self):
        self.thread.stop()
        self.thread.join()

    ###############################################################################################
    # NVSimInterface implementation for this device
    ###############################################################################################
    def nvsim_pcie_handler(self):
        self.pcie_handler()

    def nvsim_nvme_handler(self):
        self.nvme_handler()

    def nvsim_exception_handler(self, exception):
        logger.error('Simulator thread raised an exception and is no longer running!')
        logger.exception(exception)

        # Set CFS on simulator exceptions so calling code can stop early
        self.nvme_regs.CSTS.CFS = 1

    def nvsim_pcie_regs_changed(self, old_pcie_regs, new_pcie_regs):
        # PCIe register changes handled here

        # First check capabilitiers changed
        for old_cap, new_cap in zip(old_pcie_regs.capabilities, new_pcie_regs.capabilities):
            if old_cap != new_cap:
                if type(new_cap) is new_pcie_regs.PCICapExpress:
                    if old_cap.PXDC.IFLR == 0 and new_cap.PXDC.IFLR == 1:
                        logger.debug('Initiate FLR requested!')
                        self.config = self.config_type(self.pcie_regs, self.nvme_regs)
                        break

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

        # If we are ready go check for commands
        if new_nvme_regs.CSTS.RDY == 1:
            # Check for commands
            self.check_commands()

    @staticmethod
    def check_mem_access(mem):
        ''' Tries to access mem. If this is not successful, then you will see a segfault
        '''
        logger.debug('Trying to access 0x{:x} size: {}'.format(mem.vaddr, mem.size))

        data = (ctypes.c_uint8 * (mem.size)).from_address(mem.vaddr)
        data[0] = 0xFF
        data[-1] = 0xFF

        logger.debug('Able to access all memory!')

    def disable(self):
        self.nvme_regs.CSTS.RDY = 0

    def enable(self):
        logger.debug('CC.EN 0 -> 1')

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
        self.config.queue_mgr.add(
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
        logger.debug('GenericNVMeNVSimDevice ready (CSTS.RDY = 1)!')

    def check_commands(self):

        # First get all admin commands and handle them (ASQ has highest priority)
        asq, acq = self.config.queue_mgr.get(0, 0)
        if asq is not None and acq is not None:
            command = asq.get_command()
            while command is not None:
                self.config.admin_cmd_handlers[command.OPC](self, command, asq, acq)
                command = asq.get_command()

        # Find all the IO queues we should look at for commands
        busy_sqs = [(sq, cq) for k, (sq, cq) in
                    self.config.queue_mgr.nvme_queues.items() if
                    sq is not None and sq.num_entries() > 0 and sq.qid != 0]

        # Max commands to handle per loop
        cmds_in_qs = sum([sq.num_entries() for sq, cq in busy_sqs])
        nvm_commands_handled = min(100, cmds_in_qs)

        while nvm_commands_handled > 0:
            for sq, cq in busy_sqs:
                command = sq.get_command()
                if command is not None:
                    self.config.nvm_cmd_handlers[command.OPC](self, command, sq, cq)
                    nvm_commands_handled -= 1


class GenericNVMeNVSimDevice(NVMeDeviceCommon):
    def __init__(self):
        self.sim_thread = GenericNVMeNVSim()
        self.sim_thread.start()

        # Get our registers from the simulator thread
        pcie_regs = self.sim_thread.pcie_regs
        nvme_regs = self.sim_thread.nvme_regs

        # Calculate MPS
        self.mps = 2 ** (12 + nvme_regs.CC.MPS)

        # Create memory manager
        mem_mgr = SimMemMgr(self.mps)

        # Create simulated device
        super().__init__('nvsim', pcie_regs, nvme_regs, mem_mgr)

    def __del__(self):
        # Wait until the sim device is gc'd to stop the thread
        #   so we know nobody is waiting on anything from it anymore
        if self.sim_thread.thread.is_alive():
            self.sim_thread.thread.stop()
