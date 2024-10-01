import ctypes
import time
import enum

from lone.system import System, DMADirection
from lone.injection import Injection
from lone.nvme.spec.queues import QueueMgr, NVMeSubmissionQueue, NVMeCompletionQueue
from lone.nvme.spec.prp import PRP
from lone.nvme.spec.structures import CQE
from lone.nvme.spec.commands.admin.create_io_completion_q import CreateIOCompletionQueue
from lone.nvme.spec.commands.admin.create_io_submission_q import CreateIOSubmissionQueue
from lone.nvme.spec.commands.admin.delete_io_completion_q import DeleteIOCompletionQueue
from lone.nvme.spec.commands.admin.delete_io_submission_q import DeleteIOSubmissionQueue
from lone.nvme.spec.commands.status_codes import status_codes
from lone.nvme.device.identify import NVMeDeviceIdentifyData

import logging
logger = logging.getLogger('nvme_device')


class NVMeDeviceIntType(enum.Enum):
    POLLING = 0
    INTX = 1
    MSI = 2
    MSIX = 3


class CidMgr:
    ''' Manager class to track CID values for NVMe commands
        TODO: Need to add tracking and checks to forbid allocating
        a sqid/cid pair that is currently outstanding. Not an issue
        unless the user is sending more than max_value - init_value
        commands at a time.
    '''
    def __init__(self, init_value=0x1000, max_value=0xFFFE):
        self.init_value = init_value
        self.max_value = max_value
        self.value = self.init_value

    def alloc(self):
        # Get next value
        value = self.value

        # Increment and wrap if needed
        self.value = self.value + 1
        if self.value >= self.max_value:
            self.value = self.init_value

        # Return it
        return value


class NVMeDeviceCommon:

    def __init__(self,
                 pci_slot,
                 pcie_regs,
                 nvme_regs,
                 mem_mgr,
                 sq_entry_size=64,
                 cq_entry_size=16):

        # Save values passed in
        self.pci_slot = pci_slot
        self.pcie_regs = pcie_regs
        self.nvme_regs = nvme_regs
        self.mem_mgr = mem_mgr
        self.sq_entry_size = sq_entry_size
        self.cq_entry_size = cq_entry_size

        # CID manager
        self.cid_mgr = CidMgr()

        # NVMe Queue manager
        self.queue_mgr = QueueMgr()

        # List of outstanding commands
        self.outstanding_commands = {}

        # Injectors
        self.injectors = Injection()

        # Interrupt type for this drive, None is polling
        self.int_type = NVMeDeviceIntType.POLLING
        self.get_completions = self.poll_cq_completions

        # Identify data for the device, no init until the user
        #   requests it
        self.id_data = NVMeDeviceIdentifyData(self, initialize=False)

    def initiate_flr(self):
        pcie_cap = [cap for cap in self.pcie_regs.capabilities if
                    cap._cap_id_ is self.pcie_regs.PCICapExpress._cap_id_][0]
        pcie_cap.PXDC.IFLR = 1

    def cc_disable(self, timeout_s=10):
        start_time = time.time()

        # Tell the drive to disable
        self.nvme_regs.CC.EN = 0

        # Clear BME
        self.pcie_regs.CMD.BME = 0

        while True:
            if (time.time() - start_time) > timeout_s:
                assert False, 'Device did not disable in {}s'.format(timeout_s)
            elif self.nvme_regs.CSTS.CFS == 1:
                logger.error('Disabling while CFS=1, not watiting for RDY=1')
                break
            elif self.nvme_regs.CSTS.RDY == 0:
                break
            time.sleep(0)

        # Clear all doorbells
        for sqdnbs in self.nvme_regs.SQNDBS:
            sqdnbs.SQTAIL = 0
            sqdnbs.CQHEAD = 0

        # Reset queue manager since all queues are gone after a disable
        # TODO: Technically the user can keep the admin queues intact
        #  during a disable, so we should allow that here. For now, after a
        #  disable, the user is expected to re-init admin queues
        self.queue_mgr = QueueMgr()

        # Any command that was outstanding is gone now. All their memory is now free as well.
        self.outstanding_commands = {}

    def cc_enable(self, timeout_s=10):
        start_time = time.time()
        self.nvme_regs.CC.EN = 1

        while True:
            if (time.time() - start_time) > timeout_s:
                assert False, 'Device did not enable in {}s'.format(timeout_s)
            elif self.nvme_regs.CSTS.CFS == 1:
                assert False, 'Enabling while CFS=1, not watiting for RDY=1'
                break
            elif self.nvme_regs.CSTS.RDY == 1:
                break
            time.sleep(0)

    def init_admin_queues(self, asq_entries, acq_entries):
        # Make sure the device is disabled before messing with queues
        self.cc_disable()

        # Allocate admin queue memory
        asq_mem = self.mem_mgr.malloc(self.sq_entry_size * asq_entries,
                                      DMADirection.HOST_TO_DEVICE,
                                      client='asq')

        acq_mem = self.mem_mgr.malloc(self.cq_entry_size * acq_entries,
                                      DMADirection.DEVICE_TO_HOST,
                                      client='acq')

        # Stop the device from mastering the bus while we set admin queues up
        self.pcie_regs.CMD.BME = 0

        # Set up our ADMIN queues
        self.nvme_regs.AQA.ASQS = asq_entries - 1  # Zero based
        self.nvme_regs.ASQ.ASQB = asq_mem.iova
        self.nvme_regs.AQA.ACQS = acq_entries - 1  # Zero based
        self.nvme_regs.ACQ.ACQB = acq_mem.iova

        # Set up CC
        self.nvme_regs.CC.IOSQES = 6  # 2 ** 6 = 64 bytes per command entry
        self.nvme_regs.CC.IOCQES = 4  # 2 ** 4 = 16 bytes per completion entry

        # Enable all command sets supported by the device
        if self.nvme_regs.CAP.CSS == 0x40:
            self.nvme_regs.CC.CSS = 0x06

        # Re-enable BME so the device can master the bus
        self.pcie_regs.CMD.BME = 1

        # Add the Admin queue pair
        self.queue_mgr.add(NVMeSubmissionQueue(
                           asq_mem,
                           asq_entries,
                           self.sq_entry_size,
                           0,
                           ctypes.addressof(self.nvme_regs.SQNDBS[0])),
                           NVMeCompletionQueue(acq_mem,
                           acq_entries,
                           self.cq_entry_size,
                           0,
                           ctypes.addressof(self.nvme_regs.SQNDBS[0]) + 4,
                           0))

    def create_io_queue_pair(self,
                             cq_entries, cq_id, cq_iv, cq_ien, cq_pc,
                             sq_entries, sq_id, sq_prio, sq_pc, sq_setid):

        # Allocate memory for the completion queue, and map with for write with the iommu
        cq_mem = self.mem_mgr.malloc(self.cq_entry_size * cq_entries,
                                     DMADirection.DEVICE_TO_HOST,
                                     client=f'iocq_{cq_id}')

        # Create the CreateIOCompletionQueue command
        create_iocq_cmd = CreateIOCompletionQueue()
        create_iocq_cmd.DPTR.PRP.PRP1 = cq_mem.iova
        create_iocq_cmd.QSIZE = cq_entries - 1  # zero-based value
        create_iocq_cmd.QID = cq_id
        create_iocq_cmd.IEN = cq_ien
        create_iocq_cmd.PC = cq_pc

        if self.int_type == NVMeDeviceIntType.MSIX:
            assert cq_iv <= self.num_msix_vectors, (
                   'Invalid Interrupt requested: {}, num_msix_vectors: {}').format(
                       cq_iv, self.num_msix_vectors)
            create_iocq_cmd.IV = cq_iv
        else:
            create_iocq_cmd.IV = 0

        # Send the command and wait for a completion
        self.sync_cmd(create_iocq_cmd)

        # Allocate memory for the submission queue, and map with for read with the iommu
        sq_mem = self.mem_mgr.malloc(self.sq_entry_size * sq_entries,
                                     DMADirection.HOST_TO_DEVICE,
                                     client=f'iosq_{sq_id}')

        # Create the CreateIOSubmissionQueue command
        create_iosq_cmd = CreateIOSubmissionQueue()
        create_iosq_cmd.DPTR.PRP.PRP1 = sq_mem.iova
        create_iosq_cmd.QSIZE = sq_entries - 1  # zero-based value
        create_iosq_cmd.QID = sq_id
        create_iosq_cmd.CQID = cq_id
        create_iosq_cmd.QPRIO = sq_prio
        create_iosq_cmd.PC = sq_pc
        create_iosq_cmd.NVMSETID = sq_setid

        # Send the command and wait for a completion
        self.sync_cmd(create_iosq_cmd, timeout_s=1)

        # Add the NVM queue pair to the queue manager
        self.queue_mgr.add(NVMeSubmissionQueue(
                           sq_mem,
                           sq_entries,
                           self.sq_entry_size,
                           sq_id,
                           ctypes.addressof(self.nvme_regs.SQNDBS[0]) + (sq_id * 8)),
                           NVMeCompletionQueue(
                           cq_mem,
                           cq_entries,
                           self.cq_entry_size,
                           cq_id,
                           ctypes.addressof(self.nvme_regs.SQNDBS[0]) + ((cq_id * 8) + 4),
                           cq_iv),
                           )

    def create_io_queues(self, num_queues=10, queue_entries=256, sq_nvme_set_id=0):

        # Has the ADMIN queue been initialized?
        assert self.nvme_regs.AQA.ASQS != 0, 'admin queues are NOT initialized!'
        assert self.nvme_regs.ASQ.ASQB != 0, 'admin queues are NOT initialized!'
        assert self.nvme_regs.AQA.ACQS != 0, 'admin queues are NOT initialized!'
        assert self.nvme_regs.ACQ.ACQB != 0, 'admin queues are NOT initialized!'

        # Create each queue requested
        for queue_id in range(1, num_queues + 1):
            self.create_io_queue_pair(
                queue_entries, queue_id, queue_id, 1, 1,
                queue_entries, queue_id, 0, 1, 0)

    def delete_io_queues(self):

        # First delete all submission queues
        for (sqid, cqid), (sq, cq) in self.queue_mgr.nvme_queues.items():

            # Never delete Admin queues
            if sqid == 0 and cqid == 0:
                continue

            # Delete IO submission queue
            del_sq_cmd = DeleteIOSubmissionQueue(QID=sqid)
            self.sync_cmd(del_sq_cmd, timeout_s=1)
            self.queue_mgr.remove_sq(sqid)

        # Then delete all completion queues
        for (sqid, cqid), (sq, cq) in list(self.queue_mgr.nvme_queues.items()):

            # Never delete Admin queues
            if sqid == 0 and cqid == 0:
                continue

            # Delete IO completion queue
            del_cq_cmd = DeleteIOCompletionQueue(QID=cqid)
            self.sync_cmd(del_cq_cmd, timeout_s=1)
            self.queue_mgr.remove_cq(cqid)

    def posted_command(self):
        ''' Interface that can be overridden by custom devices that need to know
            when a command is posted (useful for simulators).
        '''
        pass

    def post_command(self, command):

        # Set a CID for the command
        command.CID = self.cid_mgr.alloc()

        # Post the command on the next available sq slot
        command.sq.post_command(command)
        self.posted_command()

        # Keep track of outstanding commands
        self.outstanding_commands[(command.CID, command.sq.qid)] = command

        command.start_time_ns = time.perf_counter_ns()

    def poll_cq_completions(self, cqids=None, max_completions=1, max_time_s=0):

        if cqids is None:
            cqids = [cq.qid for cq in self.queue_mgr.get_cqs()]
        else:
            if type(cqids) is int:
                cqids = [cqids]

        max_time = time.time() + max_time_s
        num_completions = 0
        while True:

            for cqid in cqids:
                if self.get_completion(cqid) is True:
                    num_completions += 1

            if num_completions >= max_completions:
                break

            if time.time() > max_time:
                break

            if self.nvme_regs.CSTS.CFS == 1:
                logger.error('CFS = 1 while looking for completions!')
                break

            # Yield in case other threads are running
            time.sleep(0)

        return num_completions

    def get_completion(self, cqid):

        if cqid == 0:
            _, cq = self.queue_mgr.get(0, 0)
        else:
            _, cq = self.queue_mgr.get(None, cqid)

        # Figure out where the next completion should be coming to
        cqe = cq.get_next_completion()

        # Wait for the completion by polling for the phase bit change
        if cqe.SF.P == cq.phase:

            command = self.outstanding_commands[(cqe.CID, cqe.SQID)]
            self.complete_command(command, cqe)
            return True
        else:
            return False

    def get_msix_completions(self, cqids=None, max_completions=1, max_time_s=0):
        cqs = []

        if cqids is None:
            cqs = [cq for cq in self.queue_mgr.get_cqs()]
        elif type(cqids) is int:
            sq, cq = self.queue_mgr.get(None, cqids)
            if cq is not None:
                cqs = [self.queue_mgr.get(None, cqids)[1]]
        else:
            assert False, 'Invalid cqids type'

        # If we didn't find a cq to look for completions in just return 0
        if len(cqs) == 0:
            return 0

        max_time = time.time() + max_time_s
        num_completions = 0

        # Process completion by first waiting on the MSI-X interrupt for the
        #   completion queue we are waiting for a completion at
        while True:
            # Yield in case other threads are running
            time.sleep(0)

            for cq in cqs:
                vector = cq.int_vector
                if self.get_msix_vector_pending_count(vector):
                    while self.get_completion(cq.qid):
                        num_completions += 1

            if num_completions >= max_completions:
                break

            if time.time() > max_time:
                break

            if self.nvme_regs.CSTS.CFS == 1:
                logger.error('CFS = 1 while looking for completions!')
                break

        return num_completions

    def complete_command(self, command, cqe):

        # Mark the time the command was completed as soon as we find it!
        command.end_time_ns = time.perf_counter_ns()

        # Get the next completion
        assert command.posted is True, 'not posted'
        assert command.CID == cqe.CID, 'cqid mismatch'
        assert command.sq.qid == cqe.SQID, 'sqid mismatch'

        command.posted = False
        command.complete = True
        ctypes.memmove(ctypes.addressof(command.cqe),
                       ctypes.addressof(cqe),
                       ctypes.sizeof(CQE))

        # Remove from our outstanding_commands list
        del self.outstanding_commands[(command.CID, command.sq.qid)]

        # If there was data in, then grab it from PRPs and copy to
        #   the data in object
        if command.data_in is not None:
            command.data_in = command.data_in_type.from_buffer_copy(command.prp.get_data_buffer())

        # Consume the completion we just processed in the queue
        command.cq.consume_completion()

        # Advance the SQ head for the command based on what is on the completion
        command.sq.head.set(cqe.SQHD)

    def process_completions(self, cqids=None, max_completions=1, max_time_s=0):
        return self.get_completions(cqids, max_completions, max_time_s)

    def sync_cmd(self, command, sqid=None, cqid=None, timeout_s=10, check=True):

        # Start the command
        self.start_cmd(command, sqid, cqid)

        # Get completions, this function is setup based on what interrupts we are using
        self.get_completions(command.cq.qid, 1, timeout_s)

        # Make sure it is in complete state
        assert command.complete is True, 'Command not complete at the end of sync_cmd'

        # Check for successful completion, will raise if not success
        if check:
            status_codes.check(command)

    def start_cmd(self, command, sqid=None, cqid=None):

        if sqid is None:
            if command.cmdset_admin:
                sqid = 0
                cqid = 0
            else:
                sqid = self.queue_mgr.next_iosq_id()

        # Get command queues
        sq, cq = self.queue_mgr.get(sqid, cqid)
        assert sq is not None and cq is not None, "No queue to send command to!"
        command.sq, command.cq = sq, cq

        # Sanity checks
        assert (command.CID, command.sq.qid) not in self.outstanding_commands.keys(), (
            'Command already with the drive, impossible to identify completion')
        assert command.posted is not True, 'Command already posted'
        assert command.complete is not True, 'Command already completed'

        # Post the command on the next available sq slot
        self.post_command(command)
        command.posted = True

        # Return the qpair in which the command was posted
        return sqid, cq.qid

    def alloc(self, command, bytes_per_block=None):
        set_buffer = False
        size = None

        # Special handling for reads and writes
        if command.__class__.__name__ == 'Write':
            assert bytes_per_block is not None, 'Must pass in bytes_per_block for Write commands'
            direction = DMADirection.HOST_TO_DEVICE
            size = (command.NLB + 1) * bytes_per_block

        elif command.__class__.__name__ == 'Read':
            assert bytes_per_block is not None, 'Must pass in bytes_per_block for Read commands'

            direction = DMADirection.DEVICE_TO_HOST
            size = (command.NLB + 1) * bytes_per_block

        else:
            # Not reads and writes
            if hasattr(command, 'data_in_type') and command.data_in_type is not None:
                direction = DMADirection.DEVICE_TO_HOST
                size = len(command.data_in)

            if hasattr(command, 'data_out_type') and command.data_out_type is not None:
                direction = DMADirection.HOST_TO_DEVICE
                size = len(command.data_out)
                set_buffer = True

        assert size is not None, 'Could not figure out size for command'

        # Allocate memory, set PRPs
        prp = PRP(self.mem_mgr, size,
                  self.mem_mgr.page_size,
                  direction,
                  ' '.join([hex(id(command)), command.__class__.__name__]))

        # Set PRP
        command.prp = prp
        command.DPTR.PRP.PRP1 = prp.prp1
        command.DPTR.PRP.PRP2 = prp.prp2

        if set_buffer:
            # Copy data out to it
            prp.set_data_buffer(bytes(command.data_out))


def NVMeDevice(pci_slot):
    ''' Helper function to allow tests/modules/etc to pick a physical or simulated
        device by using the special nvsim pci_slot name. Any other name is treated
        as a real device in the pci bus
    '''
    if pci_slot == 'nvsim':
        from nvsim.simulators.generic import GenericNVMeNVSimDevice
        return GenericNVMeNVSimDevice()
    else:
        return NVMeDevicePhysical(pci_slot)


class NVMeDevicePhysicalNotFoundError(Exception):
    pass


class NVMeDevicePhysical(NVMeDeviceCommon):
    ''' Implementation that accesses a physical nvme device on the
          pcie bus via vfio
    '''
    def __init__(self, pci_slot):
        # Create a pci_userspace_device, then get pcie and nvme regs
        device_found = False
        try:
            self.pci_userspace_device = System.PciUserspaceDevice(pci_slot)
            device_found = True
        except Exception as e:
            e

        # Raise exception if we didn't find a device at pci_slot
        if not device_found:
            raise NVMeDevicePhysicalNotFoundError(f'Not able to access {pci_slot}')

        pci_regs = self.pci_userspace_device.pci_regs()
        pci_regs.init_capabilities()

        nvme_regs = self.pci_userspace_device.nvme_regs()

        # Memory manager
        self.mps = 2 ** (12 + nvme_regs.CC.MPS)
        mem_mgr = System.DevMemMgr(self.mps,
                                   self.pci_userspace_device.map_dma_region_read,
                                   self.pci_userspace_device.map_dma_region_write,
                                   self.pci_userspace_device.unmap_dma_region,
                                   self.pci_userspace_device.iova_ranges)

        # Initialize NVMeDeviceCommon
        super().__init__(pci_slot,
                         pci_regs,
                         nvme_regs,
                         mem_mgr)

    def init_msix_interrupts(self, num_vectors, start=0):
        self.num_msix_vectors = start + num_vectors
        self.pci_userspace_device.enable_msix(num_vectors, start)
        self.int_type = NVMeDeviceIntType.MSIX
        self.get_completions = self.get_msix_completions

    def get_msix_vector_pending_count(self, vector):
        return self.pci_userspace_device.get_msix_vector_pending_count(vector)
