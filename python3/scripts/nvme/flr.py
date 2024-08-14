import sys
import argparse
import time

# lone imports
from lone.nvme.device import NVMeDevice
from lone.nvme.device.identify import NVMeDeviceIdentifyData


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    args = parser.parse_args()

    nvme_device = NVMeDevice(args.pci_slot)

    # Make sure we can talk to the device
    nvme_device.cc_disable()
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    id_data = NVMeDeviceIdentifyData(nvme_device)

    # Get the PCIeExpress capability to set the "Initiate FLR" bit
    pcie_cap = [cap for cap in nvme_device.pcie_regs.capabilities if
                cap._cap_id_ is nvme_device.pcie_regs.PCICapExpress._cap_id_][0]

    assert nvme_device.nvme_regs.CC.EN == 1, "Device not enabled before FLR"
    print('Initiating FLR on slot: {} SN: {} MN: {} FR: {}'.format(
        args.pci_slot,
        id_data.controller.SN,
        id_data.controller.MN,
        id_data.controller.FR))
    pcie_cap.PXDC.IFLR = 1
    time.sleep(0.2)
    assert nvme_device.nvme_regs.CC.EN == 0, "Device not disabled after FLR"

    # Re-initialize the device and get the identify data again
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    id_data_after = NVMeDeviceIdentifyData(nvme_device)

    assert id_data.controller.SN == id_data_after.controller.SN
    assert id_data.controller.MN == id_data_after.controller.MN
    assert id_data.controller.FR == id_data_after.controller.FR


if __name__ == '__main__':
    sys.exit(main())
