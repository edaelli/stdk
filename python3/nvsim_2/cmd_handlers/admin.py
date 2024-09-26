import ctypes

from nvsim_2.cmd_handlers import NVSimCmdHandlerInterface

from lone.nvme.spec.prp import PRP
from lone.nvme.spec.commands.status_codes import status_codes
from lone.system import MemoryLocation
from lone.nvme.spec.queues import NVMeSubmissionQueue, NVMeCompletionQueue

from lone.nvme.spec.commands.admin.identify import (Identify,
                                                    IdentifyData,
                                                    IdentifyController,
                                                    IdentifyNamespace,
                                                    IdentifyNamespaceList,
                                                    IdentifyUUIDList)
from lone.nvme.spec.commands.admin.create_io_completion_q import CreateIOCompletionQueue
from lone.nvme.spec.commands.admin.create_io_submission_q import CreateIOSubmissionQueue
from lone.nvme.spec.commands.admin.delete_io_completion_q import DeleteIOCompletionQueue
from lone.nvme.spec.commands.admin.delete_io_submission_q import DeleteIOSubmissionQueue
from lone.nvme.spec.commands.admin.get_log_page import GetLogPage, GetLogPageSupportedLogPages
from lone.nvme.spec.commands.admin.format_nvm import FormatNVM
from lone.nvme.spec.commands.admin.get_set_feature import (GetFeature, SetFeature,
                                                           FeaturePowerManagement,
                                                           GetFeaturePowerManagement,
                                                           SetFeaturePowerManagement)

from lone.util.logging import log_init
logger = log_init()


class NVSimIdentify(NVSimCmdHandlerInterface):
    OPC = Identify().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):

        # Cast the command into a identify command
        id_cmd = Identify.from_buffer(command)
        logger.debug(f'NVMeAdminCommandHandler: NVSimIdentify CNS: 0x{id_cmd.CNS:x}')

        # Create the PRP at the location from the command
        prp = PRP(None, IdentifyData.size, nvsim.config.mps, None,
                  'sim identify', alloc=False).from_address(id_cmd.DPTR.PRP.PRP1)

        # Based on CNS, we have to simulate different structures for responses
        if id_cmd.CNS == IdentifyController().CNS:
            prp.set_data_buffer(bytearray(nvsim.config.id_ctrl_data))
            status_code = status_codes['Successful Completion']

        elif id_cmd.CNS == IdentifyNamespace().CNS:
            if id_cmd.NSID == 0 or id_cmd.NSID > len(nvsim.config.namespaces) - 1:
                status_code = status_codes['Invalid Namespace or Format']
            else:
                prp.set_data_buffer(bytearray(nvsim.config.id_ns_data[id_cmd.NSID]))
                status_code = status_codes['Successful Completion']

        elif id_cmd.CNS == IdentifyNamespaceList().CNS:
            prp.set_data_buffer(bytearray(nvsim.config.id_ns_list_data))
            status_code = status_codes['Successful Completion']

        elif id_cmd.CNS == IdentifyUUIDList().CNS:
            prp.set_data_buffer(bytearray(nvsim.config.id_uuid_list_data))
            status_code = status_codes['Successful Completion']

        else:
            # Return invalid field in command in SF.SC
            logger.info(f'Identify command with CNS: 0x{id_cmd.CNS:x} not supported')
            status_code = status_codes['Invalid Field in Command']

        # Complete the command
        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_code)


class NVSimCreateIOCompletionQueue(NVSimCmdHandlerInterface):
    OPC = CreateIOCompletionQueue().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):

        # Cast the command into a CreateIOCompletionQueue comma1d
        ccq_cmd = CreateIOCompletionQueue.from_buffer(command)

        if ccq_cmd.PC != 1:
            NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Invalid Field in Command'])
            return

        # Create the memory object for the queue location
        q_mem = MemoryLocation(ccq_cmd.DPTR.PRP.PRP1,
                               ccq_cmd.DPTR.PRP.PRP1,
                               (ccq_cmd.QSIZE + 1) * 16,
                               'nvsim_iocq')

        # Make sure we can access the queue memory before actually doing it
        nvsim.check_mem_access(q_mem)

        # Add IO queue to nvsim's queue mgr
        new_cq = NVMeCompletionQueue(q_mem,
                                     ccq_cmd.QSIZE + 1,
                                     16,
                                     ccq_cmd.QID,
                                     (ctypes.addressof(
                                         nvsim.nvme_regs.SQNDBS[0]) +
                                         ((ccq_cmd.QID * 8) + 4)))

        # Keep it in our state tracker until it can be used with a SQ
        nvsim.config.completion_queues.append(new_cq)
        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Successful Completion'])


class NVSimCreateIOSubmissionQueue(NVSimCmdHandlerInterface):
    OPC = CreateIOSubmissionQueue().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):

        # Cast the command into a CreateIOCompletionQueue command
        csq_cmd = CreateIOSubmissionQueue.from_buffer(command)

        # Create the memory object for the queue location
        q_mem = MemoryLocation(csq_cmd.DPTR.PRP.PRP1,
                               csq_cmd.DPTR.PRP.PRP1,
                               (csq_cmd.QSIZE + 1) * 64,
                               'nvsim_iosq')

        # Make sure we can access the queue memory before actually doing it
        nvsim.check_mem_access(q_mem)

        # Create the sq object
        new_sq = NVMeSubmissionQueue(q_mem,
                                     csq_cmd.QSIZE + 1,
                                     64,
                                     csq_cmd.QID,
                                     (ctypes.addressof(
                                         nvsim.nvme_regs.SQNDBS[0]) +
                                         ((csq_cmd.QID * 8))))
        # Find the associated CQ
        cqs = [c for c in nvsim.config.completion_queues if c.qid == csq_cmd.CQID]
        if len(cqs) == 0:
            NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Invalid Field in Command'])
            return

        # Add it to the list
        nvsim.config.queue_mgr.add(new_sq, cqs[0])
        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Successful Completion'])


class NVSimDeleteIOCompletionQueue(NVSimCmdHandlerInterface):
    OPC = DeleteIOCompletionQueue().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):

        del_iocq_cmd = DeleteIOCompletionQueue.from_buffer(command)
        del_cqid = del_iocq_cmd.QID

        # Cant delete the admin cq
        assert del_cqid != 0, "DeleteIOCompletionQueue command for qid = 0!"

        # Delete internal queue
        nvsim.config.queue_mgr.remove_cq(del_cqid)

        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Successful Completion'])


class NVSimDeleteIOSubmissionQueue(NVSimCmdHandlerInterface):
    OPC = DeleteIOSubmissionQueue().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):

        del_iosq_cmd = DeleteIOSubmissionQueue.from_buffer(command)
        del_sqid = del_iosq_cmd.QID

        # Cant delete the admin sq
        assert del_sqid != 0, "DeleteIOSubmissionQueue command for qid = 0!"

        # Delete internal queue
        nvsim.config.queue_mgr.remove_sq(del_sqid)

        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Successful Completion'])


class NVSimGetLogPage(NVSimCmdHandlerInterface):
    OPC = GetLogPage().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):
        glp_cmd = GetLogPage.from_buffer(command)

        # Whick log id are we servicing?
        if glp_cmd.LID == 0:

            # Get the Supported Log Pages command
            glp_cmd = GetLogPageSupportedLogPages.from_buffer(command)

            # Figure out how many bytes are we transferring
            num_bytes = (((glp_cmd.NUMDU << 16) | glp_cmd.NUMDL) + 1) * 4

            # Claim support for all pages, index offset supported
            data_out = glp_cmd.data_in_type()
            for lid in range(256):
                data_out.LIDS[lid].LSUPP = 1
                data_out.LIDS[lid].IOS = 1
            data_out = bytearray(data_out)

            # Offset
            offset = (glp_cmd.LPOU << 32) | (glp_cmd.LPOL & 0xFFFFFFFF)

            # Did the host ask for a byte offset or an index offset?
            if glp_cmd.OT == 0:
                # Offset in bytes
                data_out = data_out[offset:]
            else:
                # Offset in structure index
                logger.error('OT = 1 not yet implemented!')
                return NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Invalid Field in Command'])

            # Copy data to the host's PRP
            prp = PRP(None, num_bytes, nvsim.mps, None,
                      'sim glp', alloc=False).from_address(glp_cmd.DPTR.PRP.PRP1,
                                                           glp_cmd.DPTR.PRP.PRP2)
            prp.set_data_buffer(data_out)

            # Complete command
            NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Successful Completion'])

        else:
            NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Invalid Log Page', GetLogPage])


class NVSimFormat(NVSimCmdHandlerInterface):
    OPC = FormatNVM().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):
        fmt_cmd = FormatNVM.from_buffer(command)

        # Re-initialize our backend storage
        nvsim.namespaces[fmt_cmd.NSID].init_storage()

        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_codes['Successful Completion'])


class NVSimGetFeature(NVSimCmdHandlerInterface):
    OPC = GetFeature().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):
        gf_cmd = GetFeature.from_buffer(command)
        cmd_spec = 0

        # Check which feature we are doing
        if gf_cmd.FID == GetFeaturePowerManagement().FID:
            gf_cmd = GetFeaturePowerManagement.from_buffer(command)

            # Pretend PS = 1 until we implement state
            response = FeaturePowerManagement()
            response.PS = nvsim.config.power_state

            # Get response and status code
            cmd_spec = (ctypes.c_uint32).from_buffer(response)
            status_code = status_codes['Successful Completion']
        else:
            assert f'FID: 0x{gf_cmd.FID:x} not supported!'

        # Respond to the command
        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_code, cmd_spec)


class NVSimSetFeature(NVSimCmdHandlerInterface):
    OPC = SetFeature().OPC

    @staticmethod
    def __call__(nvsim, command, sq, cq):
        sf_cmd = SetFeature.from_buffer(command)

        if sf_cmd.FID == SetFeaturePowerManagement().FID:
            sf_cmd = SetFeaturePowerManagement.from_buffer(command)
            nvsim.config.power_state = sf_cmd.PS
            assert sf_cmd.SV == 0, 'SV set not yet supported'
            status_code = status_codes['Successful Completion']

        # Respond to the command
        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_code)
