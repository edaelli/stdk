import pytest
from types import SimpleNamespace

from lone.system.linux.pci import LinuxSysPci, LinuxSysPciDevice


@pytest.fixture(scope='function')
def mocked_linux_sys_pci_device(mocker):
    mocker.patch('builtins.open', mocker.mock_open(read_data='data'))
    mocker.patch('os.readlink', return_value='/mocked_path/path/')

    return LinuxSysPciDevice('pci_slot')


def test_linux_sys_pci(mocker):
    mocker.patch('builtins.open', mocker.mock_open(read_data='data'))
    lin_sys_pci = LinuxSysPci()
    lin_sys_pci.rescan()


def test_linux_sys_pci_device(mocked_linux_sys_pci_device):
    assert mocked_linux_sys_pci_device.pci_slot == 'pci_slot'


def test_linux_sys_pci_device_exists(mocked_linux_sys_pci_device):
    ''' def exists(self):
    '''
    assert mocked_linux_sys_pci_device.exists() is False


def test_linux_sys_pci_device_remove(mocker, mocked_linux_sys_pci_device):
    ''' def remove(self):
    '''
    mocker.patch('os.path.exists', return_value=False)
    mocked_linux_sys_pci_device.remove()

    mocker.patch('os.path.exists', return_value=True)
    mocked_linux_sys_pci_device.remove()


def test_linux_sys_pci_device_expose(mocker, mocked_linux_sys_pci_device):
    ''' def expose(self, user):
    '''
    mocker.patch('subprocess.check_output', side_effect=[b'a b c d e f g'] * 5)
    mocker.patch('os.chown', return_value=None)
    mocker.patch('os.stat', return_value=SimpleNamespace(st_uid=1000,
                                                         st_gid=1000,
                                                         st_mode=0,
                                                         st_size=0,
                                                         st_mtime=0))

    mocker.patch('pwd.getpwnam', return_value=SimpleNamespace(pw_uid=1000,
                                                              pw_gid=1000))
    mocked_linux_sys_pci_device.expose('1000')

    mocker.patch('pwd.getpwnam', return_value=SimpleNamespace(pw_uid=1000,
                                                              pw_gid=1000))
    mocked_linux_sys_pci_device.expose('user')

    mocker.patch('pwd.getpwuid', return_value=SimpleNamespace(pw_uid=1000,
                                                              pw_gid=1000))
    mocked_linux_sys_pci_device.expose(1000)

    mocker.patch('os.path.exists', return_value=False)
    mocked_linux_sys_pci_device.expose(1000)

    # Invalid type
    with pytest.raises(Exception):
        mocked_linux_sys_pci_device.expose(list())


def test_linux_sys_pci_device_reclaim(mocker, mocked_linux_sys_pci_device):
    ''' def reclaim(self, driver):
    '''
    mocker.patch('subprocess.check_output', side_effect=[b'a b c d e f g'] * 3)

    mocker.patch('os.path.basename', return_value='test')
    mocker.patch('os.path.exists', return_value=True)
    mocked_linux_sys_pci_device.reclaim('test')

    mocker.patch('os.path.basename', return_value='vfio_pci')
    mocker.patch('os.path.exists', return_value=True)
    mocked_linux_sys_pci_device.reclaim('vfio_pci')

    mocker.patch('os.path.exists', return_value=False)
    mocked_linux_sys_pci_device.reclaim('vfio_pci')
