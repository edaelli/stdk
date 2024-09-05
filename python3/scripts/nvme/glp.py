import sys
import os
import argparse
import time

from lone.nvme.device import NVMeDevicePhysical
from lone.nvme.spec.commands.admin.identify import IdentifyUUIDList
from lone.nvme.spec.commands.admin.get_log_page import GetLogPageCommandsSupportedAndEffects


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    parser.add_argument('--page', type=str, default='GetLogPageCommandsSupportedAndEffects')
    args = parser.parse_args()

    # Create NVMe device and initialize it
    nvme_device = NVMeDevicePhysical(args.pci_slot)
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()

    # Figure out what page we are sending
    if args.page == 'GetLogPageCommandsSupportedAndEffects':
        glp_cmd = GetLogPageCommandsSupportedAndEffects()

    # Send it out, get reply
    nvme_device.alloc(glp_cmd)
    nvme_device.sync_cmd(glp_cmd)

    # Post process results
    if args.page == 'GetLogPageCommandsSupportedAndEffects':

        for i in range(256):
            print(f'ADMIN Command OPC: 0x{i:04x} CSUPP: {glp_cmd.data_in.ACS[i].CSUPP}')

        for i in range(256):
            print(f'NVM   Command OPC: 0x{i:04x} CSUPP: {glp_cmd.data_in.IOCS[i].CSUPP}')

