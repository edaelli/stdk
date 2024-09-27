import copy
from nvsim.simulators import NVSimInterface


class PCIeRegChangeHandler:

    def __init__(self, device):

        if NVSimInterface not in device.__class__.__bases__:
            raise Exception(
                'Device must implement the NVSimInterface to be used by PCIeRegChangeHandler!')

        self.device = device
        self.pcie_regs = device.pcie_regs
        self.last_pcie_regs = copy.deepcopy(self.pcie_regs)

    def registers_changed(self, old_pcie_regs, new_pcie_regs):
        changed = False

        data_old = bytearray(old_pcie_regs)
        data_new = bytearray(new_pcie_regs)

        # Check every byte for a change
        for i in range(len(data_new)):

            # Did this byte change?
            if data_old[i] != data_new[i]:

                # Something changed!
                changed = True

                # Break since we found a change
                break

        return changed

    def __call__(self):

        # Has anything changed?
        changed = self.registers_changed(self.last_pcie_regs, self.pcie_regs)

        if changed is True:
            # Call nvsim_pcie_regs_changed simulator interface

            # Pass in old and new regs, let the simulator handle if
            #  they want to, and check again. If they handled all changes
            #  we are done, otherwise we should go check what is left
            self.device.nvsim_pcie_regs_changed(self.last_pcie_regs, self.pcie_regs)

            # Check again after the interface was called
            changed = self.registers_changed(self.last_pcie_regs, self.pcie_regs)

        # Save off the last time we checked, this callable should be called
        #  by the caller with a threading lock so the registers don't move
        #  under us
        self.last_pcie_regs = copy.deepcopy(self.pcie_regs)
