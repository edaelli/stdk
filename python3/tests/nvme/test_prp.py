import pytest
import ctypes

from lone.nvme.spec.prp import PRP
from lone.system import DMADirection


####################################################################################################
# PRP tests
####################################################################################################
def test_init(mocker, mocked_nvme_device):
    ''' def __init__(self, mem_mgr, num_bytes, mps, direction, client, alloc=True):
    '''
    # Test both alloc=True and alloc=False paths
    prp = PRP(mocked_nvme_device.mem_mgr,
              4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)

    mocker.patch('lone.nvme.spec.prp.PRP.alloc')
    prp = PRP(mocked_nvme_device.mem_mgr,
              4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=True)
    assert prp is not None


def test_malloc_page(mocked_nvme_device):
    ''' def malloc_page(self, direction, client):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    mem = prp.malloc_page(DMADirection.HOST_TO_DEVICE, 'test')
    assert mem.vaddr != 0
    assert mem.iova != 0


def test_alloc(mocked_nvme_device):
    ''' def alloc(self, data_dma_direction):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 1
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    prp.alloc()
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == before + 1

    prp = PRP(mocked_nvme_device.mem_mgr,
              2 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 2
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    prp.alloc()
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == before + 2

    prp = PRP(mocked_nvme_device.mem_mgr,
              3 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 4
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    prp.alloc()
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == before + 4

    prp = PRP(mocked_nvme_device.mem_mgr,
              4 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 5
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    prp.alloc()
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == before + 5

    prp = PRP(mocked_nvme_device.mem_mgr,
              16 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 17
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    prp.alloc()
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == before + 17

    prp = PRP(mocked_nvme_device.mem_mgr,
              2 * 1024 * 1024,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 513
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    prp.alloc()
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == before + 513

    prp = PRP(mocked_nvme_device.mem_mgr,
              (2 * 1024 * 1024) + 1,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.pages_needed == 515
    before = len(mocked_nvme_device.mem_mgr.allocated_mem_list())
    with pytest.raises(AssertionError):
        prp.alloc()


def test_from_address(mocked_nvme_device):
    ''' def from_address(self, prp1_address, prp2_address=0):
    '''
    memory_1 = (ctypes.c_uint8 * 4096)()
    memory_2 = (ctypes.c_uint8 * 4096)()

    prp = PRP(mocked_nvme_device.mem_mgr,
              4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.prp1 == 0
    assert prp.prp1_mem is None
    assert prp.prp2 == 0
    assert prp.prp2_mem is None
    new_prp = prp.from_address(ctypes.addressof(memory_1))
    assert new_prp.prp1 == ctypes.addressof(memory_1)
    assert new_prp.prp1_mem is not None
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 0

    prp = PRP(mocked_nvme_device.mem_mgr,
              2 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.prp1 == 0
    assert prp.prp1_mem is None
    assert prp.prp2 == 0
    assert prp.prp2_mem is None
    new_prp = prp.from_address(ctypes.addressof(memory_1), ctypes.addressof(memory_2))
    assert new_prp.prp1 == ctypes.addressof(memory_1)
    assert new_prp.prp1_mem is not None
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 0

    prp = PRP(mocked_nvme_device.mem_mgr,
              10 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=False)
    assert prp.prp1 == 0
    assert prp.prp1_mem is None
    assert prp.prp2 == 0
    assert prp.prp2_mem is None
    new_prp = prp.from_address(ctypes.addressof(memory_1), ctypes.addressof(memory_2))
    assert new_prp.prp1 == ctypes.addressof(memory_1)
    assert new_prp.prp1_mem is not None
    assert len(mocked_nvme_device.mem_mgr.allocated_mem_list()) == 0


def test_str(mocked_nvme_device):
    ''' def __str__(self):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              16 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=True)

    # Test string conversion
    str(prp)

    # Test string conversion with empty list (mps = 0 gets us down that path)
    prp.mps = 0
    str(prp)

    # Test string conversion with no memory
    prp.mem_list = []
    str(prp)


def test_free_all_memory(mocked_nvme_device):
    ''' def free_all_memory(self):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=True)

    prp.free_all_memory()
    assert len(prp.mem_list) == 0


def test_get_data_segments(mocked_nvme_device):
    ''' def get_data_segments(self):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              10 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=True)

    segments = prp.get_data_segments()
    assert len(segments) == 10


def test_get_data_buffer(mocked_nvme_device):
    ''' def get_data_buffer(self):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              10 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=True)
    assert len(prp.get_data_buffer()) == 10 * 4096


def test_set_data_buffer(mocked_nvme_device):
    ''' def set_data_buffer(self, data):
    '''
    prp = PRP(mocked_nvme_device.mem_mgr,
              10 * 4096,
              4096,
              DMADirection.HOST_TO_DEVICE,
              'test',
              alloc=True)

    prp.set_data_buffer(bytearray(10 * 4096))

    prp.set_data_buffer(bytearray(9 * 4096))
