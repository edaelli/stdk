import sys
import argparse
import time
import copy

# lone imports
from lone.nvme.device import NVMeDevice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    args = parser.parse_args()

    print(f'Working on device {args.pci_slot}')

    # Create device based on the pci_slot passed in
    nvme_device = NVMeDevice(args.pci_slot)

    # Disable, init admin queues, enable, initi id data
    nvme_device.cc_disable()
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    nvme_device.id_data.initialize()

    # Save a copy of id_data before we FLR
    id_data_before = copy.copy(nvme_device.id_data)

    # Initiate FLR
    print(f'Initiating FLR on slot: {args.pci_slot}')
    nvme_device.initiate_flr()

    # Wait 2x the spec time (100ms) for it to complete
    time.sleep(0.2)

    # Verify that the device comes up disabled after an FLR
    assert nvme_device.nvme_regs.CC.EN == 0, "Device not disabled after FLR"

    # Re-initialize the device and get the identify data again
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    nvme_device.id_data.initialize()
    id_data_after = copy.copy(nvme_device.id_data)

    # Compare before/after for sanity
    assert id_data_before.controller.SN == id_data_after.controller.SN
    assert id_data_before.controller.MN == id_data_after.controller.MN
    assert id_data_before.controller.FR == id_data_after.controller.FR

    print(f'FLR complete on slot: {args.pci_slot}')


if __name__ == '__main__':
    sys.exit(main())
