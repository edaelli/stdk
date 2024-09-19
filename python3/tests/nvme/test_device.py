import pytest
from types import SimpleNamespace

from lone.system import System
from lone.nvme.spec.queues import NVMeSubmissionQueue, NVMeCompletionQueue
from lone.nvme.device import CidMgr
from lone.nvme.device import NVMeDevice, NVMeDeviceCommon, NVMeDeviceIntType, NVMeDevicePhysical
from lone.nvme.device.identify import NVMeDeviceIdentifyData
from lone.nvme.spec.commands.admin.identify import (IdentifyNamespaceListData,
                                                    IdentifyNamespaceData)
from lone.nvme.spec.commands.status_codes import NVMeStatusCodeException

from nvsim import NVMeSimulator


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


def test_initate_flr(mocker, mocked_nvme_device):
    ''' def initiate_flr(self):
    '''
    mocked_nvme_device.initiate_flr()


def test_cc_disable(mocker, mocked_nvme_device):
    ''' def cc_disable(self, timeout_s=10):
    '''
    # Mock time.sleep for these tests
    mocker.patch('time.sleep', None)

    # Timeout path, includes more than one loop
    mocked_nvme_device.nvme_regs.CSTS.RDY = 1
    with pytest.raises(Exception):
        mocked_nvme_device.cc_disable(timeout_s=0)
    with pytest.raises(Exception):
        mocked_nvme_device.cc_disable(timeout_s=1)
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


def test_cc_enable(mocker, mocked_nvme_device):
    ''' def cc_enable(self, timeout_s=10):
    '''
    # Mock time.sleep for these tests
    mocker.patch('time.sleep', None)

    # Timeout path, includes more than one loop
    mocked_nvme_device.nvme_regs.CSTS.RDY = 0
    with pytest.raises(Exception):
        mocked_nvme_device.cc_enable(timeout_s=0)
    with pytest.raises(Exception):
        mocked_nvme_device.cc_enable(timeout_s=1)
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
    assert mocked_nvme_device.nvme_regs.ASQ.ASQB != 0
    assert mocked_nvme_device.nvme_regs.AQA.ACQS == 1
    assert mocked_nvme_device.nvme_regs.ACQ.ACQB != 0

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
    asq, acq = mocked_nvme_device.queue_mgr.nvme_queues[(0, 0)]
    assert type(asq) is NVMeSubmissionQueue
    assert asq.qid == 0
    assert type(acq) is NVMeCompletionQueue
    assert acq.qid == 0


def test_create_io_queue_pair(mocker, mocked_nvme_device):
    ''' def create_io_queue_pair(self,
                                 cq_entries, cq_id, cq_iv, cq_ien, cq_pc,
                                 sq_entries, sq_id, sq_prio, sq_pc, sq_setid):
    '''
    # Must create admin queues before creating io queues, verify one queue (admin) is created
    mocked_nvme_device.init_admin_queues(2, 2)
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 1
    # Make sure that we allocated 2 memory regions for each the sq and cq
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 2

    # Call it with parameters
    mocked_nvme_device.create_io_queue_pair(1, 1, 0, 0, 1,
                                            1, 1, 0, 1, 0)

    # After calling, one more queue should be created, and we should have 1 cq and 1 sq
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 2
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 1
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 1
    # Make sure that we allocated 2 more memory regions for each the sq and cq
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 4

    # Call it with parameters again to verify
    mocked_nvme_device.create_io_queue_pair(1, 2, 0, 0, 1,
                                            1, 2, 0, 1, 0)

    # After calling, one more queue should be created, and we should have 1 cq and 1 sq
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 3
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 2
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 2
    # Make sure that we allocated 2 more memory regions for each the sq and cq
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 6

    # Test the MSI-X path
    mocked_nvme_device.int_type = NVMeDeviceIntType.MSIX
    mocked_nvme_device.num_msix_vectors = 10
    mocked_nvme_device.create_io_queue_pair(1, 3, 0, 0, 1,
                                            1, 3, 0, 1, 0)
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 4
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 3
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 3
    # Make sure that we allocated 2 more memory regions for each the sq and cq
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 8

    # Test the MSI-X path with vector too high
    mocked_nvme_device.int_type = NVMeDeviceIntType.MSIX
    mocked_nvme_device.num_msix_vectors = 1
    with pytest.raises(Exception):
        mocked_nvme_device.create_io_queue_pair(1, 4, 2, 0, 1,
                                                1, 4, 2, 1, 0)
    # Make sure nothing new was created
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 4
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 3
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 3


def test_create_io_queues(mocked_nvme_device):
    ''' def create_io_queues(self, num_queues=10, queue_entries=256, sq_nvme_set_id=0):
    '''
    mocked_nvme_device.init_admin_queues(2, 2)
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 1
    # Make sure that we allocated 2 memory regions for each the sq and cq
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 2

    # Create queues, make sure they are all there
    mocked_nvme_device.create_io_queues(10, 256, 0)
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 11
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 10
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 10
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 22


def test_delete_io_queues(mocked_nvme_device):
    ''' def delete_io_queues(self):
    '''
    # First try calling it without any queues to see how it works
    mocked_nvme_device.delete_io_queues()
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 0
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 0
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 0
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 0

    # Now create some queues, delete them and check
    mocked_nvme_device.init_admin_queues(2, 2)
    mocked_nvme_device.create_io_queues(10, 256, 0)
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 11
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 10
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 10
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 22

    mocked_nvme_device.delete_io_queues()
    assert len(mocked_nvme_device.queue_mgr.nvme_queues) == 1  # admin remains
    assert len(mocked_nvme_device.queue_mgr.io_sqids) == 0
    assert len(mocked_nvme_device.queue_mgr.io_cqids) == 0


def test_post_command(mocked_nvme_device, mocked_admin_cmd):
    ''' def post_command(self, command):
    '''
    mocked_nvme_device.post_command(mocked_admin_cmd)
    assert len(mocked_nvme_device.outstanding_commands) == 1
    assert mocked_admin_cmd.start_time_ns != 0


def test_poll_cq_completions(mocker, mocked_nvme_device):
    ''' def poll_cq_completions(self, cqids=None, max_completions=1, max_time_s=0):
    '''
    # First test without providing a queue
    assert mocked_nvme_device.poll_cq_completions() == 0

    # Create admin queue for testing
    mocked_nvme_device.init_admin_queues(2, 2)

    # Then providing a queue, admin in this case
    mocked_nvme_device.get_completion = lambda x: True
    assert mocked_nvme_device.poll_cq_completions(cqids=0) == 1

    mocked_nvme_device.get_completion = lambda x: False
    assert mocked_nvme_device.poll_cq_completions(cqids=0) == 0

    # Then a list of queues
    mocked_nvme_device.get_completion = lambda x: True
    assert mocked_nvme_device.poll_cq_completions(cqids=[0]) == 1

    mocked_nvme_device.get_completion = lambda x: False
    assert mocked_nvme_device.poll_cq_completions(cqids=[0]) == 0

    # Timeout
    mocked_nvme_device.get_completion = lambda x: False
    assert mocked_nvme_device.poll_cq_completions(max_time_s=0.0001) == 0


def test_get_completion(mocker, mocked_nvme_device, mocked_admin_cmd):
    ''' def get_completion(self, cqid):

    '''
    # Test with admin queue
    mocked_nvme_device.init_admin_queues(10, 10)
    sq, cq = mocked_nvme_device.queue_mgr.get(0, 0)

    # Mock a completion and set outstanding commands, P = 0
    mocker.patch.object(cq, 'get_next_completion', lambda: SimpleNamespace(SF=SimpleNamespace(P=0),
                                                                           CID=1,
                                                                           SQID=0))
    assert mocked_nvme_device.get_completion(0) is False

    # Mock a completion and set outstanding commands, P = 1
    mocker.patch.object(cq, 'get_next_completion', lambda: SimpleNamespace(SF=SimpleNamespace(P=1),
                                                                           CID=1,
                                                                           SQID=0))
    mocked_nvme_device.outstanding_commands = {}
    mocked_admin_cmd.posted = True
    mocked_admin_cmd.CID = 1
    mocked_admin_cmd.SQID = 0
    mocked_nvme_device.complete_command = lambda cmd, cqe: None
    mocked_nvme_device.outstanding_commands[(1, 0)] = mocked_admin_cmd
    assert mocked_nvme_device.get_completion(0) is True

    # Now with IO queues
    mocked_nvme_device.create_io_queues(1, 256, 0)
    mocker.patch.object(cq, 'get_next_completion', lambda: SimpleNamespace(SF=SimpleNamespace(P=0),
                                                                           CID=1,
                                                                           SQID=1))
    mocked_nvme_device.outstanding_commands = {}
    mocked_nvme_device.outstanding_commands[(1, 1)] = None
    mocked_nvme_device.get_completion(1)
    assert mocked_nvme_device.get_completion(0) is False


def test_get_msix_completions(mocker, mocked_nvme_device):
    ''' def get_msix_completions(self, cqids=None, max_completions=1, max_time_s=0):
    '''
    mocked_nvme_device.init_admin_queues(10, 10)
    mocked_nvme_device.get_msix_vector_pending_count = lambda x: 0
    mocked_nvme_device.get_completion = lambda x: 0

    assert mocked_nvme_device.get_msix_completions() == 0
    assert mocked_nvme_device.get_msix_completions(0) == 0
    assert mocked_nvme_device.get_msix_completions(1) == 0

    with pytest.raises(Exception):
        mocked_nvme_device.get_msix_completions('invalid type')

    # Test max time path
    assert mocked_nvme_device.get_msix_completions(0, max_time_s=0.0001) == 0

    # Test actually receiving completions path!
    mocker.patch.object(mocked_nvme_device, 'get_msix_vector_pending_count', return_value=1)
    mocker.patch.object(mocked_nvme_device, 'get_completion', side_effect=[True, True, True, False])
    assert mocked_nvme_device.get_msix_completions(0, max_completions=3, max_time_s=1) == 3


def test_complete_command(mocked_nvme_device, mocked_admin_cmd):
    ''' def complete_command(self, command, cqe):
    '''
    mocked_admin_cmd.prp = SimpleNamespace(
        get_data_buffer=lambda: bytearray(len(mocked_admin_cmd.data_in)))
    mocked_nvme_device.outstanding_commands[(0, 0)] = mocked_admin_cmd
    mocked_admin_cmd.posted = True
    mocked_nvme_device.complete_command(mocked_admin_cmd, mocked_admin_cmd.cqe)
    assert mocked_admin_cmd.posted is False
    assert len(mocked_nvme_device.outstanding_commands) == 0

    # Pretend it didnt have data in
    mocked_nvme_device.outstanding_commands[(0, 0)] = mocked_admin_cmd
    mocked_admin_cmd.posted = True
    mocked_admin_cmd.data_in = None
    mocked_nvme_device.complete_command(mocked_admin_cmd, mocked_admin_cmd.cqe)
    assert mocked_admin_cmd.posted is False
    assert len(mocked_nvme_device.outstanding_commands) == 0


def test_process_completions(mocked_nvme_device):
    ''' def process_completions(self, cqids=None, max_completions=1, max_time_s=0):
    '''
    mocked_nvme_device.get_completions = lambda x, y, z: 0
    assert mocked_nvme_device.process_completions() == 0


def test_sync_cmd(mocker, mocked_nvme_device, mocked_admin_cmd):
    ''' def sync_cmd(self, command, sqid=None, cqid=None, timeout_s=10, check=True):
    '''
    # Mocked device mocks sync_cmd, so access it directly here
    sync_cmd = type(mocked_nvme_device).sync_cmd
    mocked_nvme_device.start_cmd = lambda x, y, z: None
    mocked_nvme_device.get_completions = lambda x, y, z: None
    mocked_nvme_device.start_cmd = lambda x, y, z: None

    mocked_admin_cmd.complete = False
    with pytest.raises(Exception):
        sync_cmd(mocked_nvme_device, mocked_admin_cmd)

    mocked_admin_cmd.complete = True
    sync_cmd(mocked_nvme_device, mocked_admin_cmd)

    mocked_admin_cmd.complete = True
    sync_cmd(mocked_nvme_device, mocked_admin_cmd, check=False)


def test_start_cmd(mocked_nvme_device, mocked_admin_cmd):
    ''' def start_cmd(self, command, sqid=None, cqid=None):
    '''
    mocked_nvme_device.init_admin_queues(10, 10)
    mocked_nvme_device.queue_mgr.next_iosq_id = lambda: 1
    mocked_nvme_device.queue_mgr.get = lambda x, y: (SimpleNamespace(qid=0),
                                                     SimpleNamespace(qid=0))
    mocked_nvme_device.post_command = lambda x: None

    # Make sure the queues match at the end of the test: (0, 0)
    mocked_admin_cmd.posted = False
    assert mocked_nvme_device.start_cmd(mocked_admin_cmd) == (0, 0)

    # Make sure the queues match at the end of the test: (0, 0)
    mocked_admin_cmd.posted = False
    assert mocked_nvme_device.start_cmd(mocked_admin_cmd, sqid=0) == (0, 0)

    # Make sure the queues match at the end of the test: (1, 1)
    mocked_admin_cmd.posted = False
    mocked_admin_cmd.cmdset_admin = 0
    mocked_nvme_device.queue_mgr.get = lambda x, y: (SimpleNamespace(qid=1),
                                                     SimpleNamespace(qid=1))
    assert mocked_nvme_device.start_cmd(mocked_admin_cmd) == (1, 1)


def test_alloc(mocked_nvme_device, mocked_admin_cmd, mocked_nvm_cmd):
    ''' def alloc(self, command, bytes_per_block=None):
    '''
    mocked_nvme_device.alloc(mocked_admin_cmd)
    assert mocked_admin_cmd.prp is not None
    assert mocked_admin_cmd.prp.num_bytes == len(mocked_admin_cmd.data_in)

    mocked_nvme_device.alloc(mocked_nvm_cmd)
    assert mocked_nvm_cmd.prp.num_bytes == len(mocked_nvm_cmd.data_in)

    # Test allocating a write command
    mocked_nvm_cmd.__class__.__name__ = 'Write'
    mocked_nvm_cmd.NLB = 0
    mocked_nvme_device.alloc(mocked_nvm_cmd, bytes_per_block=4096)
    assert mocked_nvm_cmd.prp.num_bytes == 4096

    # Test allocating a read command
    mocked_nvm_cmd.__class__.__name__ = 'Read'
    mocked_nvm_cmd.NLB = 0
    mocked_nvme_device.alloc(mocked_nvm_cmd, bytes_per_block=4096)
    assert mocked_nvm_cmd.prp.num_bytes == 4096

    mocked_nvm_cmd.__class__.__name__ = 'NotReadWrite'
    mocked_nvm_cmd.data_in_type = None
    mocked_nvm_cmd.data_out_type = None
    with pytest.raises(AssertionError):
        mocked_nvme_device.alloc(mocked_nvm_cmd)


def test_delete(mocked_nvme_device):
    ''' def __del__(self):
    '''
    mocked_nvme_device.__del__()


####################################################################################################
# NVMeDevice tests
####################################################################################################
def test_nvme_device(mocker):
    # Test that we get the right type of device when using nvsim and a real pcie device
    assert type(NVMeDevice('nvsim')) is NVMeSimulator

    mocker.patch('lone.nvme.device.NVMeDevicePhysical.__init__', lambda x, y: None)
    assert type(NVMeDevice('test_slot')) is NVMeDevicePhysical


####################################################################################################
# NVMeDevicePhysical tests
####################################################################################################
def test_nvme_device_physical(mocker):
    ''' def __init__(self, pci_slot):
    '''
    class MockedDevMemMgr:
        def __init__(self, a, b, c, d, e):
            pass
    System.DevMemMgr = MockedDevMemMgr

    class MockedUserspaceDevice:
        def __init__(self, pci_slot):
            pass

        def pci_regs(self):
            return SimpleNamespace(init_capabilities=lambda: None)

        def nvme_regs(self):
            return SimpleNamespace(CC=SimpleNamespace(MPS=0))

        def map_dma_region_read(self):
            pass

        def map_dma_region_write(self):
            pass

        def unmap_dma_region(self):
            pass

        def enable_msix(self, num_vectors, start):
            pass

        def get_msix_vector_pending_count(self, vector):
            return 0

        iova_ranges = []
    System.PciUserspaceDevice = MockedUserspaceDevice

    # Test mocked physical device
    nvme_dev = NVMeDevicePhysical('slot')
    assert nvme_dev.mps == 4096

    # init_msix_interrupts(self, num_vectors, start=0)
    nvme_dev.init_msix_interrupts(10, 0)

    # get_msix_vector_pending_count(self, vector)
    assert nvme_dev.get_msix_vector_pending_count(0) == 0

    def init_except(self, pcie_slot):
        raise Exception('testing exception')

    System.PciUserspaceDevice.__init__ = init_except
    with pytest.raises(Exception):
        nvme_dev = NVMeDevicePhysical('slot')


####################################################################################################
# NVMeDeviceIdentifyData tests
####################################################################################################
def test_nvme_identify_data_init(mocked_nvme_device):
    ''' def __init__(self, nvme_device):
    '''
    NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)


def test_nvme_identify_data_initialize(mocker, mocked_nvme_device):
    ''' def initialize(self):
    '''
    # First test without init, then mock and test with init
    NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)

    mocker.patch.object(NVMeDeviceIdentifyData, 'identify_controller', lambda x: None)
    mocker.patch.object(NVMeDeviceIdentifyData, 'identify_namespaces', lambda x: (None, None))
    mocker.patch.object(NVMeDeviceIdentifyData, 'identify_uuid_list', lambda x: None)
    NVMeDeviceIdentifyData(mocked_nvme_device, initialize=True)


def test_ns_size(mocked_nvme_device):
    ''' def ns_size(self, lba_ds_bytes, nsze, nuse):
    '''
    id_data = NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)

    usage, total, unit = id_data.ns_size(0, 0, 0)
    assert unit == 'B'

    usage, total, unit = id_data.ns_size(1024**1, 1, 1)
    assert unit == 'KB'

    usage, total, unit = id_data.ns_size(1024**2, 1, 1)
    assert unit == 'MB'

    usage, total, unit = id_data.ns_size(1024**3, 1, 1)
    assert unit == 'GB'

    usage, total, unit = id_data.ns_size(1024**4, 1, 1)
    assert unit == 'TB'


def test_lba_ds_size(mocked_nvme_device):
    ''' def lba_ds_size(self, lba_ds_bytes):
    '''
    id_data = NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)

    size, unit = id_data.lba_ds_size(512)
    assert unit == 'B'

    size, unit = id_data.lba_ds_size(4096)
    assert unit == 'KiB'


def test_identify_namespaces(mocker, mocked_nvme_device):
    ''' def identify_namespaces(self):
    '''
    class CmdSeq:
        def __init__(self):
            self.i = 0

        def __call__(self, command):
            # Send the correct sequence of data_in objects to test all paths
            if self.i == 0:
                data = IdentifyNamespaceListData()
                data.Identifiers[0] = 1

            elif self.i == 1:
                data = IdentifyNamespaceData()
                data.NSZE = 1
                data.NUSE = 1
                data.FLBAS = 0
                data.LBAF_TBL[0].LBADS = 1
                data.LBAF_TBL[0].MS = 0

            else:
                data = None

            command.data_in = data

            self.i += 1

    mocker.patch.object(mocked_nvme_device, 'sync_cmd', side_effect=CmdSeq())

    id_data = NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)

    # Test identify_namespaces with the IdentifyNamespaceListData above
    id_data.identify_namespaces()


def test_identify_uuid_list(mocker, mocked_nvme_device):
    ''' def identify_uuid_list(self):
    '''
    id_data = NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)
    id_data.identify_uuid_list()

    # With exception on sync_cmd
    mocker.patch.object(mocked_nvme_device, 'sync_cmd', side_effect=[
        NVMeStatusCodeException(SimpleNamespace(value=0,
                                                name='',
                                                cmd_type=SimpleNamespace(__name__='')))])
    id_data.identify_uuid_list()


def test_identify_controller(mocked_nvme_device):
    ''' def identify_controller(self):
    '''
    id_data = NVMeDeviceIdentifyData(mocked_nvme_device, initialize=False)
    id_data.identify_controller()
