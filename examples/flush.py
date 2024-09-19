import argparse

# lone imports
from lone.nvme.device import NVMeDevice
from lone.nvme.spec.commands.nvm.flush import Flush


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    parser.add_argument('namespace', type=lambda x: int(x, 0))
    args = parser.parse_args()

    print('Working on device {}'.format(args.pci_slot))

    # Create a NVMeDevice object for the slot we want to work with
    nvme_device = NVMeDevice(args.pci_slot)

    # Disable, create queues, get namespace information
    nvme_device.cc_disable()
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    nvme_device.create_io_queues(num_queues=1, queue_entries=16)

    flush_cmd = Flush(NSID=args.namespace)
    nvme_device.sync_cmd(flush_cmd, timeout_s=1)
    print(f'Flush command (nsid: 0x{args.namespace:x}) complete!')


if __name__ == '__main__':
    main()
