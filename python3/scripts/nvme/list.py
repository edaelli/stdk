import sys
import argparse
from types import SimpleNamespace

# lone imports
from lone.system import System
from lone.nvme.device import NVMeDevice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pci-slot', default=None, help='Only list device at this pci slot')
    args = parser.parse_args()

    # Copy the output of nvme-cli's list command
    fmt = '{:<16} {:<20} {:<40} {:<9} {:<26} {:<16} {:<8}'
    print(fmt.format('Node', 'SN', 'Model', 'Namespace', 'Usage', 'Format', 'FW Rev'))
    print(fmt.format('-' * 16, '-' * 20, '-' * 40, '-' * 9, '-' * 26, '-' * 16, '-' * 8))

    # One of the system's interfaces is the current OS's view of all exposed devices we
    #   can work with. Use that interface and list them all, unless the user requested a
    #   specific one
    if args.pci_slot:
        pci_slots = [args.pci_slot]
    else:
        devices = [SimpleNamespace(pci_slot='nvsim')] + System.PciUserspace().exposed_devices()
        pci_slots = [device.pci_slot for device in devices]

    # Print info on all devices
    for pci_slot in pci_slots:
        # Create the nvme device object
        nvme_device = NVMeDevice(pci_slot)

        # Disable the device
        nvme_device.cc_disable()

        # Init admin queues, re-enable, initialize identify data
        nvme_device.init_admin_queues(16, 16)
        nvme_device.cc_enable()
        nvme_device.id_data.initialize()

        # Print all namespaces and their info
        for ns_id, ns in enumerate(nvme_device.id_data.namespaces):
            if ns:
                # Print the information for this device and namespace
                print(fmt.format(pci_slot,
                                 nvme_device.id_data.controller.SN.strip().decode(),
                                 nvme_device.id_data.controller.MN.strip().decode(),
                                 ns_id,
                                 '{:>6} {} / {:>6} {}'.format(ns.ns_usage,
                                                              ns.ns_unit,
                                                              ns.ns_total,
                                                              ns.ns_unit),
                                 '{:>3} {:>4} + {} B'.format(ns.lba_size,
                                                             ns.lba_unit,
                                                             ns.ms_bytes),
                                 nvme_device.id_data.controller.FR.strip().decode()))

        # All done, disable device and free all memory
        nvme_device.cc_disable()
        nvme_device.mem_mgr.free_all()


if __name__ == '__main__':
    sys.exit(main())
