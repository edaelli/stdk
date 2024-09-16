import pytest
import importlib

from lone.system import (SysPci, SysPciDevice, SysPciUserspace,
                         SysPciUserspaceDevice, DMADirection, MemoryLocation,
                         DevMemMgr)


def abs_tester(mocker, cls, *args):

    # Test it is abstract
    with pytest.raises(TypeError):
        cls()

    # Mock and test abstract methods raise NotImplementedError
    mocker.patch.multiple(cls, __abstractmethods__=set())
    t = cls(*args)
    return t


def test_sys_pci(mocker):
    t = abs_tester(mocker, SysPci)

    with pytest.raises(NotImplementedError):
        t.rescan()


def test_sys_pci_device(mocker):
    t = abs_tester(mocker, SysPciDevice, 'slot')

    with pytest.raises(NotImplementedError):
        t.exists()

    with pytest.raises(NotImplementedError):
        t.remove()

    with pytest.raises(NotImplementedError):
        t.expose(None)

    with pytest.raises(NotImplementedError):
        t.reclaim(None)


def test_sys_pci_userspace(mocker):
    t = abs_tester(mocker, SysPciUserspace)

    with pytest.raises(NotImplementedError):
        t.devices()

    with pytest.raises(NotImplementedError):
        t.exposed_devices()


def test_sys_pci_userspace_device(mocker):
    t = abs_tester(mocker, SysPciUserspaceDevice, 'slot')

    with pytest.raises(NotImplementedError):
        t.pci_regs()

    with pytest.raises(NotImplementedError):
        t.nvme_regs()

    with pytest.raises(NotImplementedError):
        t.map_dma_region_read(None, None, None)

    with pytest.raises(NotImplementedError):
        t.map_dma_region_write(None, None, None)

    with pytest.raises(NotImplementedError):
        t.map_dma_region_rw(None, None, None)

    with pytest.raises(NotImplementedError):
        t.unmap_dma_region(None, None)

    with pytest.raises(NotImplementedError):
        t.reset()


def test_sys_dma_direction(mocker):
    with pytest.raises(ValueError):
        DMADirection(0)
    assert DMADirection(1) == DMADirection.HOST_TO_DEVICE
    assert DMADirection(2) == DMADirection.DEVICE_TO_HOST
    assert DMADirection(3) == DMADirection.BIDIRECTIONAL
    with pytest.raises(ValueError):
        DMADirection(4)


def test_sys_memory_location(mocker):
    m = MemoryLocation(0, 0, 4096, 'test')
    assert m.vaddr == 0
    assert m.iova == 0
    assert m.size == 4096


def test_sys_dev_mem_mgr(mocker):
    t = abs_tester(mocker, DevMemMgr, 4096)

    with pytest.raises(NotImplementedError):
        t.malloc(0, 0, 0)

    with pytest.raises(NotImplementedError):
        t.free(0)

    with pytest.raises(NotImplementedError):
        t.free_all()

    with pytest.raises(NotImplementedError):
        t.allocated_mem_list()

    with pytest.raises(NotImplementedError):
        t.dump()

    mocker.patch.object(t, 'allocated_mem_list', lambda: [])
    str(t)
    t.dump()

    mocker.patch.object(t, 'allocated_mem_list', lambda: [MemoryLocation(0, 0, 0, 'test')])
    str(t)
    t.dump()


def test_sys_picker(mocker):
    from lone import system

    # Test normal linux path
    mocker.patch('platform.system', return_value='Linux')
    importlib.reload(system)

    # Test anything other than linux raises NotImplementedError
    mocker.patch('platform.system', return_value='Windows')
    with pytest.raises(NotImplementedError):
        importlib.reload(system)

    # Test linux path when we cannot find modules
    mocker.patch('platform.system', return_value='Linux')
    mocker.patch('importlib.util.find_spec', return_value=None)
    importlib.reload(system)

    # Test linux path when we cannot load modules
    mocker.patch('platform.system', return_value='Linux')
    mocker.patch('importlib.util.find_spec', return_value=True)
    mocker.patch('importlib.util.module_from_spec', side_effect=[ModuleNotFoundError()])
    importlib.reload(system)
