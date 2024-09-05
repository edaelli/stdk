import copy
import ctypes
import time

from lone.nvme.spec.queues import QueueMgr, NVMeSubmissionQueue, NVMeCompletionQueue
from lone.system import MemoryLocation
from nvsim.cmd_handlers.admin import admin_handlers
from nvsim.cmd_handlers.nvm import nvm_handlers
from nvsim.cmd_handlers import NvsimCommandHandler

import logging
logger = logging.getLogger('nvsim_nvme')


class NVMeRegChangeHandler:

    def __init__(self, nvsim_state):
        self.nvsim_state = nvsim_state
        self.last_nvme_regs = copy.deepcopy(self.nvsim_state.nvme_regs)

        self.ignore_changes = False
        self.ignore_changes_end_time = None

        self.fail_next_command = False
        self.fail_next_command_sc = None

        self.set_cfs = False

    def check_injectors(self):

        # Check if we are supposed to ignore changes for a certain time
        injector = self.nvsim_state.injectors.get('IgnoreNVMeRegChanges')
        if injector:
            injector.ack = True
            self.ignore_changes = True
            self.ignore_changes_end_time = time.time() + injector.kwargs['timeout_s']

        # Check if we are supposed to fail the next command
        injector = self.nvsim_state.injectors.get('FailCommand')
        if injector:
            injector.ack = True
            self.fail_next_command = True
            self.fail_next_command_sc = injector.kwargs['sc']

        # Check if we are supposed to set the CFS bit
        injector = self.nvsim_state.injectors.get('SetCFS')
        if injector:
            injector.ack = True
            self.set_cfs = True

    def __call__(self):

        # Make a copy right away to minimize things moving under us
        nvme_regs = copy.deepcopy(self.nvsim_state.nvme_regs)

        # Check if our behavior should change based on injectors
        self.check_injectors()

        # Have we been asked to ignore changes?
        if self.ignore_changes:
            if time.time() < self.ignore_changes_end_time:
                return
            else:
                self.ignore_changes = False

        # Have we been asked to set the CFS bit?
        if self.set_cfs:
            self.nvme_regs.CSTS.CFS = 1
            self.set_cfs = False

        # Did we just transition from not enabled to enabled?
        if (self.last_nvme_regs.CC.EN == 0 and nvme_regs.CC.EN == 1):
            logger.info('CC.EN 0 -> 1')

            # Log Admin queues addresses and sizes
            logger.debug('ASQS   {}'.format(nvme_regs.AQA.ASQS))
            logger.debug('ASQB 0x{:08x}'.format(nvme_regs.ASQ.ASQB))
            logger.debug('ACQS   {}'.format(nvme_regs.AQA.ACQS))
            logger.debug('ACQB 0x{:08x}'.format(nvme_regs.ACQ.ACQB))

            # Create and check queue memory address
            asq_mem = MemoryLocation(nvme_regs.ASQ.ASQB,
                                     nvme_regs.ASQ.ASQB,
                                     ((nvme_regs.AQA.ASQS + 1) *
                                         self.nvsim_state.nvme_device.sq_entry_size),
                                     'nvsim_asq')
            self.nvsim_state.check_mem_access(asq_mem)

            acq_mem = MemoryLocation(nvme_regs.ACQ.ACQB,
                                     nvme_regs.ACQ.ACQB,
                                     ((nvme_regs.AQA.ACQS + 1) *
                                         self.nvsim_state.nvme_device.cq_entry_size),
                                     'nvsim_acq')
            self.nvsim_state.check_mem_access(acq_mem)

            # Add ADMIN queue to nvsim_state
            self.nvsim_state.queue_mgr.add(
                NVMeSubmissionQueue(
                    asq_mem,
                    nvme_regs.AQA.ASQS + 1,
                    self.nvsim_state.nvme_device.sq_entry_size,
                    0,
                    ctypes.addressof(self.nvsim_state.nvme_regs.SQNDBS[0])),
                NVMeCompletionQueue(
                    acq_mem,
                    nvme_regs.AQA.ACQS + 1,
                    self.nvsim_state.nvme_device.cq_entry_size,
                    0,
                    ctypes.addressof(self.nvsim_state.nvme_regs.SQNDBS[0]) + 4))

            # Ok, looks like the addresses add up, setting ourselves to ready!
            self.nvsim_state.nvme_regs.CSTS.RDY = 1
            self.nvsim_state.ready = True
            logger.info('NVSim ready (CSTS.RDY = 1)')

        # Did we just transition from enabled to not enabled?
        if (self.last_nvme_regs.CC.EN == 1 and
                nvme_regs.CC.EN == 0):
            logger.info('CC.EN 1 -> 0')

            # Remove all queues from nvsim_state on disable
            self.queue_mgr = QueueMgr()

            self.nvsim_state.nvme_regs.CSTS.RDY = 0
            logger.info('NVSim no longer ready (CSTS.RDY = 0)')

        if self.nvsim_state.nvme_regs.CSTS.RDY == 1:

            # Find all the queues we should look at for commands
            busy_sqs = [(sq, cq) for k, (sq, cq) in
                        self.nvsim_state.queue_mgr.nvme_queues.items() if
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

                    # Were we asked to fail the next command we got?
                    if self.fail_next_command:
                        NvsimCommandHandler.complete(None,
                                                     command,
                                                     sq,
                                                     cq,
                                                     self.fail_next_command_sc)
                        self.fail_next_command = False
                    else:
                        # Pick either the ADMIN or NVM handler
                        if sq.qid == 0:
                            handler = admin_handlers.handlers[command.OPC]
                        else:
                            handler = nvm_handlers.handlers[command.OPC]

                        # Execute the command
                        handler(self.nvsim_state, command, sq, cq)

        # Save off the last time we checked
        self.last_nvme_regs = nvme_regs
