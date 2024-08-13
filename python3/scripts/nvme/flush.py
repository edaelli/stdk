import argparse
import logging

# Import NVMe device. This gets us (and the driver) access to the device's
#   PCIe and NVMe registers
from lone.nvme.device import NVMeDevice

# Import NVMe spec objects we will use for commands
from lone.nvme.spec.commands.nvm.flush import Flush
from lone.util.logging import log_format


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='Turn on debug logging')
    parser.add_argument('pci_slot', type=str)
    parser.add_argument('namespace', type=lambda x: int(x, 0))
    args = parser.parse_args()

    # Set our global logging config here depending on what the user requested
    level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format=log_format)
    logger = logging.getLogger('rw')

    # Create a NVMeDevice object for the slot we want to work with
    logger.info('Working on device {}'.format(args.pci_slot))
    nvme_device = NVMeDevice(args.pci_slot)

    # Disable, create queues, get namespace information
    nvme_device.cc_disable()
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    nvme_device.init_io_queues(num_queues=1, queue_entries=16)

    flush_cmd = Flush(NSID=args.namespace)
    nvme_device.sync_cmd(flush_cmd, timeout_s=1)


if __name__ == '__main__':
    main()
