from nvsim.cmd_handlers import NvsimCommandHandlers
from lone.nvme.spec.commands.status_codes import status_codes
from lone.nvme.spec.prp import PRP
from lone.nvme.spec.commands.nvm.read import Read
from lone.nvme.spec.commands.nvm.write import Write

import logging
logger = logging.getLogger('nvsim_nvm')


class NVSimWrite:
    OPC = Write().OPC

    def __call__(self, nvsim_state, command, sq, cq):
        wr_cmd = Write.from_buffer(command)
        ns = nvsim_state.namespaces[wr_cmd.NSID]

        logger.debug('Write SLBA: 0x{:x} NLB: {} NSID: {}'.format(
            wr_cmd.SLBA, wr_cmd.NLB, wr_cmd.NSID))

        # Is this in range for the ns's LBA?
        if (wr_cmd.SLBA + wr_cmd.NLB + 1) > ns.num_lbas:
            status_code = status_codes['LBA Out of Range']

        else:
            # Make a PRP object from the command's information
            prp = PRP(None, (wr_cmd.NLB + 1) * ns.block_size, nvsim_state.mps, None,
                      'NVSimWrite', alloc=False).from_address(wr_cmd.DPTR.PRP.PRP1,
                                                              wr_cmd.DPTR.PRP.PRP2)

            # Write data to nvsim's storage
            ns.write(wr_cmd.SLBA, wr_cmd.NLB + 1, prp)

            status_code = status_codes['Successful Completion']

        # Complete the command
        self.complete(command, sq, cq, status_code)


class NVSimRead:
    OPC = Read().OPC

    def __call__(self, nvsim_state, command, sq, cq):
        rd_cmd = Read.from_buffer(command)
        ns = nvsim_state.namespaces[rd_cmd.NSID]

        logger.debug('Read SLBA: 0x{:x} NLB: {} NSID: {}'.format(
            rd_cmd.SLBA, rd_cmd.NLB, rd_cmd.NSID))

        # Is this in range for the ns's LBA?
        if (rd_cmd.SLBA + rd_cmd.NLB + 1) > ns.num_lbas:
            status_code = status_codes['LBA Out of Range']

        else:

            # Make a PRP object from the command's information
            prp = PRP(None, (rd_cmd.NLB + 1) * ns.block_size, nvsim_state.mps, None,
                      'NVSimRead', alloc=False).from_address(rd_cmd.DPTR.PRP.PRP1,
                                                             rd_cmd.DPTR.PRP.PRP2)

            # Read data from nvsim's storage
            ns.read(rd_cmd.SLBA, rd_cmd.NLB + 1, prp)

            status_code = status_codes['Successful Completion']

        # Complete the command
        self.complete(command, sq, cq, status_code)


# Create our admin command handlers object. Can you do this with introspection??
nvm_handlers = NvsimCommandHandlers()
for handler in [
    NVSimWrite,
    NVSimRead,
]:
    nvm_handlers.register(handler)
