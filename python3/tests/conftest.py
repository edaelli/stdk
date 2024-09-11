import pytest
import ctypes
from types import SimpleNamespace

from lone.nvme.spec.registers.pcie_regs import PCIeRegistersDirect
from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect
from lone.nvme.spec.structures import ADMINCommand, DataInCommon
from lone.system import DevMemMgr, MemoryLocation
from lone.nvme.device import NVMeDeviceCommon


####################################################################################################
# pytest fixture for mocking an nvme device to be used in unittests
####################################################################################################
@pytest.fixture(scope='function')
def mocked_nvme_device(mocker):
    pcie_regs = PCIeRegistersDirect()
    nvme_regs = NVMeRegistersDirect()

    class MockedMemMgr(DevMemMgr):
        def __init__(self, page_size):
            self.page_size = page_size
            self._allocated_mem_list = []

        def malloc(self, size, direction, client=None):
            memory = (ctypes.c_uint8 * size)()
            m = MemoryLocation(ctypes.addressof(memory),
                               ctypes.addressof(memory),
                               size,
                               'mocked_dev')
            self._allocated_mem_list.append(m)
            return m

        def free(self, memory):
            pass

        def free_all(self):
            pass

        def allocated_mem_list(self):
            return self._allocated_mem_list

    nvme_device = NVMeDeviceCommon('test_slot', None,
                                   pcie_regs, nvme_regs,
                                   MockedMemMgr(4096), 64, 16)

    # Mock sync_cmd
    def mocked_sync_cmd(command, sqid=None, cqid=None, timeout_s=10, check=True):
        return

    mocker.patch.object(nvme_device, 'sync_cmd', mocked_sync_cmd)

    yield nvme_device

    # Make sure that the disable when the nvme_device is deleted doesnt timeout
    nvme_device.nvme_regs.CSTS.RDY = 0


####################################################################################################
# pytest fixture for mocking an admin command that can be used in unittests
####################################################################################################
@pytest.fixture(scope='function')
def mocked_admin_cmd(mocker):
    admin_cmd = ADMINCommand()
    admin_cmd.sq = SimpleNamespace(post_command=lambda x: True,
                                   qid=0,
                                   head=SimpleNamespace(set=lambda x: None))
    admin_cmd.cq = SimpleNamespace(consume_completion=lambda: None,
                                   qid=0)
    admin_cmd.data_in = DataInCommon()
    admin_cmd.data_in_type = DataInCommon
    yield admin_cmd
