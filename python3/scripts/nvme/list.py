import sys
import argparse
import logging
from types import SimpleNamespace

# lone imports
from lone.system import System
from lone.nvme.device import NVMeDevice
from lone.nvme.device.identify import NVMeDeviceIdentifyData
from lone.util.logging import log_format


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='Turn on debug logging')
    parser.add_argument('--pci-slot', default=None, help='Only list device at this pci slot')
    args = parser.parse_args()

    # Set our global logging config here depending on what the user requested
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format=log_format)

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

        # Device's memory manager. Implements the DevMemMgr interface
        mem_mgr = nvme_device.mem_mgr

        # Disable the device. Free all memory (not really needed here since we just
        #   created the mem_mgr and have not allocated anything, but leaving in for
        #   demonstration purposes)
        nvme_device.cc_disable()
        mem_mgr.free_all()

        # Init admin queues, re-enable
        nvme_device.init_admin_queues(256, 16)
        nvme_device.cc_enable()

        # Get identify data from the device
        id_data = NVMeDeviceIdentifyData(nvme_device)

        # Create IO queues
        nvme_device.create_io_queues(num_queues=1, queue_entries=16)
        nvme_device.delete_io_queues()

        # Print all namespaces and their info
        for ns_id, ns in enumerate(id_data.namespaces):
            if ns:
                # Print the information for this device and namespace
                print(fmt.format(pci_slot,
                                 id_data.controller.SN.strip().decode(),
                                 id_data.controller.MN.strip().decode(),
                                 ns_id,
                                 '{:>6} {} / {:>6} {}'.format(ns.ns_usage,
                                                              ns.ns_unit,
                                                              ns.ns_total,
                                                              ns.ns_unit),
                                 '{:>3} {:>4} + {} B'.format(ns.lba_size,
                                                             ns.lba_unit,
                                                             ns.ms_bytes),
                                 id_data.controller.FR.strip().decode()))

        # All done, disable device and free all memory
        nvme_device.cc_disable()
        mem_mgr.free_all()

        # Verify that all memory is freed
        assert len(mem_mgr.allocated_mem_list()) == 0, 'Exiting with allocated memory!'


if __name__ == '__main__':
    sys.exit(main())
