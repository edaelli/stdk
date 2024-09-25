import copy

from lone.util.logging import log_init
logger = log_init()


class PCIeRegChangeHandler:

    def __init__(self, nvsim_state):
        self.nvsim_state = nvsim_state
        self.pcie_regs_data = bytearray(self.nvsim_state.pcie_regs)
        self.pcie_regs_old = copy.deepcopy(self.nvsim_state.pcie_regs)

    def __call__(self):
        # Make a copy right away to minimize things moving under us
        pcie_regs_data_old = self.pcie_regs_data
        pcie_regs_data_new = bytearray(self.nvsim_state.pcie_regs)

        # If old != new go check if we need to do anything
        if pcie_regs_data_old != pcie_regs_data_new:

            changed = False
            for i in range(len(pcie_regs_data_new)):
                if pcie_regs_data_old[i] != pcie_regs_data_new[i]:
                    # Mark that something changed!
                    changed = True

            if changed is True:

                # Did we get an FLR request?
                try:
                    pcie_cap_new = [cap for cap in self.nvsim_state.pcie_regs.capabilities if
                                    cap._cap_id_ is
                                    self.nvsim_state.pcie_regs.PCICapExpress._cap_id_][0]

                    pcie_cap_old = [cap for cap in self.pcie_regs_old.capabilities if
                                    cap._cap_id_ is
                                    self.pcie_regs_old.PCICapExpress._cap_id_][0]

                    if pcie_cap_old.PXDC.IFLR == 0 and pcie_cap_new.PXDC.IFLR == 1:
                        self.nvsim_state.initialize()
                        logger.debug("IFLR detected!")
                except IndexError:
                    # Means the simulator doesnt have a PCICapExpress capability
                    pass

        # Save off the last time we checked
        self.pcie_regs_data = pcie_regs_data_new
        self.pcie_regs_old = copy.deepcopy(self.nvsim_state.pcie_regs)
