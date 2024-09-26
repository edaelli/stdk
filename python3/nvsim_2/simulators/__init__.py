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
