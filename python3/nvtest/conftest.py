import os
import pytest
import yaml

from lone.util.logging import log_init


def pytest_addoption(parser):
    # Figure out the ci_tox.yml path and use it as default
    #  to allow users to just call pytest from the root of
    #  the repo for tox/ci testing
    default_path = os.path.abspath(
        os.path.join(__file__, '../', 'tox_cov.yml'))

    # Add the config option so we can configure tests with an yaml file
    parser.addoption("--config", required=False, default=default_path, type=str)
    parser.addoption("--pci-slot", required=False, default=None, type=str)


def pytest_configure(config):
    # Get config path if passed in to figure out what tests to run
    config_path = config.getoption('config')

    # If we have a valid config file passed in, parse it with yaml
    if config_path is not None:
        # Absolute path
        config_path = os.path.abspath(config.getoption('config'))

        # Make sure it exists
        assert os.path.exists(config_path), 'Config path: {} does not exist'.format(config_path)

        with open(config_path) as fh:
            config_data = yaml.load(fh, Loader=yaml.SafeLoader)

            if 'pytest' in config_data:
                if 'verbose' in config_data['pytest']:
                    config.option.verbose = config_data['pytest']['verbose']


def pytest_collection_modifyitems(session, config, items):
    logger = log_init()

    # Get config path if passed in to figure out what tests to run
    config_path = config.getoption('config')

    # If we have a valid config file passed in, parse it with yaml
    if config_path is not None:
        # Absolute path
        config_path = os.path.abspath(config.getoption('config'))

        # Make sure it exists
        assert os.path.exists(config_path), 'Config path: {} does not exist'.format(config_path)

        with open(config_path) as fh:
            config_data = yaml.load(fh, Loader=yaml.SafeLoader)

        # Does the config file specify what tests (and in what order) to run?
        # If so, adjust items here, otherwise run all discovered tests
        if 'test_list' in config_data and config_data['test_list'] is not None:
            # Check for duplicates on the test list
            config_tests = [*set(config_data['test_list'])]
            if len(config_data['test_list']) != len(config_tests):
                logger.warning('Duplicate tests in test_list will be combined into 1 run')

            # Clear items and make a copy to add them back in
            items_copy = items.copy()
            discovered_test_names = [n.name for n in items]
            discovered_test_nodeids = [n.nodeid for n in items]
            items.clear()

            # Now filter them out to only execute the ones in the config file, in the
            #  order they show up in the config file
            for test in config_tests:
                if test in discovered_test_names:
                    index = discovered_test_names.index(test)
                elif test in discovered_test_nodeids:
                    index = discovered_test_nodeids.index(test)
                else:
                    logger.error('{} not found! Tests found:'.format(test))
                    for t in items_copy:
                        logger.warning('NODEID: {} NAME: {}'.format(t.nodeid, t.name))
                    assert False, 'Requested test: {} not found!'.format(test)

                item = items_copy[index]
                if item in items:
                    logger.warning('Duplicate tests in test_list will be combined into 1 run')
                else:
                    items.append(items_copy[index])


@pytest.fixture(scope='session')
def lone_logger():
    # Get a logger and return it
    logger = log_init()
    return logger


@pytest.fixture(scope='session')
def lone_config(pytestconfig):

    class LoneConfig:
        def __init__(self):
            self.config_path = pytestconfig.getoption("--config")
            self.config = None

            # Override defaults if they are in the config file
            if self.config_path is not None:
                with open(self.config_path) as fh:
                    self.config = yaml.load(fh, Loader=yaml.SafeLoader)

            # Override pci-slot if defined
            pci_slot = pytestconfig.getoption("--pci-slot")
            if pci_slot is not None:
                self.config['dut']['pci_slot'] = pci_slot

    # Get our config passed in the form of a yaml file
    config = LoneConfig().config
    return config


@pytest.fixture(scope='function')
def nvme_device_raw(lone_config):
    from lone.nvme.device import NVMeDevice
    try:
        assert 'dut' in lone_config, (
            'Config must define a dut to use nvme_device_raw fixture')
        assert 'pci_slot' in lone_config['dut'], (
            'Config must define a dut pci_slot to use the nvme_device_raw fixture')
        nvme_device = NVMeDevice(lone_config['dut']['pci_slot'])

        yield nvme_device

    finally:
        pass


@pytest.fixture(scope='function')
def nvme_device(request, lone_config, lone_logger):
    from lone.nvme.device import NVMeDevice

    assert 'dut' in lone_config, (
        'Config must define a dut to use nvme_device fixture')
    assert 'pci_slot' in lone_config['dut'], (
        'Config must define a dut pci_slot to use the nvme_device fixture')
    nvme_device = NVMeDevice(lone_config['dut']['pci_slot'])

    # Default initialization parameters
    asq_entries = 16
    acq_entries = 16
    num_io_queues = 16
    io_queue_entries = 256

    # Allow the caller to override with
    #    @pytest.mark.parametrize('nvme_device',
    #       [{'asq_entries': 10, 'acq_entries': 10, 'num_io_queues': 10, 'io_queue_entries': 10}],
    #       indirect=True)
    #    def test__test(nvme_device):
    #        nvme_device has been initialized with the params passed above!
    if hasattr(request, 'param'):
        asq_entries = request.param['asq_entries']
        acq_entries = request.param['acq_entries']
        num_io_queues = request.param['num_io_queues']
        io_queue_entries = request.param['io_queue_entries']

    try:
        # Disable, create admin queues
        nvme_device.cc_disable()
        nvme_device.init_admin_queues(asq_entries=asq_entries, acq_entries=acq_entries)

        # Enable, get id information, create io queues
        nvme_device.cc_enable()
        nvme_device.create_io_queues(num_queues=num_io_queues, queue_entries=io_queue_entries)
        try:
            nvme_device.id_data.initialize()
        except Exception as e:
            lone_logger.exception(e)
            lone_logger.info('Not able to initialize identify data for device')

        yield nvme_device

    finally:
        pass
