import argparse

from lone.nvme.device import NVMeDevice
from lone.nvme.spec.commands.admin.get_set_feature import (GetFeaturePowerManagement,
                                                           SetFeaturePowerManagement)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    parser.add_argument('--set-ps', type=int, default=None)
    parser.add_argument('--set-ps-save', action='store_true', default=False)
    args = parser.parse_args()

    # Create NVMe device and initialize it (only need admin queues)
    nvme_device = NVMeDevice(args.pci_slot)
    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()
    nvme_device.id_data.initialize()

    # Get identify controller data
    id_ctrl_data = nvme_device.id_data.controller

    # Print all power states reported by the device first
    print('Power States:')
    for i in range(id_ctrl_data.NPSS):
        power_scale = 0.01 if id_ctrl_data.PSDS[i].MXPS == 0 else 0.0001
        print(f'  {i}: {id_ctrl_data.PSDS[i].MP * power_scale} Watts')

    # Get current power state
    gf_pm = GetFeaturePowerManagement()
    nvme_device.sync_cmd(gf_pm)
    gf_data = gf_pm.response(gf_pm.cqe)
    print(f'Current power state: {gf_data.PS} (wl hint: 0x{gf_data.WH:x})')

    # Set new power state if requested
    if args.set_ps is not None:
        print('User requested a change in power state')

        power_scale = 0.01 if id_ctrl_data.PSDS[args.set_ps].MXPS == 0 else 0.0001
        print(f'  Setting PS to: {args.set_ps}: '
              f'{id_ctrl_data.PSDS[args.set_ps].MP * power_scale} Watts')

        # Set it
        sf_pm = SetFeaturePowerManagement(PS=args.set_ps, SV=args.set_ps_save)
        nvme_device.sync_cmd(sf_pm)

        # Get current power state after setting
        gf_pm = GetFeaturePowerManagement()
        nvme_device.sync_cmd(gf_pm)
        gf_data = gf_pm.response(gf_pm.cqe)
        power_scale = 0.01 if id_ctrl_data.PSDS[gf_data.PS].MXPS == 0 else 0.0001
        print(f'  Current Power State: {gf_data.PS}: '
              f'{id_ctrl_data.PSDS[gf_data.PS].MP * power_scale} Watts')
