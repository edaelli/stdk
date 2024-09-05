import sys
import argparse
import ctypes

# lone imports
from lone.nvme.device import NVMeDevice


if not (sys.version_info.major == 3 and sys.version_info.minor >= 11):
    print('Python 3.11 is required to run this script (uses os.eventfd)')
    sys.exit(-1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pci_slot', type=str)
    args = parser.parse_args()

    nvme_device = NVMeDevice(args.pci_slot)

    # Disable
    nvme_device.cc_disable()

    # Get the MSI-X capability
    msix_cap = [cap for cap in nvme_device.pcie_regs.capabilities if
                cap._cap_id_ is nvme_device.pcie_regs.PCICapMSIX._cap_id_][0]

    msix_tbir = msix_cap.MTAB.TBIR
    msix_table_offset = msix_cap.MTAB.TO << 3
    msix_table_size = msix_cap.MXC.TS + 1
    msix_pir = msix_cap.MPBA.PBIR
    msix_pba_offset = msix_cap.MPBA.PBAO << 3
    msix_pba_num_qwords = msix_table_size // 64

    assert msix_tbir == 0, 'Need something different for vectors NOT in BAR0/1'
    assert msix_pir == 0, 'Need something different for vectors NOT in BAR0/1'

    print('MSI-X MXE: 0x{:x} FM: 0x{:x}'.format(msix_cap.MXC.MXE, msix_cap.MXC.FM))
    print('MSI-X Table Size: {} Offset: 0x{:x}'.format(msix_table_size, msix_table_offset))
    print('MSI-X PBA Offset: 0x{:x}'.format(msix_pba_offset))

    class MSIXTableEntry(ctypes.Structure):
        _fields_ = [
            ('ADDR_LO', ctypes.c_uint32),
            ('ADDR_HI', ctypes.c_uint32),
            ('DATA', ctypes.c_uint32),
            ('V_CTRL', ctypes.c_uint32),
        ]

    msix_table = (MSIXTableEntry * msix_table_size).from_address(
        ctypes.addressof(nvme_device.nvme_regs.CAP) + msix_table_offset)

    for i, table_entry in enumerate(msix_table[:16]):
        print('Table Entry {:04}: ADDR: 0x{:08x}{:08x} DATA: 0x{:08x}, V_CTRL: 0x{:08x}'.format(
            i, table_entry.ADDR_HI, table_entry.ADDR_LO, table_entry.DATA, table_entry.V_CTRL))

    msix_pba = (ctypes.c_uint64 * (msix_pba_num_qwords)).from_address(
        ctypes.addressof(nvme_device.nvme_regs) + (msix_pba_offset))
    for i, pba_entry in enumerate(msix_pba):
        print('PBA Entry {}: 0x{:016x}'.format(i, pba_entry))

    nvme_device.init_admin_queues(asq_entries=16, acq_entries=16)
    nvme_device.cc_enable()

    nvme_device.init_msix_interrupts(2, 0)
    nvme_device.create_io_queues(1, 256)

    print('MSI-X MXE: 0x{:x} FM: 0x{:x}'.format(msix_cap.MXC.MXE, msix_cap.MXC.FM))
    print('MSI-X Table Size: {} Offset: 0x{:x}'.format(msix_table_size, msix_table_offset))
    print('MSI-X PBA Offset: 0x{:x}'.format(msix_pba_offset))
    for i, table_entry in enumerate(msix_table[:16]):
        print('Table Entry {:04}: ADDR: 0x{:08x}{:08x} DATA: 0x{:08x}, V_CTRL: 0x{:08x}'.format(
            i, table_entry.ADDR_HI, table_entry.ADDR_LO, table_entry.DATA, table_entry.V_CTRL))

    from lone.nvme.spec.commands.nvm.read import Read
    from lone.nvme.spec.prp import PRP
    from lone.system import DMADirection

    # Create and map PRP for the read
    read_prp = PRP(nvme_device.mem_mgr, 4096, nvme_device.mps,
                   DMADirection.DEVICE_TO_HOST, 'read_prp')

    # Create command, set PRP
    read_cmd = Read(NSID=1, NLB=0)
    read_cmd.DPTR.PRP.PRP1 = read_prp.prp1
    read_cmd.DPTR.PRP.PRP2 = read_prp.prp2
    read_cmd.SLBA = 0

    nvme_device.start_cmd(read_cmd, 1, 1)
    read_cmd.complete = False
    while read_cmd.complete is False:
        nvme_device.process_completions()

    assert read_cmd.complete is True
    assert read_cmd.cqe.SF.SC == 0


if __name__ == '__main__':
    sys.exit(main())
