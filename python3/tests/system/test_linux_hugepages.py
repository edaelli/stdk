import pytest
from types import SimpleNamespace


from lone.system.linux.hugepages_mgr import HugePagesMemoryMgr
from lone.system import DMADirection


@pytest.fixture(scope='function')
def mocked_hugepages(mocker):
    mocker.patch('hugepages.init', return_value=None)
    mocker.patch('hugepages.malloc', side_effect=range(0x1000, 0x10000000, 2 * 1024 * 1024))
    mocker.patch('hugepages.get_size', return_value=2 * 1024 * 1024)
    mocker.patch('hugepages.free', return_value=None)
    mocker.patch('ctypes.memset', return_value=None)


def test_hugepages_memory_mgr(mocked_hugepages):
    hp_mem_mgr = HugePagesMemoryMgr(4096,
                                    lambda x, y, z: None,
                                    lambda x, y, z: None,
                                    lambda x, y: None,
                                    [(0, 0xFFFFFFFF)])

    assert len(hp_mem_mgr.free_pages()) != 0
    assert hp_mem_mgr.allocated_mem_list() is not None

    # Test malloc
    mem = hp_mem_mgr.malloc(1, DMADirection.HOST_TO_DEVICE)
    assert mem.size == 4096

    mem = hp_mem_mgr.malloc(4096, DMADirection.HOST_TO_DEVICE)
    assert mem.size == 4096

    mem = hp_mem_mgr.malloc(10 * 4096, DMADirection.HOST_TO_DEVICE)
    assert mem.size == 40960

    # Make sure we malloc enogh to test needing more hugepages
    for i in range(10):
        mem = hp_mem_mgr.malloc(100 * 4096, DMADirection.DEVICE_TO_HOST)
        assert mem.size == 409600

    with pytest.raises(AssertionError):
        hp_mem_mgr.malloc(100 * 4096, DMADirection.BIDIRECTIONAL)


def test_hugepages_alloc(mocked_hugepages):
    hp_mem_mgr = HugePagesMemoryMgr(4096,
                                    lambda x, y, z: None,
                                    lambda x, y, z: None,
                                    lambda x, y: None,
                                    [(0, 0xFFFFFFFF)])

    def test(num):
        return None
    hp_mem_mgr._malloc_hps = test
    free_pages = []
    for page in range(10):
        free_pages.append(SimpleNamespace(vaddr=1000, size=4096, in_use=True))
    for page in range(10):
        free_pages.append(SimpleNamespace(vaddr=1000, size=4096, in_use=False))
    hp_mem_mgr.free_pages = lambda: free_pages
    with pytest.raises(MemoryError):
        hp_mem_mgr.malloc(10 * 4096, DMADirection.HOST_TO_DEVICE)

    # Test malloc_pages
    free_pages = []
    for page in range(10):
        free_pages.append(SimpleNamespace(vaddr=1000, size=4096, in_use=True))
    hp_mem_mgr.free_pages = lambda: free_pages
    hp_mem_mgr.malloc_pages(1)
    with pytest.raises(AssertionError):
        hp_mem_mgr.malloc_pages(11)


def test_hugepages_free(mocked_hugepages):
    hp_mem_mgr = HugePagesMemoryMgr(4096,
                                    lambda x, y, z: None,
                                    lambda x, y, z: None,
                                    lambda x, y: None,
                                    [(0, 0xFFFFFFFF)])
    mem = hp_mem_mgr.malloc(1, DMADirection.HOST_TO_DEVICE)
    hp_mem_mgr.free(mem)
    hp_mem_mgr.free_all()

    # Test free
    hp_mem_mgr = HugePagesMemoryMgr(4096,
                                    lambda x, y, z: None,
                                    lambda x, y, z: None,
                                    lambda x, y: None,
                                    [(0, 0xFFFFFFFF)])
    mem = hp_mem_mgr.malloc(1, DMADirection.HOST_TO_DEVICE)
    hp_mem_mgr.free(mem)

    mem = hp_mem_mgr.malloc(40960, DMADirection.HOST_TO_DEVICE)

    # Test free_all
    hp_mem_mgr.free_all()


def test_hugepages_iova_mgr(mocked_hugepages):
    # Test iova != 0, does not get bumped to + 1000
    hp_mem_mgr = HugePagesMemoryMgr(4096,
                                    lambda x, y, z: None,
                                    lambda x, y, z: None,
                                    lambda x, y: None,
                                    [(0x1000, 0xFFFFFFFF)])
    assert hp_mem_mgr.iova_mgr.get(4096) == 0x1000

    # Test iovas spanning ranges
    hp_mem_mgr = HugePagesMemoryMgr(4096,
                                    lambda x, y, z: None,
                                    lambda x, y, z: None,
                                    lambda x, y: None,
                                    [(0x1000, 0x2000), (0x3000, 0xFFFFFFFF)])
    assert hp_mem_mgr.iova_mgr.get(4096) == 0x1000
    assert hp_mem_mgr.iova_mgr.num_allocated_iovas() == 1
    hp_mem_mgr.iova_mgr.free(0x1000)
    assert hp_mem_mgr.iova_mgr.num_allocated_iovas() == 0


def test_hugepages_malloc_failure(mocker, mocked_hugepages):
    mocker.patch('hugepages.malloc', return_value=0)

    with pytest.raises(MemoryError):
        HugePagesMemoryMgr(4096,
                           lambda x, y, z: None,
                           lambda x, y, z: None,
                           lambda x, y: None,
                           [(0, 0xFFFFFFFF)])
