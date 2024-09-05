import pytest
import os
import subprocess
import ctypes
import importlib.util
from types import SimpleNamespace

from lone.system.linux.requirements import LinuxRequirements
from lone.system.linux.vfio import VfioIoctl, VfioGetApiVersion
from lone.system.linux.vfio import SysVfioIfc, SysVfio


def test_system_picker(mocker):
    mocker.patch('platform.system', return_value='Linux')
    file_path = os.path.abspath(os.path.join(__file__, '../../../../lone/system/__init__.py'))
    spec = importlib.util.spec_from_file_location('test.system', file_path)
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)


def test_system_picker_module_not_found(mocker):
    mocker.patch('platform.system', return_value='Linux')
    file_path = os.path.abspath(os.path.join(__file__, '../../../../lone/system/__init__.py'))
    spec = importlib.util.spec_from_file_location('test.system', file_path)
    test_module = importlib.util.module_from_spec(spec)
    mocker.patch('importlib.util.module_from_spec', side_effect=ModuleNotFoundError)
    spec.loader.exec_module(test_module)


def test_system_picker_not_implemented(mocker):
    file_path = os.path.abspath(os.path.join(__file__, '../../../../lone/system/__init__.py'))
    spec = importlib.util.spec_from_file_location('test.system', file_path)
    mocker.patch('platform.system', return_value='test_system')
    spec = importlib.util.spec_from_file_location('test.system', file_path)
    test_module = importlib.util.module_from_spec(spec)
    with pytest.raises(NotImplementedError):
        spec.loader.exec_module(test_module)


def test_system_interface(mocker):

    from lone.system import SysRequirements
    mocker.patch("lone.system.SysRequirements.__abstractmethods__", set())
    reqs = SysRequirements()
    with pytest.raises(NotImplementedError):
        reqs.check_requirements()

    from lone.system import SysPci
    mocker.patch("lone.system.SysPci.__abstractmethods__", set())
    sys_pci = SysPci()
    with pytest.raises(NotImplementedError):
        sys_pci.rescan()

    from lone.system import SysPciDevice
    mocker.patch("lone.system.SysPciDevice.__abstractmethods__", set())
    sys_pci_dev = SysPciDevice('pci_slot')
    with pytest.raises(NotImplementedError):
        sys_pci_dev.exists()
    with pytest.raises(NotImplementedError):
        sys_pci_dev.remove()
    with pytest.raises(NotImplementedError):
        sys_pci_dev.expose('user')
    with pytest.raises(NotImplementedError):
        sys_pci_dev.reclaim('driver')

    from lone.system import SysPciUserspace
    mocker.patch("lone.system.SysPciUserspace.__abstractmethods__", set())
    sys_pci_userspace = SysPciUserspace()
    with pytest.raises(NotImplementedError):
        sys_pci_userspace.devices()
    with pytest.raises(NotImplementedError):
        sys_pci_userspace.exposed_devices()

    from lone.system import SysPciUserspaceDevice
    mocker.patch("lone.system.SysPciUserspaceDevice.__abstractmethods__", set())
    sys_pci_userspace_dev = SysPciUserspaceDevice('pci_slot')
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.pci_regs()
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.nvme_regs()
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.map_dma_region_read(0, 0, 0)
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.map_dma_region_write(0, 0, 0)
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.map_dma_region_rw(0, 0, 0)
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.unmap_dma_region(0, 0)
    with pytest.raises(NotImplementedError):
        sys_pci_userspace_dev.reset()

    from lone.system import MemoryLocation
    mem = MemoryLocation(0, 0, 0, 'test_system.py')
    mem


def test_iova_mgr():
    from lone.system import IovaMgr
    iova_mgr = IovaMgr(0xED000000)
    assert iova_mgr.get(0x1000) == 0xED000000
    assert iova_mgr.get(0x1000) == 0xED001000
    iova_mgr.free(0xED000000)


def test_no_mem_mgr(mocker):
    mocker.patch('platform.system', return_value='Linux')
    mocker.patch('importlib.util.find_spec', lambda x: None)

    file_path = os.path.abspath(os.path.join(__file__, '../../../../lone/system/__init__.py'))
    spec = importlib.util.spec_from_file_location('system', file_path)
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)


def test_linux_sys_pci(mocker):
    from lone.system.linux.pci import LinuxSysPci
    sys_pci = LinuxSysPci()

    mocker.patch('builtins.open', mocker.mock_open(read_data='0'))
    sys_pci.rescan()


def test_linux_sys_pci_device(mocker):
    from lone.system.linux.pci import LinuxSysPciDevice
    mocker.patch('os.readlink', return_value='')
    sys_pci_dev = LinuxSysPciDevice('')

    mocker.patch('os.path.exists', return_value=False)
    sys_pci_dev.exists()

    mocker.patch('os.path.exists', return_value=False)
    sys_pci_dev.remove()
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('builtins.open', mocker.mock_open(read_data='0'))
    sys_pci_dev.remove()

    mocker.patch('os.path.exists', return_value=False)
    mocker.patch('pwd.getpwnam', return_value=SimpleNamespace(pw_uid=1000, pw_gid=1000))
    mocker.patch('pwd.getpwuid', return_value=SimpleNamespace(pw_uid=1000, pw_gid=1000))
    mocker.patch('os.chown', return_value=True)
    mocker.patch('os.stat', return_value=SimpleNamespace(st_uid=1000, st_gid=1000))
    mocker.patch('subprocess.check_output', return_value=b'00:00.0 0000 1234:5678')

    sys_pci_dev.expose('user')
    sys_pci_dev.expose('1000')
    sys_pci_dev.expose(1000)

    mocker.patch('os.path.exists', return_value=False)
    sys_pci_dev.reclaim('driver')

    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.basename', return_value='test')
    sys_pci_dev._unbind_current_driver()

    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.basename', return_value='vfio_pci')
    sys_pci_dev._unbind_current_driver()

    mocker.patch('os.path.exists', return_value=False)
    sys_pci_dev._bind_to_driver('driver')

    mocker.patch('os.path.exists', return_value=True)
    sys_pci_dev._bind_to_driver('driver')

    mocker.patch('os.path.exists', return_value=True)
    sys_pci_dev._create_device()

    sys_pci_dev._change_device_ownership('path', 'owner')
    sys_pci_dev._change_device_ownership('path', 1000)
    with pytest.raises(Exception):
        sys_pci_dev._change_device_ownership('path', [])


def test_requirements():
    req = LinuxRequirements()

    req.print_status('desc', True)
    req.print_status('desc', False)
    req.print_status('desc', False, extra='extra')


def test_check_requirements():
    req = LinuxRequirements()
    req.check_python = lambda: None
    req.check_ubuntu = lambda: None
    req.check_VT_VI = lambda: None
    req.check_hugepages = lambda: None
    req.check_hugepages_lib = lambda: None

    req.failure = True
    req.check_requirements()

    req.failure = False
    req.check_requirements()


def test_check_python(mocker):
    req = LinuxRequirements()

    mocker.patch('sys.version_info', (3, 0, 0))
    mocker.patch('platform.python_version', return_value='3.0.0')
    req.check_python()

    mocker.patch('sys.version_info', (3, 10, 0))
    mocker.patch('platform.python_version', return_value='3.10.0')
    req.check_python()


def test_check_ubuntu(mocker):
    req = LinuxRequirements()

    output = b'''
        No LSB modules are available.
        Distributor ID: Ubuntu
        Description:    Ubuntu 20.04.4 LTS
        Release:        20.04
        Codename:       focal
    '''
    mocker.patch('subprocess.check_output', return_value=output)
    req.check_ubuntu()

    output = b'''
        No LSB modules are available.
        Distributor ID: Ubuntu
        Description:    Ubuntu 19.04.4 LTS
        Release:        19.04
        Codename:       focal
    '''
    mocker.patch('subprocess.check_output', return_value=output)
    req.check_ubuntu()

    mocker.patch('subprocess.check_output', side_effect=Exception('test'))
    with pytest.raises(Exception):
        req.check_ubuntu()


def test_check_vt_vi(mocker):
    req = LinuxRequirements()

    mocker.patch('subprocess.check_call', return_value='')
    req.check_VT_VI()

    mocker.patch('subprocess.check_call', side_effect=subprocess.CalledProcessError('test', 'cmd'))
    req.check_VT_VI()


def test_hugepages(mocker):
    req = LinuxRequirements()

    data = '''
        HugePages_Total:     128
        HugePages_Free:      128
        HugePages_Rsvd:        0
        HugePages_Surp:        0
        Hugepagesize:       2048 kB
        Hugetlb:          262144 kB
    '''
    mocker.patch('builtins.open', mocker.mock_open(read_data=data))
    req.check_hugepages()


def test_hugepages_lib(mocker):
    req = LinuxRequirements()

    mocker.patch('subprocess.check_call', return_value=0)
    req.check_hugepages_lib()

    mocker.patch('subprocess.check_call', side_effect=subprocess.CalledProcessError('test', 'cmd'))
    req.check_hugepages_lib()


def test_vfio_ioctl(mocker):
    vfio_ioctl = VfioIoctl()
    vfio_ioctl

    mocker.patch('ioctl_opt.IO', return_value=0)
    mocker.patch('fcntl.ioctl', return_value=0)

    # Test the VfioIoctl interfaces
    VfioGetApiVersion().ioctl(0)
    VfioGetApiVersion().ioctl(0, 0)
    VfioGetApiVersion().ioctl(0)
    VfioGetApiVersion().get_data()


def test_sysvfioifc_init(mocker):
    # Test interface without init
    ifc = SysVfioIfc('test', init=False)
    assert ifc.pci_slot == 'test'

    # Test interface with init
    mocker.patch('os.open', return_value=0)
    mocker.patch('os.readlink', return_value='')
    mocker.patch('fcntl.ioctl',
                 side_effect=[0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05, 0x00] + [0] * 9)
    from lone.system.linux.vfio import VfioGroupGetStatus, VfioDeviceGetInfo
    mocker.patch('lone.system.linux.vfio.VfioGroupGetStatus.get_data',
                 side_effect=[VfioGroupGetStatus(flags=0x01), VfioGroupGetStatus(flags=0x03)])
    mocker.patch('lone.system.linux.vfio.VfioDeviceGetInfo.get_data',
                 side_effect=[VfioDeviceGetInfo(num_regions=9)])
    ifc = SysVfioIfc('test', init=True)


def test_get_irq_info(mocker):
    mocker.patch('fcntl.ioctl', return_value=0)
    ifc = SysVfioIfc('test', init=False)
    ifc.device_fd = 1
    ifc.get_irq_info()


def test_enable_msix(mocker):
    mocker.patch('fcntl.ioctl', return_value=0)
    ifc = SysVfioIfc('test', init=False)
    ifc.device_fd = 1
    ifc.enable_msix(1, 0)


def test_get_msix_vector_pending_count(mocker):
    mocker.patch('os.read', side_effect=[bytes(0), BlockingIOError()])
    ifc = SysVfioIfc('test', init=False)
    ifc.device_fd = 1
    ifc.eventfds = [0]
    ifc.get_msix_vector_pending_count(0)
    ifc.get_msix_vector_pending_count(0)


def test_sysvfioifc_pci_regs(mocker):
    ifc = SysVfioIfc('test', init=False)
    ifc.device_fd = 1
    ifc.pci_region = {'size': 0, 'offset': 0}
    pci_regs = ifc.pci_regs()

    assert pci_regs.ID.VID == 0x0000
    pci_regs.ID.VID = 0x1234


def test_sysvfioifc_nvme_regs(mocker):
    ifc = SysVfioIfc('test', init=False)
    assert ifc.pci_slot == 'test'
    ifc.device_fd = 1
    ifc.bars = []
    ifc.bars.append({'size': 0, 'offset': 0})
    mocker.patch('mmap.mmap', return_value=(ctypes.c_uint8 * 16 * 1024)())
    ifc.nvme_regs()


def test_sysvfioifc_dma(mocker):
    ifc = SysVfioIfc('test', init=False)
    ifc.container_fd = 1
    mocker.patch('fcntl.ioctl', return_value=0)
    ifc.map_dma_region(0, 0, 0, 0)
    ifc.map_dma_region_read(0, 0, 0)
    ifc.map_dma_region_write(0, 0, 0)
    ifc.map_dma_region_rw(0, 0, 0)
    ifc.unmap_dma_region(0, 0)


def test_sysvfioifc_reset(mocker):
    ifc = SysVfioIfc('test', init=False)
    mocker.patch('fcntl.ioctl', return_value=0)
    ifc.device_fd = 1
    ifc.reset()


def test_sysvfioifc_clean(mocker):
    ifc = SysVfioIfc('test', init=False)
    ifc.container_fd = 1
    ifc.group_fd = 1
    ifc.device_fd = 1
    ifc.nvme_registers = 0
    ifc.nvme_mmap = open('/tmp/test', 'wb')
    mocker.patch('os.close', return_value=0)
    mocker.patch('fcntl.ioctl', return_value=0)
    ifc.clean()


def test_sysvfio_exposed_devices(mocker):
    sysvfio = SysVfio()
    mocker.patch('subprocess.check_output', return_value=b'')
    mocker.patch('pyudev.Context.list_devices', return_value=[])
    sysvfio.exposed_devices()


def test_sysvfio_devices(mocker):
    sysvfio = SysVfio()

    mocker.patch('subprocess.check_output', return_value=b'')
    mocker.patch('pyudev.Context.list_devices', return_value=[])
    sysvfio.devices()

    mocker.patch('pyudev.Context.list_devices', return_value=[{'SUBSYSTEM': 'not_pci'}])
    sysvfio.devices()

    mocker.patch('subprocess.check_output',
                 side_effect=subprocess.CalledProcessError('test', 'cmd'))
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()

    mocker.patch('subprocess.check_output', side_effect=[
        b'/sys/kernel/iommu_groups/17/devices/not_find_name\n',
        b'\n',
        b'\nslot_name: information\n'])
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()

    mocker.patch('subprocess.check_output', side_effect=[
        b'/sys/kernel/iommu_groups/17/devices/slot_name\n',
        b'\n',
        b'\nslot_name: information\n'])
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()

    mocker.patch('subprocess.check_output', side_effect=[
        b'/sys/kernel/iommu_groups/17/devices/slot_name\n',
        b'\n',
        b'\nslot_name: information\n'])
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'DEVNAME': 'test',
                                'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()

    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.readlink', return_value='')
    mocker.patch('subprocess.check_output', side_effect=[
        b'/sys/kernel/iommu_groups/17/devices/slot_name\n',
        b'\n',
        b'\nslot_name: information\n'])
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'DEVNAME': 'test',
                                'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()

    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.readlink', return_value='vfio_pci')
    mocker.patch('pathlib.Path.owner', return_value='owner')
    mocker.patch('subprocess.check_output', side_effect=[
        b'/sys/kernel/iommu_groups/17/devices/slot_name\n',
        b'\n',
        b'\nslot_name: information\n'])
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'DEVNAME': 'test',
                                'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()

    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.readlink', return_value='vfio_pci')
    mocker.patch('pathlib.Path.owner', return_value='owner')
    mocker.patch('subprocess.check_output', side_effect=[
        b'/sys/kernel/iommu_groups/17/devices/slot_name\n',
        b'test\n',
        b'\nslot_name: information\n'])
    mocker.patch('pyudev.Context.list_devices',
                 return_value=[{'DEVNAME': 'test',
                                'SUBSYSTEM': 'pci',
                                'PCI_CLASS': '10802',
                                'PCI_SLOT_NAME': 'slot_name',
                                'PCI_ID': '1:1'}])
    sysvfio.devices()
