import abc
import traceback
import ctypes

from lone.nvme.spec.structures import CQE
from lone.nvme.spec.commands.status_codes import status_codes

from lone.util.logging import log_init
logger = log_init()


class NVSimInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def nvsim_exception_handler(self, exception):
        raise NotImplementedError('not implemented')

    @abc.abstractmethod
    def nvsim_pcie_handler(self):
        raise NotImplementedError('not implemented')

    @abc.abstractmethod
    def nvsim_pcie_regs_changed(self, old_pcie_regs, new_pcie_regs):
        raise NotImplementedError('not implemented')

    @abc.abstractmethod
    def nvsim_nvme_handler(self):
        raise NotImplementedError('not implemented')

    @abc.abstractmethod
    def nvsim_nvme_regs_changed(self, old_nvme_regs, new_nvme_regs):
        raise NotImplementedError('not implemented')


class NVSimCmdHandlerInterface(metaclass=abc.ABCMeta):

    @staticmethod
    @abc.abstractmethod
    def __call__(nvsim, command, sq, cq, cmd_spec_value=0):
        raise NotImplementedError('not implemented')

    @staticmethod
    def complete(cid, sq, cq, status_code, cmd_spec_value):

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
