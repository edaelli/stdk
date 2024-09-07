from lone.nvme.spec.structures import Generic

import logging
logger = logging.getLogger('prp')


class NVMeStatusCodeException(Exception):
    def __init__(self, code):
        self.code = code
        message = 'SF.SC: 0x{:02x} "{}" cmd: {}'.format(
            code.value, code.name, code.cmd_type.__name__)
        super().__init__(message)


class NVMeStatusCode:
    def __init__(self, value, name, cmd_type=Generic):
        self.value = value
        self.name = name
        self.cmd_type = cmd_type

    def __int__(self):
        return int(self.value)

    def __str__(self):
        return self.name

    @property
    def failure(self):
        return False if self.value == 0 else True

    @property
    def success(self):
        return not self.failure


class NVMeStatusCodes:
    def __init__(self):
        self.__codes = {}

        # All all generic status codes from the base spec
        self.add(NVMeStatusCode(0x00, 'Successful Completion')),
        self.add(NVMeStatusCode(0x01, 'Invalid Command Opcode')),
        self.add(NVMeStatusCode(0x02, 'Invalid Field in Command')),
        self.add(NVMeStatusCode(0x03, 'Command ID Conflict')),
        self.add(NVMeStatusCode(0x04, 'Data Transfer Error')),
        self.add(NVMeStatusCode(0x05, 'Commands Aborted due to Power Loss Notification')),
        self.add(NVMeStatusCode(0x06, 'Internal Error')),
        self.add(NVMeStatusCode(0x07, 'Command Abort Requested')),
        self.add(NVMeStatusCode(0x08, 'Command Aborted due to SQ Deletion')),
        self.add(NVMeStatusCode(0x09, 'Command Aborted due to Failed Fused Command')),
        self.add(NVMeStatusCode(0x0A, 'Command Aborted due to Missing Fused Command')),
        self.add(NVMeStatusCode(0x0B, 'Invalid Namespace or Format')),
        self.add(NVMeStatusCode(0x0C, 'Command Sequence Error')),
        self.add(NVMeStatusCode(0x0D, 'Invalid SGL Segment Descriptor')),
        self.add(NVMeStatusCode(0x0E, 'Invalid Number of SGL Descriptors')),
        self.add(NVMeStatusCode(0x0F, 'Data SGL Length Invalid')),
        self.add(NVMeStatusCode(0x10, 'Metadata SGL Length Invalid')),
        self.add(NVMeStatusCode(0x11, 'SGL Descriptor Type Invalid')),
        self.add(NVMeStatusCode(0x12, 'Invalid Use of Controller Memory Buffer')),
        self.add(NVMeStatusCode(0x13, 'PRP Offset Invalid')),
        self.add(NVMeStatusCode(0x14, 'Atomic Write Unit Exceeded')),
        self.add(NVMeStatusCode(0x15, 'Operation Denied')),
        self.add(NVMeStatusCode(0x16, 'SGL Offset Invalid')),
        #                       0x17 Reserved
        self.add(NVMeStatusCode(0x18, 'Host Identifier Inconsistent Format')),
        self.add(NVMeStatusCode(0x19, 'Keep Alive Timer Expired')),
        self.add(NVMeStatusCode(0x1A, 'Keep Alive Timeout Invalid')),
        self.add(NVMeStatusCode(0x1B, 'Command Aborted due to Preempt and Abort')),
        self.add(NVMeStatusCode(0x1C, 'Sanitize Failed')),
        self.add(NVMeStatusCode(0x1D, 'Sanitize In Progress')),
        self.add(NVMeStatusCode(0x1E, 'SGL Data Block Granularity Invalid')),
        self.add(NVMeStatusCode(0x1F, 'Command Not Supported for Queue in CMB')),
        self.add(NVMeStatusCode(0x20, 'Namespace is Write Protected')),
        self.add(NVMeStatusCode(0x21, 'Command Interrupted')),
        self.add(NVMeStatusCode(0x22, 'Transient Transport Error')),
        self.add(NVMeStatusCode(0x23, 'Command Prohibited by Command and Feature Lockdown')),
        self.add(NVMeStatusCode(0x24, 'Admin Command Media Not Ready')),
        #                       0x25 to 0x7F Reserved
        self.add(NVMeStatusCode(0x80, 'LBA Out of Range')),
        self.add(NVMeStatusCode(0x81, 'Capacity Exceeded')),
        self.add(NVMeStatusCode(0x82, 'Namespace Not Ready')),
        self.add(NVMeStatusCode(0x83, 'Reservation Conflict')),
        self.add(NVMeStatusCode(0x84, 'Format In Progress')),
        self.add(NVMeStatusCode(0x85, 'Invalid Value Size')),
        self.add(NVMeStatusCode(0x86, 'Invalid Key Size')),
        self.add(NVMeStatusCode(0x87, 'KV Key Does Not Exist')),
        self.add(NVMeStatusCode(0x88, 'Unrecovered Error')),
        self.add(NVMeStatusCode(0x89, 'Key Exists')),

    def add(self, codes):
        if type(codes) is not list:
            codes = [codes]

        for code in codes:
            self.__codes[(code.value, code.cmd_type)] = code

    def get(self, command):

        # Look for the status in generic if SCT = 0
        if command.cqe.SF.SCT == 0:
            c = [v for k, v in self.__codes.items() if (
                v.value == command.cqe.SF.SC and v.cmd_type == Generic)]

        # Then command specific if SCT != 0
        else:
            c = [v for k, v in self.__codes.items() if (
                v.value == command.cqe.SF.SC and (
                    v.cmd_type == type(command) or v.cmd_type in type(command).__bases__))]

        if len(c) == 0:
            return NVMeStatusCode(command.cqe.SF.SC, 'Unknown', type(command))
        else:
            return c[0]

    def check(self, command, raise_exc=True):

        # Fast exit if the command was successful
        if command.cqe.SF.SCT == 0 and command.cqe.SF.SC == 0:
            return
        else:
            code = self.get(command)
            if raise_exc:
                raise NVMeStatusCodeException(code)

    def __getitem__(self, key):

        if type(key) is tuple:
            key, cmd_type = key
        else:
            key, cmd_type = 0, Generic

        if type(key) is int:
            return self.__codes[(key, cmd_type)]
        elif type(key) is str:
            c = [v for k, v in self.__codes.items() if v.name == key and v.cmd_type == cmd_type]
            if len(c):
                return c[0]
        else:
            assert False, 'Invalid type {}'.format(type(key))


# Expose it to other users
status_codes = NVMeStatusCodes()
