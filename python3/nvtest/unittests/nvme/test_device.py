import pytest

from lone.nvme.spec.registers.pcie_regs import PCIeRegistersDirect
from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect
from lone.nvme.spec.queues import NVMeSubmissionQueue, NVMeCompletionQueue
from lone.system import DevMemMgr, MemoryLocation

from lone.nvme.device import CidMgr
from lone.nvme.device import NVMeDeviceCommon, NVMeDeviceIntType


@pytest.fixture(scope='function')
def mocked_nvme_device(pytestconfig):
    pcie_regs = PCIeRegistersDirect()
    nvme_regs = NVMeRegistersDirect()

    class MockedMemMgr(DevMemMgr):
        def __init__(self, page_size):
            self.page_size = page_size
            self._allocated_mem_list = []
        def malloc(self, size, direction, client=None):
            m = MemoryLocation(0x1000, 0x2000, size, 'mocked_dev')
            self._allocated_mem_list.append(m)
            return m
        def free(self, memory):
            pass
        def free_all(self):
            pass
        def allocated_mem_list(self):
            return self._allocated_mem_list

    nvme_device = NVMeDeviceCommon('test_slot', None, pcie_regs, nvme_regs, MockedMemMgr(4096), 64, 16)

    yield nvme_device

    # Make sure that the disable when the nvme_device is deleted doesnt timeout
    nvme_device.nvme_regs.CSTS.RDY = 0


####################################################################################################
# CidMgr tests
####################################################################################################
def test_nvme_device_cid_mgr():
    cid_mgr = CidMgr(init_value=0, max_value=1000)
    assert cid_mgr.value == 0

    for i in range(1000):
        new_cid = cid_mgr.alloc()
        assert new_cid == i

    new_cid = cid_mgr.alloc()
    assert new_cid == 0


####################################################################################################
# NVMeDeviceCommon tests
####################################################################################################
def test_nvme_device_common_init():
    ''' def __init__(self,
                 pci_slot,
                 pci_userspace_device,
                 pcie_regs,
                 nvme_regs,
                 mem_mgr,
                 sq_entry_size=64,
                 cq_entry_size=16):
    '''
    nvme_device = NVMeDeviceCommon(None, None, None, None, None, None, None)

    # Check init values
    assert nvme_device.cid_mgr is not None
    assert nvme_device.queue_mgr is not None
    assert type(nvme_device.outstanding_commands) is dict
    assert len(nvme_device.outstanding_commands) == 0
    assert nvme_device.injectors is not None
    assert nvme_device.int_type == NVMeDeviceIntType.POLLING
    assert callable(nvme_device.get_completions)


def test_cc_disable(mocked_nvme_device):
    ''' def cc_disable(self, timeout_s=10):
    '''
    # Timeout path, includes more than one loop
    mocked_nvme_device.nvme_regs.CSTS.RDY = 1
    with pytest.raises(Exception):
        mocked_nvme_device.cc_disable(timeout_s=0.00001)
    assert mocked_nvme_device.nvme_regs.CSTS.RDY == 1
    assert mocked_nvme_device.nvme_regs.CC.EN == 0

    # CFS path
    mocked_nvme_device.nvme_regs.CSTS.RDY = 0
    mocked_nvme_device.nvme_regs.CSTS.CFS = 1
    mocked_nvme_device.cc_disable()
    assert mocked_nvme_device.nvme_regs.CSTS.RDY == 0
    assert mocked_nvme_device.nvme_regs.CC.EN == 0

    # Sucessful disable path
    mocked_nvme_device.nvme_regs.CSTS.RDY = 0
    mocked_nvme_device.nvme_regs.CSTS.CFS = 0
    mocked_nvme_device.cc_disable()
    assert mocked_nvme_device.nvme_regs.CSTS.RDY == 0
    assert mocked_nvme_device.nvme_regs.CC.EN == 0
    for sqdnbs in mocked_nvme_device.nvme_regs.SQNDBS:
        assert sqdnbs.SQTAIL == 0
        assert sqdnbs.CQHEAD == 0
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 0
    assert len(mocked_nvme_device.outstanding_commands) == 0


def test_cc_enable(mocked_nvme_device):
    ''' def cc_enable(self, timeout_s=10):
    '''
    # Timeout path, includes more than one loop
    mocked_nvme_device.nvme_regs.CSTS.RDY = 0
    with pytest.raises(Exception):
        mocked_nvme_device.cc_enable(timeout_s=0.00001)
    assert mocked_nvme_device.nvme_regs.CC.EN == 1

    # Sucessful enable path
    mocked_nvme_device.nvme_regs.CSTS.RDY = 1
    mocked_nvme_device.cc_enable()
    assert mocked_nvme_device.nvme_regs.CC.EN == 1

def test_init_admin_queues(mocked_nvme_device):
    ''' def init_admin_queues(self, asq_entries, acq_entries):
    '''
    # Sucess path, does not set CC.CSS
    mocked_nvme_device.nvme_regs.CAP.CSS = 0x00
    mocked_nvme_device.init_admin_queues(2, 2)
    assert mocked_nvme_device.nvme_regs.CC.EN == 0
    assert mocked_nvme_device.nvme_regs.CC.CSS == 0

    # Sucess path, sets CC.CSS
    mocked_nvme_device.nvme_regs.CAP.CSS = 0x40
    mocked_nvme_device.init_admin_queues(2, 2)

    # Check register values after init_admin_queues
    assert mocked_nvme_device.nvme_regs.CC.EN == 0

    # Check AQA/ASQ/AQA/ACQ
    assert mocked_nvme_device.nvme_regs.AQA.ASQS == 1
    assert mocked_nvme_device.nvme_regs.ASQ.ASQB == 0x2000
    assert mocked_nvme_device.nvme_regs.AQA.ACQS == 1
    assert mocked_nvme_device.nvme_regs.ACQ.ACQB == 0x2000

    # Check CC
    assert mocked_nvme_device.nvme_regs.CC.IOSQES == 6
    assert mocked_nvme_device.nvme_regs.CC.IOCQES == 4
    assert mocked_nvme_device.nvme_regs.CC.CSS == 0x06

    # Check BME is back on
    assert mocked_nvme_device.pcie_regs.CMD.BME == 1

    # Check the right number of queues was added
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 1
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 0
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 0
    asq, acq = mocked_nvme_device.queue_mgr.nvme_queues[(0,0)]
    assert type(asq) == NVMeSubmissionQueue
    assert asq.qid == 0
    assert type(acq) == NVMeCompletionQueue
    assert acq.qid == 0

def test_create_io_queue_pair(mocked_nvme_device):
    ''' def create_io_queue_pair(self,
                                 cq_entries, cq_id, cq_iv, cq_ien, cq_pc,
                                 sq_entries, sq_id, sq_prio, sq_pc, sq_setid):
    '''
    # Must create admin queues before creating io queues
    mocked_nvme_device.init_admin_queues(2, 2)
    # This will segfault... Fix next!
    #mocked_nvme_device.create_io_queue_pair(
        #1, 1, 0, 0, 1,
        #1, 1, 0, 1, 0)


def test_create_io_queues():
    ''' def create_io_queues(self, num_queues=10, queue_entries=256, sq_nvme_set_id=0):
    '''
    pass


def test_delete_io_queues():
    ''' def delete_io_queues(self):
    '''
    pass


def test_post_command():
    ''' def post_command(self, command):
    '''
    pass


def test_poll_cq_completions():
    ''' def poll_cq_completions(self, cqids=None, max_completions=1, max_time_s=0):
    '''
    pass


def test_get_completion():
    ''' def get_completion(self, cqid):
    '''
    pass


def test_get_msix_completions():
    ''' def get_msix_completions(self, cqids=None, max_completions=1, max_time_s=0):
    '''
    pass


def test_complete_command():
    ''' def complete_command(self, command, cqe):
    '''
    pass


def test_process_completions():
    ''' def process_completions(self, cqids=None, max_completions=1, max_time_s=0):
    '''
    pass


def test_sync_cmd():
    ''' def sync_cmd(self, command, sqid=None, cqid=None, timeout_s=10, check=True):
    '''
    pass


def test_start_cmd():
    ''' def start_cmd(self, command, sqid=None, cqid=None):
    '''
    pass


def test_alloc():
    ''' def alloc(self, command, bytes_per_block=None):
    '''
    pass


def test_delete():
    ''' def __del__(self):
    '''
    pass


####################################################################################################
# NVMeDevice tests
####################################################################################################
def test_nvme_device():
    pass


####################################################################################################
# NVMeDevicePhysical tests
####################################################################################################
def test_nvme_device_physical_init():
    ''' def __init__(self, pci_slot):
    '''
    pass


def test_init_msix_interrupts():
    ''' def init_msix_interrupts(self, num_vectors, start=0):
    '''
    pass


def test_get_msix_vector_pending_count():
    ''' def get_msix_vector_pending_count(self, vector):
    '''
    pass


####################################################################################################
# NVMeDeviceIdentifyData tests
####################################################################################################
def test_nvme_identify_data_init():
    ''' def __init__(self, nvme_device):
    '''
    pass


def test_ns_size():
    ''' def ns_size(self, lba_ds_bytes, nsze, nuse):
    '''
    pass


def test_lba_ds_size():
    ''' def lba_ds_size(self, lba_ds_bytes):
    '''
    pass


def test_identify_namespaces():
    ''' def identify_namespaces(self):
    '''
    pass


def test_identify_uuid_list():
    ''' def identify_uuid_list(self):
    '''
    pass


def test_identify_controller():
    ''' def identify_controller(self):
    '''
    pass
