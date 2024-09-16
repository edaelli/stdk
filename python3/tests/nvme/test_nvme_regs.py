from lone.nvme.spec.registers.nvme_regs import NVMeRegistersDirect


def test_nvme_regs():
    regs = NVMeRegistersDirect()
    regs.log()
