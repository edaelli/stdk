import ctypes
import inspect

from lone.util.struct_tools import StructFieldsIterator
from lone.util.hexdump import hexdump
from lone.system import DMADirection

import logging
logger = logging.getLogger('nvme_struct')


class DataDumper:

    def dump(self, prefix=None, postfix=None, dump_hex=False, dump_limit_bytes=None, # noqa: C901
             printer=logger.debug, noprint=['RSVD', 'TBD'], oneline=True):
        base_name = self.__class__.__name__
        attributes = set()

        for t in inspect.getmro(type(self)):
            if t.__name__ not in ['Structure', '_CData', 'DataDumper', 'object']:

                # Print all the data in the structure using the StructFieldsIterator
                for field, value in StructFieldsIterator(t.from_address(ctypes.addressof(self))):
                    fmt = '{} {}'

                    # Do not print if the field includes any of the strings in noprint
                    if not any(f in field for f in noprint):
                        field_attr = '.'.join(field.split('.')[1:])
                        if type(value) is int:
                            fmt = '{}=0x{:x}'
                        else:
                            fmt = '{}={}'

                        attributes.add((fmt, field_attr, value))

        attr_strings = sorted(
            [(fmt.format(f, v)) for fmt, f, v in attributes], key=lambda x: (x[0], x[1]))

        print_string = ''
        if oneline:
            if prefix:
                print_string = prefix + ' '

            print_string += base_name + ': '

            for s in attr_strings:
                print_string += s + ', '
            print_string = print_string[:-2]

            if postfix:
                print_string += ' ' + postfix
        else:
            printer(base_name)
            for line in attr_strings:
                printer(line + ' ')

        printer(print_string)

        if dump_hex:
            printer(base_name + ' Hexdump:')
            for line in hexdump(self, max_bytes=dump_limit_bytes):
                printer(line)


class DptrPrp(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('PRP1', ctypes.c_uint64),
        ('PRP2', ctypes.c_uint64),
    ]


class DptrSgl(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('SGL1', ctypes.c_uint64 * 2),
    ]


class Dptr(ctypes.Union):
    _fields_ = [
        ('PRP', DptrPrp),
        ('SGL', DptrSgl),
    ]


class SQECommon(ctypes.Structure, DataDumper):
    _pack_ = 1
    _fields_ = [
        ('OPC', ctypes.c_uint32, 8),
        ('FUSE', ctypes.c_uint32, 2),
        ('RSVD_0', ctypes.c_uint32, 4),
        ('PSDT', ctypes.c_uint32, 2),
        ('CID', ctypes.c_uint32, 16),

        ('NSID', ctypes.c_uint32),

        ('DW2', ctypes.c_uint32),
        ('DW3', ctypes.c_uint32),

        ('MPTR', ctypes.c_uint64),

        ('DPTR', Dptr),
    ]

    def __init__(self, **kwargs):

        self.initialized = False

        # Initialize defaults
        if hasattr(type(self), '_defaults_'):
            values = type(self)._defaults_.copy()
            for k, v in values.items():
                values[k] = v
            super().__init__(**values)
        super().__init__(**kwargs)

        # Add all the variables we want to be able to use here

        # Create data in/out object if the command has one

        # PRPs get set by the device, but make them none for consistency
        self.prp = None

        if hasattr(self, 'data_in_type') and self.data_in_type is not None:
            # Create Data in type
            self.data_in = self.data_in_type()
        else:
            self.data_in = None

        if hasattr(self, 'data_out_type') and self.data_out_type is not None:
            # Create Data out type
            self.data_out = self.data_out_type()
        else:
            self.data_out = None

        # Add variables to track start/end times for the command
        self.start_time_ns = 0
        self.end_time_ns = 0

        # Add variables to keep track of what sq the command was sent in
        #  and what cq we should expect a reply on
        self.sq = None
        self.cq = None

        # Once the command completes, the whole cqe is added to it
        self.cqe = CQE()
        self.complete = False
        self.posted = False

        # Context variable so users can keep track of non-standard things
        self.context = None

        # Mark as initialized. After this point no more variables can be added
        self.initialized = True
        self.internal_mem = False

    def __len__(self):
        return ctypes.sizeof(self)

    @property
    def time_ns(self):
        return self.end_time_ns - self.start_time_ns

    @property
    def time_us(self):
        return self.time_ns / 1000

    @property
    def time_ms(self):
        return self.time_us / 1000

    @property
    def time_s(self):
        return self.time_us / 1000000

    def free_prps(self):
        if self.prp is not None:
            self.prp.free_all_memory()


class DataOutCommon(ctypes.Structure, DataDumper):
    _pack_ = 1

    def __len__(self):
        return ctypes.sizeof(self)


class DataInCommon(ctypes.Structure, DataDumper):
    _pack_ = 1

    def __len__(self):
        return ctypes.sizeof(self)


class Generic(SQECommon):
    _fields_ = [
        ('DW10', ctypes.c_uint32),
        ('DW11', ctypes.c_uint32),
        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
        ('DW14', ctypes.c_uint32),
        ('DW15', ctypes.c_uint32),
    ]


class ADMINCommand(SQECommon):
    cmdset_admin = True
    cmdset_nvm = False


class NVMCommand(SQECommon):
    cmdset_admin = False
    cmdset_nvm = True


class CQE(ctypes.Structure, DataDumper):

    class Sf(ctypes.Structure):
        _pack_ = 1
        _fields_ = [
            ('P', ctypes.c_uint16, 1),
            ('SC', ctypes.c_uint16, 8),
            ('SCT', ctypes.c_uint16, 3),
            ('CRD', ctypes.c_uint16, 2),
            ('M', ctypes.c_uint16, 1),
            ('DNR', ctypes.c_uint16, 1),
        ]

    _pack_ = 1
    _fields_ = [
        ('CMD_SPEC', ctypes.c_uint32),
        ('RSVD_0', ctypes.c_uint32),
        ('SQHD', ctypes.c_uint32, 16),
        ('SQID', ctypes.c_uint32, 16),
        ('CID', ctypes.c_uint16),
        ('SF', Sf),
    ]

    # It is kinda weird how the spec defines
    #   the P bit. It is not part of the SF structure
    #   but it is a 1 bit in the middle of a 32 bit field.
    #   Rather than trying to make a structure that fits that,
    #   just "cheat" here and use __getattr__/__setattr__ when
    #   a caller accesses it.
    def __getattr__(self, name):
        if name == 'P':
            return self.SF.P
        raise AttributeError('{} not in {}'.format(name, self.__class__.__name__))

    def __setattr__(self, name, value):
        if name == 'P':
            self.SF.P = value
        else:
            object.__setattr__(self, name, value)

    def __len__(self):
        return ctypes.sizeof(self)
