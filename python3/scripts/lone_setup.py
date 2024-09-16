import os
import sys
import argparse
from types import SimpleNamespace

from lone.system import System


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['list', 'expose', 'reclaim'])
    args, unknown_args = parser.parse_known_args()

    if args.action == 'list':
        # Get all available devices and list them
        devices = System.PciUserspace().devices()

        # Add simulator device
        nvsim = SimpleNamespace(pci_slot='nvsim',
                                pci_vid=0xEDDA,
                                pci_did=0xE111,
                                driver='nvsim',
                                owner='usert ',
                                info_string='NVSim simulator')
        devices.insert(0, nvsim)

        if len(devices):
            print('PciUserspaceDevice devices:')
            fmt = '{:<16} {:>6}:{:<6} {:>12} {:>12}   {}'
            print(fmt.format('slot', 'vid', 'did', 'driver', 'owner', 'info'))

            for device in devices:
                print(fmt.format(device.pci_slot,
                                 device.pci_vid,
                                 device.pci_did,
                                 device.driver,
                                 device.owner,
                                 device.info_string))

            print()
        else:
            print('No devices found!')

    elif args.action == 'expose':
        parser.add_argument('pci_slot')
        parser.add_argument('user')
        args = parser.parse_args()

        # Must be root for exposing devices and changing permissions
        if os.geteuid() != 0:
            sys.exit('ERROR: Must be root to expose devices')

        # Get an interface object to the pci system and slot
        pci_sys = System.Pci()
        pci_dev = System.PciDevice(args.pci_slot)

        # Remove and rescan
        pci_dev.remove()
        pci_sys.rescan()

        # Make sure the device in the slot exists
        if not pci_dev.exists():
            sys.exit('Slot {} does not exist!'.format(args.pci_slot))

        # Expose it
        pci_dev.expose(args.user)

        print('SUCESS: {} is now usable by {} in userspace as {}'.format(
              args.pci_slot, args.user, pci_dev.exposed_device_path))

    elif args.action == 'reclaim':
        parser.add_argument('pci_slot')
        parser.add_argument('driver')
        args = parser.parse_args()

        # Must be root for reclaiming devices and changing drivers
        if os.geteuid() != 0:
            sys.exit('ERROR: Must be root to reclaim devices')

        # Get an interface object to the pci slot and reclaim it
        pci_dev = System.PciDevice(args.pci_slot)
        pci_dev.reclaim(args.driver)
