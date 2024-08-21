import ctypes
import enum

from lone.nvme.spec.structures import ADMINCommand
from lone.nvme.spec.commands.status_codes import NVMeStatusCode, status_codes


class Sanitize(ADMINCommand):
    class SanAct(enum.IntEnum):
        RESERVED = 0
        EXIT_FAILURE_MODE = 1
        START_BLOCK_SANITIZE = 2
        START_OVERWRITE_SANITIZE = 3
        START_CRYPTO_ERASE_SANITIZE = 4

    _pack_ = 1
    _fields_ = [
        ('SANACT', ctypes.c_uint32, 3),
        ('AUSE', ctypes.c_uint32, 1),
        ('OWPASS', ctypes.c_uint32, 4),
        ('OIPBP', ctypes.c_uint32, 1),
        ('NODEALOC', ctypes.c_uint32, 1),
        ('RSVD', ctypes.c_uint32, 22),

        ('OVRPAT', ctypes.c_uint32),

        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
        ('DW14', ctypes.c_uint32),
        ('DW15', ctypes.c_uint32),
    ]

    _defaults_ = {
        'OPC': 0x84
    }


status_codes.add([
    NVMeStatusCode(0x0B, 'Firmware Activation Requires Conventional Reset', Sanitize),
    NVMeStatusCode(0x10, 'Firmware Activation Requires NVM Subsystem Reset', Sanitize),
    NVMeStatusCode(0x11, 'Firmware Activation Requires Controller Level Reset', Sanitize),
    NVMeStatusCode(0x23, 'Sanitize Prohibited While Persistent Memory Region is Enabled', Sanitize),
])
