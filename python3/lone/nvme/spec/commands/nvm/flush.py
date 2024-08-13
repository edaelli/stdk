import ctypes
from lone.nvme.spec.structures import NVMCommand


class Flush(NVMCommand):
    _pack_ = 1
    _fields_ = [
        ('DW10', ctypes.c_uint32),
        ('DW11', ctypes.c_uint32),
        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
        ('DW14', ctypes.c_uint32),
        ('DW15', ctypes.c_uint32),
    ]

    _defaults_ = {
        'OPC': 0x00
    }
