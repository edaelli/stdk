''' Test module for examples on how to use lone
'''
import pytest


def test_example_config(lone_config):
    # The lone_config fixture is the dictionary representation
    #   of the yaml file passed into pytest with the --config
    #   option.
    #   For example:
    #   pytest --config /tmp/example.yml
    #   example.yml contains
    #   dut:
    #      pci_slot: nvsim
    #   Then lone_config will look like:
    #   lone_config = {'dut': {'pci_slot': 'nvsim'}}
    assert 'dut' in lone_config.keys()
    assert 'pci_slot' in lone_config['dut'].keys()


def test_nvme_device_raw(nvme_device_raw):
    # The nvme_device_raw fixture is the bare nvme device
    #  which can be accessed by PCIe and NVMe registers, and
    #  has not had anything done to it. For example, it is in
    #  an unknown state, no queues have been created, etc.
    #  This allows for testing of very low level operations
    #  like creating queues, etc.
    #  The nvme_device_raw is configured by the information
    #  in the lone config file passed in as the --config parameter

    # Check the registers are of the right type
    from lone.nvme.spec.registers.pcie_regs import PCIeRegisters
    assert issubclass(type(nvme_device_raw.pcie_regs), PCIeRegisters)

    from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect
    assert type(nvme_device_raw.nvme_regs) is NVMeRegistersDirect

    # Check a couple of values in pcie and nvme for demonstration

    # Make sure that PCIe VID and DID are not zero
    assert nvme_device_raw.pcie_regs.ID.VID != 0
    assert nvme_device_raw.pcie_regs.ID.DID != 0

    # Make sure that NVMe VS is not zero
    assert nvme_device_raw.nvme_regs.VS.MJR != 0
    assert nvme_device_raw.nvme_regs.VS.MNR != 0

    # Disable the device, setup admin queues, enable it
    nvme_device_raw.cc_disable()
    nvme_device_raw.init_admin_queues(asq_entries=64, acq_entries=256)
    nvme_device_raw.cc_enable()

    # Make sure it is ready after enable
    assert nvme_device_raw.nvme_regs.CSTS.RDY == 1

    # At this point the device is ready to take in ADMIN commands
    # Let's try an Identify (CNS=1 Controller)

    # First create the command object
    from lone.nvme.spec.commands.admin.identify import IdentifyController
    id_ctrl_cmd = IdentifyController()

    # Allocate memory for that command and check that a PRP object was
    #  created for it
    nvme_device_raw.alloc(id_ctrl_cmd)
    from lone.nvme.spec.prp import PRP
    assert type(id_ctrl_cmd.prp) is PRP, 'Invalid PRP for id_ctrl_cmd'

    # Then send it to the device, and wait for a completion
    nvme_device_raw.sync_cmd(id_ctrl_cmd)

    # Getting here means that sync_cmd sent the command to the device on the
    #  admin submission queue, then found a completion in the admin completion
    #  queue for it. sync_cmd can (and does by default) check status on the
    #  completion, but let's do it here to demonstrate
    # If the command failed, cqe.SF.SC would be non-zero
    assert id_ctrl_cmd.cqe.SF.SC == 0x0, 'Identify command failed with SC=0x{:02x}'.format(
                                         id_ctrl_cmd.cqe.SF.SC)

    # Ok, the identify controller command was sucessful, this means we can look at the
    #   returned data
    assert id_ctrl_cmd.data_in.MN != '', 'Empty Model Number'
    assert id_ctrl_cmd.data_in.SN != '', 'Empty Serial Number'
    assert id_ctrl_cmd.data_in.FR != '', 'Empty Firmware Revision'


@pytest.mark.parametrize(
    'nvme_device',
    [{'asq_entries': 10, 'acq_entries': 20, 'num_io_queues': 10, 'io_queue_entries': 10}],
    indirect=True)
def test_nvme_device(nvme_device, lone_config):
    # The nvme_device fixture is similar to the nvme_device_raw
    #  fixture, except it has initialized admin and io queues on
    #  the device before the test starts.
    #  You can set parameters to how many queues, slots, etc by
    #  decorating this function as shown above.

    # Check that the initialization matches the setup above
    assert nvme_device.nvme_regs.AQA.ASQS == (10 - 1)  # Zero based
    assert nvme_device.nvme_regs.AQA.ACQS == (20 - 1)  # Zero based
    assert len(nvme_device.queue_mgr.nvme_queues) == 1 + 10  # Admin + NVM queues

    # Check that the device is enabled
    assert nvme_device.nvme_regs.CSTS.RDY == 1

    # Ok, now we can demonstrate how to send a NVM commands

    #  First step is to import the commands we need, and PRP and DMADirection objects
    from lone.nvme.spec.commands.nvm.write import Write
    from lone.nvme.spec.commands.nvm.read import Read
    from lone.nvme.spec.prp import PRP
    from lone.system import DMADirection

    # Next we need to get information from the device so we know how to properly
    #  create NVM commands. We do that by sending a couple of identify commands to the
    #  device. The NVMeDeviceIdentifyData object does that for us (see details in there)
    from lone.nvme.device.identify import NVMeDeviceIdentifyData
    id_data = NVMeDeviceIdentifyData(nvme_device)

    # Now that we know the existing namespaces in the device, make sure the caller asked
    #   us to access a valid namespace
    nsid = lone_config['dut']['namespaces'][0]['nsid']
    ns = id_data.namespaces[nsid]
    assert ns is not None, f'Invalid Namespace: {nsid} for device'

    # Calculate some other values we need to send writes/reads
    xfer_len = 4096
    slba = 0
    ns_block_size = ns.lba_ds_bytes
    num_blocks = xfer_len // ns_block_size
    nlb = num_blocks - 1

    # Next allocate memory and format a PRP for the write/read we will send. Note that the
    #  memory is allocated with a direction parameter. This allow us to setup the OS's
    #  IOMMU with that information and it will only allow that direction to happen on the bus
    write_prp = PRP(nvme_device.mem_mgr,
                    xfer_len,
                    nvme_device.mps,
                    DMADirection.HOST_TO_DEVICE,
                    'test_example write',
                    alloc=True)

    # Set the data in the PRP's buffers to a known pattern so we can check later
    write_prp.set_data_buffer(bytes([0xED] * xfer_len))

    # Create a write command and set it up
    write_cmd = Write(SLBA=slba, NLB=nlb, NSID=nsid)
    write_cmd.DPTR.PRP.PRP1 = write_prp.prp1
    write_cmd.DPTR.PRP.PRP2 = write_prp.prp2

    # Send the command, wait for completion, check status
    nvme_device.sync_cmd(write_cmd)

    # Now create the PRP for a read command
    read_prp = PRP(nvme_device.mem_mgr,
                   xfer_len,
                   nvme_device.mps,
                   DMADirection.DEVICE_TO_HOST,
                   'test_example read',
                   alloc=True)

    # Create a read command and set it up
    read_cmd = Read(SLBA=slba, NLB=nlb, NSID=nsid)
    read_cmd.DPTR.PRP.PRP1 = read_prp.prp1
    read_cmd.DPTR.PRP.PRP2 = read_prp.prp2

    # Send the command, wait for completion, check status
    nvme_device.sync_cmd(read_cmd)

    # At this point the command completed, we can look at the read data and
    #   compare it with the written data
    assert read_prp.get_data_buffer() == write_prp.get_data_buffer()

    # We are done! Now we can disable the device and clean up whatever memory we used
    nvme_device.cc_disable()

    # Free all memory we used (both PRPs above)
    nvme_device.mem_mgr.free_all()
    assert len(nvme_device.mem_mgr.allocated_mem_list()) == 0

    # Make sure the device disabled correctly
    assert nvme_device.nvme_regs.CSTS.RDY == 0
