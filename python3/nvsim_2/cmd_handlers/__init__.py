import abc
import traceback
import ctypes

from lone.nvme.spec.structures import CQE
from lone.nvme.spec.commands.status_codes import status_codes

from lone.util.logging import log_init
logger = log_init()


class NVSimCmdHandlerInterface(metaclass=abc.ABCMeta):

    @staticmethod
    @abc.abstractmethod
    def __call__(nvsim, command, sq, cq, cmd_spec_value=0):
        raise NotImplementedError('not implemented')

    @staticmethod
    def complete(cid, sq, cq, status_code, cmd_spec_value=0):

        # Create completion queue entry, fill it in, and post it
        cqe = CQE()
        cqe.CID = cid
        cqe.SF.SC = int(status_code)
        cqe.SQID = sq.qid
        cqe.SQHD = sq.head.value
        cqe.CMD_SPEC = 0
        cq.post_completion(cqe)


class NVSimCommandNotSupported(NVSimCmdHandlerInterface):

    @staticmethod
    def __call__(nvsim, command, sq, cq, cmd_spec_value=0):
        logger.error(f'Command OPC 0x{command.OPC:x} not supported')
        status_code = status_codes['Invalid Field in Command']
        NVSimCmdHandlerInterface.complete(command.CID, sq, cq, status_code, cmd_spec_value)
