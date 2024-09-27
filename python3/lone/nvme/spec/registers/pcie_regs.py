import ctypes
import logging
from collections import namedtuple

from lone.util.struct_tools import StructFieldsIterator
from lone.nvme.spec.registers import RegsStructAccess


#   pci registers in various implementations.
PCIeAccessData = namedtuple('PCIeAccessData', 'get_func set_func')


def pcie_reg_struct_factory(access_data):

    class NVMePCIeRegisters(ctypes.Structure):
        _access_data_ = access_data

        class Id(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('VID', ctypes.c_uint32, 16),
                ('DID', ctypes.c_uint32, 16),
            ]
            _access_ = access_data
            _base_offset_ = 0x00

        class Cmd(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('IOSE', ctypes.c_uint16, 1),
                ('MSE', ctypes.c_uint16, 1),
                ('BME', ctypes.c_uint16, 1),
                ('SCE', ctypes.c_uint16, 1),
                ('MWIE', ctypes.c_uint16, 1),
                ('VGA', ctypes.c_uint16, 1),
                ('PEE', ctypes.c_uint16, 1),
                ('RSVD_0', ctypes.c_uint16, 1),
                ('SEE', ctypes.c_uint16, 1),
                ('FBE', ctypes.c_uint16, 1),
                ('ID', ctypes.c_uint16, 1),
                ('RSVD_1', ctypes.c_uint16, 5),
            ]
            _access_ = access_data
            _base_offset_ = 0x04

        class Sts(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('RSVD_0', ctypes.c_uint16, 3),
                ('IS', ctypes.c_uint16, 1),
                ('CL', ctypes.c_uint16, 1),
                ('C66', ctypes.c_uint16, 1),
                ('RSVD_1', ctypes.c_uint16, 1),
                ('FBC', ctypes.c_uint16, 1),
                ('DPD', ctypes.c_uint16, 1),
                ('DEVT', ctypes.c_uint16, 2),
                ('STA', ctypes.c_uint16, 1),
                ('RTA', ctypes.c_uint16, 1),
                ('RMA', ctypes.c_uint16, 1),
                ('SSE', ctypes.c_uint16, 1),
                ('DPE', ctypes.c_uint16, 1),
            ]
            _access_ = access_data
            _base_offset_ = 0x06

        class Rid(RegsStructAccess):
            _pack = 1
            _fields_ = [
                ('RID', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x08

        class Cc(RegsStructAccess):
            _pack = 1
            _fields_ = [
                ('PI', ctypes.c_uint8),
                ('SCC', ctypes.c_uint8),
                ('BCC', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x09

        class Cls(RegsStructAccess):
            _pack = 1
            _fields_ = [
                ('CLS', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x0C

        class Mlt(RegsStructAccess):
            _pack = 1
            _fields_ = [
                ('MLT', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x0D

        class Htype(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('HL', ctypes.c_uint8, 7),
                ('MFD', ctypes.c_uint8, 1),
            ]
            _access_ = access_data
            _base_offset_ = 0x0E

        class Bist(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('CC', ctypes.c_uint8, 4),
                ('RSVD_1', ctypes.c_uint8, 2),
                ('SB', ctypes.c_uint8, 1),
                ('BC', ctypes.c_uint8, 1),
            ]
            _access_ = access_data
            _base_offset_ = 0x0F

        class Bar0(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('RTE', ctypes.c_uint32, 1),
                ('TP', ctypes.c_uint32, 2),
                ('PF', ctypes.c_uint32, 1),
                ('RSVD_1', ctypes.c_uint32, 10),
                ('BA', ctypes.c_uint32, 18),
            ]
            _access_ = access_data
            _base_offset_ = 0x10

        class Bar1(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('BA', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = 0x14

        class Bar2(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('RTE', ctypes.c_uint32, 1),
                ('RSVD_1', ctypes.c_uint32, 13),
                ('BA', ctypes.c_uint32, 18),
            ]
            _access_ = access_data
            _base_offset_ = 0x18

        class Bar3(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('VU', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = 0x1C

        class Bar4(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('VU', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = 0x20

        class Bar5(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('VU', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = 0x24

        class Ccptr(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('NOT_SUPPORTED', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = 0x28

        class Ss(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('SSVID', ctypes.c_uint16),
                ('SSID', ctypes.c_uint16),
            ]
            _access_ = access_data
            _base_offset_ = 0x2C

        class Erom(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('RBA', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = 0x30

        class Cap(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('CP', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x34

        class Intr(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('ILINE', ctypes.c_uint8),
                ('IPIN', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x3C

        class Mgnt(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('GNT', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x3E

        class Mlat(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('LAT', ctypes.c_uint8),
            ]
            _access_ = access_data
            _base_offset_ = 0x3F

        class Caps(RegsStructAccess):
            _pack_ = 1
            _fields_ = [
                ('DATA', ctypes.c_uint8 * 4032),
            ]
            _access_ = access_data
            _base_offset_ = 0x40

        ''' PCIe registers from the NVMe specification
        '''
        _pack_ = 1
        _fields_ = [
            ('ID', Id),
            ('CMD', Cmd),
            ('STS', Sts),
            ('RID', Rid),
            ('CC', Cc),
            ('CLS', Cls),
            ('MLT', Mlt),
            ('HTYPE', Htype),
            ('BIST', Bist),
            ('BAR0', Bar0),
            ('BAR1', Bar1),
            ('BAR2', Bar2),
            ('BAR3', Bar3),
            ('BAR4', Bar4),
            ('BAR5', Bar5),
            ('CCPTR', Ccptr),
            ('SS', Ss),
            ('EROM', Erom),
            ('CAP', Cap),
            ('RSVD_0', ctypes.c_uint8 * 5),
            ('RSVD_1', ctypes.c_uint16),
            ('INTR', Intr),
            ('MGNT', Mgnt),
            ('MLAT', Mlat),
            ('CAPS', Caps),
        ]
        _access_ = access_data
        _base_offset_ = 0x00

        class PCICapability(RegsStructAccess):
            def set_offsets(self, base_offset):
                self._base_offset_ = base_offset

        class PCICapabilityExt(RegsStructAccess):
            def set_offsets(self, base_offset):
                self._base_offset_ = base_offset

        class PCICapabilityGen(PCICapability):
            _cap_id_ = None
            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint8),
                ('NEXT_PTR', ctypes.c_uint8),
                ('CAP_REG', ctypes.c_uint16),
            ]
            _access_ = access_data
            _base_offset_ = None

        class PCICapPowerManagementInterface(PCICapability):
            _cap_id_ = 0x1

            class Pc(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('VS', ctypes.c_uint16, 3),
                    ('PMEC', ctypes.c_uint16, 1),
                    ('RSVD_0', ctypes.c_uint16, 1),
                    ('DSI', ctypes.c_uint16, 1),
                    ('AUXC', ctypes.c_uint16, 3),
                    ('D1S', ctypes.c_uint16, 1),
                    ('D2S', ctypes.c_uint16, 1),
                    ('PSUP', ctypes.c_uint16, 5),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pmcs(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('PS', ctypes.c_uint16, 2),
                    ('RSVD_0', ctypes.c_uint16, 1),
                    ('NSFRST', ctypes.c_uint16, 1),
                    ('RSVD_1', ctypes.c_uint16, 4),
                    ('PMEE', ctypes.c_uint16, 1),
                    ('DSE', ctypes.c_uint16, 4),
                    ('DSC', ctypes.c_uint16, 2),
                    ('PMES', ctypes.c_uint16, 1),
                ]
                _access_ = access_data
                _base_offset_ = None

            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint8),
                ('NEXT_PTR', ctypes.c_uint8),
                ('PC', Pc),
                ('PMCS', Pmcs),
            ]
            _access_ = access_data
            _base_offset_ = None

            def set_offsets(self, base_offset):
                self.Pc._base_offset_ = base_offset + 2
                self.Pmcs._base_offset_ = base_offset + 4

        class PCICapMSI(PCICapability):
            _cap_id_ = 0x05

            class Mc(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('MSIE', ctypes.c_uint16, 1),
                    ('MMC', ctypes.c_uint16, 3),
                    ('MME', ctypes.c_uint16, 3),
                    ('C64', ctypes.c_uint16, 1),
                    ('PVM', ctypes.c_uint16, 1),
                    ('RSVD_0', ctypes.c_uint16, 7),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Ma(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('RSVD_0', ctypes.c_uint32, 2),
                    ('ADDR', ctypes.c_uint32, 30),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Mua(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('UADDR', ctypes.c_uint32),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Md(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('DATA', ctypes.c_uint16),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Mmask(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('MASK', ctypes.c_uint32),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Mpend(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('PEND', ctypes.c_uint32),
                ]
                _access_ = access_data
                _base_offset_ = None

            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint8),
                ('NEXT_PTR', ctypes.c_uint8),
                ('MC', Mc),
                ('MA', Ma),
                ('MUA', Mua),
                ('MD', Md),
                ('MMASK', Mmask),
                ('MPEND', Mpend),
            ]
            _access_ = access_data
            _base_offset_ = None

            def set_offsets(self, base_offset):
                self.Mc._base_offset_ = base_offset + 2

        class PCICapMSIX(PCICapability):
            _cap_id_ = 0x11

            class Mxc(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('TS', ctypes.c_uint16, 11),
                    ('RSVD_0', ctypes.c_uint16, 3),
                    ('FM', ctypes.c_uint16, 1),
                    ('MXE', ctypes.c_uint16, 1),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Mtab(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('TBIR', ctypes.c_uint32, 3),
                    ('TO', ctypes.c_uint32, 29),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Mpba(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('PBIR', ctypes.c_uint32, 3),
                    ('PBAO', ctypes.c_uint32, 29),
                ]
                _access_ = access_data
                _base_offset_ = None

            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint8),
                ('NEXT_PTR', ctypes.c_uint8),
                ('MXC', Mxc),
                ('MTAB', Mtab),
                ('MPBA', Mpba),
            ]
            _access_ = access_data
            _base_offset_ = None

            def set_offsets(self, base_offset):
                self.Mxc._base_offset_ = base_offset + 2
                self.Mtab._base_offset_ = base_offset + 4
                self.Mpba._base_offset_ = base_offset + 8

        class PCICapExpress(PCICapability):
            _cap_id_ = 0x10

            class Pxcap(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('VER', ctypes.c_uint16, 4),
                    ('DPT', ctypes.c_uint16, 4),
                    ('SI', ctypes.c_uint16, 1),
                    ('IMN', ctypes.c_uint16, 5),
                    ('RSVD_0', ctypes.c_uint16, 2),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxdcap(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('MPS', ctypes.c_uint32, 3),
                    ('PFS', ctypes.c_uint32, 2),
                    ('ETFS', ctypes.c_uint32, 1),
                    ('L0SL', ctypes.c_uint32, 3),
                    ('L1L', ctypes.c_uint32, 3),
                    ('RSVD_0', ctypes.c_uint32, 3),
                    ('RER', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 2),
                    ('CSPLV', ctypes.c_uint32, 8),
                    ('CSPLS', ctypes.c_uint32, 2),
                    ('FLRC', ctypes.c_uint32, 1),
                    ('RSVD_2', ctypes.c_uint32, 3),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxdc(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('CERE', ctypes.c_uint16, 1),
                    ('NFRE', ctypes.c_uint16, 1),
                    ('FERE', ctypes.c_uint16, 1),
                    ('URRE', ctypes.c_uint16, 1),
                    ('ERO', ctypes.c_uint16, 1),
                    ('MPS', ctypes.c_uint16, 3),
                    ('ETE', ctypes.c_uint16, 1),
                    ('PFE', ctypes.c_uint16, 1),
                    ('APPME', ctypes.c_uint16, 1),
                    ('ENS', ctypes.c_uint16, 1),
                    ('MRRS', ctypes.c_uint16, 3),
                    ('IFLR', ctypes.c_uint16, 1),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxds(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('CED', ctypes.c_uint16, 1),
                    ('NFED', ctypes.c_uint16, 1),
                    ('FED', ctypes.c_uint16, 1),
                    ('URD', ctypes.c_uint16, 1),
                    ('APD', ctypes.c_uint16, 1),
                    ('TP', ctypes.c_uint16, 1),
                    ('RSVD_0', ctypes.c_uint16, 10),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxlcap(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('SLS', ctypes.c_uint32, 4),
                    ('MLW', ctypes.c_uint32, 6),
                    ('ASPMS', ctypes.c_uint32, 2),
                    ('L0SEL', ctypes.c_uint32, 3),
                    ('L1EL', ctypes.c_uint32, 3),
                    ('CPM', ctypes.c_uint32, 1),
                    ('SDERC', ctypes.c_uint32, 1),
                    ('DLLLA', ctypes.c_uint32, 1),
                    ('LBNC', ctypes.c_uint32, 1),
                    ('AOC', ctypes.c_uint32, 1),
                    ('RSVD_0', ctypes.c_uint32, 1),
                    ('PN', ctypes.c_uint32, 8),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxlc(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('ASPMC', ctypes.c_uint16, 2),
                    ('RSVD_0', ctypes.c_uint16, 1),
                    ('RCB', ctypes.c_uint16, 1),
                    ('RSVD_1', ctypes.c_uint16, 2),
                    ('CCC', ctypes.c_uint16, 1),
                    ('ES', ctypes.c_uint16, 1),
                    ('ECPM', ctypes.c_uint16, 1),
                    ('HAWD', ctypes.c_uint16, 1),
                    ('RSVD_2', ctypes.c_uint16, 6),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxls(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('CLS', ctypes.c_uint16, 4),
                    ('NLW', ctypes.c_uint16, 6),
                    ('RSVD_0', ctypes.c_uint16, 2),
                    ('SCC', ctypes.c_uint16, 1),
                    ('RSVD_1', ctypes.c_uint16, 3),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxdcap2(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('CTRS', ctypes.c_uint32, 4),
                    ('CTDS', ctypes.c_uint32, 1),
                    ('ARIFS', ctypes.c_uint32, 1),
                    ('AORS', ctypes.c_uint32, 1),
                    ('32AOCS', ctypes.c_uint32, 1),
                    ('64AOCS', ctypes.c_uint32, 1),
                    ('128CCS', ctypes.c_uint32, 1),
                    ('NPRPR', ctypes.c_uint32, 1),
                    ('LTRS', ctypes.c_uint32, 1),
                    ('TPHCS', ctypes.c_uint32, 2),
                    ('RSVD_0', ctypes.c_uint32, 4),
                    ('OBFFS', ctypes.c_uint32, 2),
                    ('EFFS', ctypes.c_uint32, 1),
                    ('EETPS', ctypes.c_uint32, 1),
                    ('MEETP', ctypes.c_uint32, 2),
                    ('RSVD_1', ctypes.c_uint32, 8),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Pxdc2(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('CTA', ctypes.c_uint32, 4),
                    ('CTD', ctypes.c_uint32, 1),
                    ('RSVD_0', ctypes.c_uint32, 5),
                    ('LTRME', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 2),
                    ('OBFFE', ctypes.c_uint32, 2),
                    ('RSVD_2', ctypes.c_uint32, 16),
                ]
                _access_ = access_data
                _base_offset_ = None

            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint8),
                ('NEXT_PTR', ctypes.c_uint8),
                ('PXCAP', Pxcap),
                ('PXDCAP', Pxdcap),
                ('PXDC', Pxdc),
                ('PXDS', Pxds),
                ('PXLCAP', Pxlcap),
                ('PXLC', Pxlc),
                ('PXLS', Pxls),
                ('PXDCAP2', Pxdcap2),
                ('PXDC2', Pxdc2),
            ]
            _access_ = access_data
            _base_offset_ = None

            def set_offsets(self, base_offset):
                self._base_offset_ = base_offset
                self.Pxcap._base_offset_ = base_offset + 2
                self.Pxdcap._base_offset_ = base_offset + 4
                self.Pxdc._base_offset_ = base_offset + 8
                self.Pxds._base_offset_ = base_offset + 10
                self.Pxlcap._base_offset_ = base_offset + 12
                self.Pxlc._base_offset_ = base_offset + 16
                self.Pxls._base_offset_ = base_offset + 18
                self.Pxdcap2._base_offset_ = base_offset + 20
                self.Pxdc2._base_offset_ = base_offset + 24

        class PCICapabilityGenExtended(PCICapabilityExt):
            _cap_id_ = None
            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint32, 16),
                ('CAP_VER', ctypes.c_uint32, 4),
                ('NEXT_PTR', ctypes.c_uint32, 12),
            ]
            _access_ = access_data
            _base_offset_ = None

        class PCICapExtendedAer(PCICapabilityExt):
            _cap_id_ = 0x1

            class Aeruces(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('RSVD_0', ctypes.c_uint32, 4),
                    ('DLPES', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 7),
                    ('PTS', ctypes.c_uint32, 1),
                    ('FCPES', ctypes.c_uint32, 1),
                    ('CTS', ctypes.c_uint32, 1),
                    ('CAS', ctypes.c_uint32, 1),
                    ('UCS', ctypes.c_uint32, 1),
                    ('ROS', ctypes.c_uint32, 1),
                    ('MTS', ctypes.c_uint32, 1),
                    ('ECRCES', ctypes.c_uint32, 1),
                    ('URES', ctypes.c_uint32, 1),
                    ('ACSVS', ctypes.c_uint32, 1),
                    ('UIES', ctypes.c_uint32, 1),
                    ('MCBTS', ctypes.c_uint32, 1),
                    ('AOEBS', ctypes.c_uint32, 1),
                    ('TPBES', ctypes.c_uint32, 1),
                    ('RSVD_2', ctypes.c_uint32, 6),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aerucem(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('RSVD_0', ctypes.c_uint32, 4),
                    ('DLPEM', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 7),
                    ('PTM', ctypes.c_uint32, 1),
                    ('FCPEM', ctypes.c_uint32, 1),
                    ('CTM', ctypes.c_uint32, 1),
                    ('CAM', ctypes.c_uint32, 1),
                    ('UCM', ctypes.c_uint32, 1),
                    ('ROM', ctypes.c_uint32, 1),
                    ('MTM', ctypes.c_uint32, 1),
                    ('ECRCEM', ctypes.c_uint32, 1),
                    ('UREM', ctypes.c_uint32, 1),
                    ('ACSVM', ctypes.c_uint32, 1),
                    ('UIEM', ctypes.c_uint32, 1),
                    ('MCBTM', ctypes.c_uint32, 1),
                    ('AOEBM', ctypes.c_uint32, 1),
                    ('TPBEM', ctypes.c_uint32, 1),
                    ('RSVD_2', ctypes.c_uint32, 6),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aerucesev(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('RSVD_0', ctypes.c_uint32, 4),
                    ('DLPESEV', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 7),
                    ('PTSEV', ctypes.c_uint32, 1),
                    ('FCPESEV', ctypes.c_uint32, 1),
                    ('CTSEV', ctypes.c_uint32, 1),
                    ('CASEV', ctypes.c_uint32, 1),
                    ('UCSEV', ctypes.c_uint32, 1),
                    ('ROSEV', ctypes.c_uint32, 1),
                    ('SEV', ctypes.c_uint32, 1),
                    ('ECRCESEV', ctypes.c_uint32, 1),
                    ('URESEV', ctypes.c_uint32, 1),
                    ('ACSVSEV', ctypes.c_uint32, 1),
                    ('UIESEV', ctypes.c_uint32, 1),
                    ('SEV', ctypes.c_uint32, 1),
                    ('AOEBSEV', ctypes.c_uint32, 1),
                    ('TPBESEV', ctypes.c_uint32, 1),
                    ('RSVD_2', ctypes.c_uint32, 6),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aerces(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('RES', ctypes.c_uint32, 1),
                    ('RSVD_0', ctypes.c_uint32, 5),
                    ('BTS', ctypes.c_uint32, 1),
                    ('BDS', ctypes.c_uint32, 1),
                    ('RRS', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 3),
                    ('RTS', ctypes.c_uint32, 1),
                    ('ANFES', ctypes.c_uint32, 1),
                    ('CIES', ctypes.c_uint32, 1),
                    ('HLOS', ctypes.c_uint32, 1),
                    ('RSVD_2', ctypes.c_uint32, 16),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aercem(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('REM', ctypes.c_uint32, 1),
                    ('RSVD_0', ctypes.c_uint32, 5),
                    ('BTM', ctypes.c_uint32, 1),
                    ('BDM', ctypes.c_uint32, 1),
                    ('RRM', ctypes.c_uint32, 1),
                    ('RSVD_1', ctypes.c_uint32, 3),
                    ('RTM', ctypes.c_uint32, 1),
                    ('ANFEM', ctypes.c_uint32, 1),
                    ('CIEM', ctypes.c_uint32, 1),
                    ('HLOM', ctypes.c_uint32, 1),
                    ('RSVD_2', ctypes.c_uint32, 16),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aercc(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('FEP', ctypes.c_uint32, 5),
                    ('EGC', ctypes.c_uint32, 1),
                    ('EGE', ctypes.c_uint32, 1),
                    ('ECC', ctypes.c_uint32, 1),
                    ('ECE', ctypes.c_uint32, 1),
                    ('MHRC', ctypes.c_uint32, 1),
                    ('MHRE', ctypes.c_uint32, 1),
                    ('TPLP', ctypes.c_uint32, 1),
                    ('RSVD_0', ctypes.c_uint32, 20),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aerhl(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('HB3', ctypes.c_uint8),
                    ('HB2', ctypes.c_uint8),
                    ('HB1', ctypes.c_uint8),
                    ('HB0', ctypes.c_uint8),
                    ('HB7', ctypes.c_uint8),
                    ('HB6', ctypes.c_uint8),
                    ('HB5', ctypes.c_uint8),
                    ('HB4', ctypes.c_uint8),
                    ('HB11', ctypes.c_uint8),
                    ('HB10', ctypes.c_uint8),
                    ('HB9', ctypes.c_uint8),
                    ('HB8', ctypes.c_uint8),
                    ('HB15', ctypes.c_uint8),
                    ('HB14', ctypes.c_uint8),
                    ('HB13', ctypes.c_uint8),
                    ('HB12', ctypes.c_uint8),
                ]
                _access_ = access_data
                _base_offset_ = None

            class Aertlp(RegsStructAccess):
                _pack_ = 1
                _fields_ = [
                    ('TPL1B3', ctypes.c_uint8),
                    ('TPL1B2', ctypes.c_uint8),
                    ('TPL1B1', ctypes.c_uint8),
                    ('TPL1B0', ctypes.c_uint8),
                    ('TPL2B3', ctypes.c_uint8),
                    ('TPL2B2', ctypes.c_uint8),
                    ('TPL2B1', ctypes.c_uint8),
                    ('TPL2B0', ctypes.c_uint8),
                    ('TPL3B3', ctypes.c_uint8),
                    ('TPL3B2', ctypes.c_uint8),
                    ('TPL3B1', ctypes.c_uint8),
                    ('TPL3B0', ctypes.c_uint8),
                    ('TPL4B3', ctypes.c_uint8),
                    ('TPL4B2', ctypes.c_uint8),
                    ('TPL4B1', ctypes.c_uint8),
                    ('TPL4B0', ctypes.c_uint8),
                ]
                _access_ = access_data
                _base_offset_ = None

            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint32, 16),
                ('CAP_VER', ctypes.c_uint32, 4),
                ('NEXT_PTR', ctypes.c_uint32, 12),
                ('AERUCES', Aeruces),
                ('AERUCEM', Aerucem),
                ('AERUCESEV', Aerucesev),
                ('AERCES', Aerces),
                ('AERCEM', Aercem),
                ('AERCC', Aercc),
                ('AERHL', Aerhl),
                ('AERTLP', Aertlp),
            ]
            _access_ = access_data
            _base_offset_ = None

        class PCICapExtendeDeviceSerialNumber(PCICapabilityExt):
            _cap_id_ = 0x3

            _pack_ = 1
            _fields_ = [
                ('CAP_ID', ctypes.c_uint32, 16),
                ('CAP_VER', ctypes.c_uint32, 4),
                ('NEXT_PTR', ctypes.c_uint32, 12),
                ('SN_LOW', ctypes.c_uint32),
                ('SN_HIGH', ctypes.c_uint32),
            ]
            _access_ = access_data
            _base_offset_ = None

    return NVMePCIeRegisters


class PCIeRegisters:

    def init_capabilities(self):

        PCIeCapabilityIdTable = [
            self.PCICapabilityGen,
            self.PCICapPowerManagementInterface,
            *([self.PCICapabilityGen] * 3),
            self.PCICapMSI,
            *([self.PCICapabilityGen] * 10),
            self.PCICapExpress,
            self.PCICapMSIX,
            *([self.PCICapabilityGen] * 238),
        ]

        PCIeCapabilityExtIdTable = [
            self.PCICapabilityGen,
            self.PCICapExtendedAer,
            *([self.PCICapabilityGen] * 1),
            self.PCICapExtendeDeviceSerialNumber,
            *([self.PCICapabilityGenExtended] * 251),
        ]

        # Collect capabilities into a list
        self.capabilities = []

        # Get the pointer to the first capability and walk the list saving each in
        #  the self.capabilities list
        for next_cap_ptr in [self.CAP.CP, 0x100]:

            while next_cap_ptr:

                # Different handling for generic vs extended capabilities
                if next_cap_ptr < 0x100:

                    # Make a generic capability first so we can find out what type it is
                    cap_gen = self.PCICapabilityGen()

                    # Different handling for direct vs indirect registers
                    if type(self) is PCIeRegistersDirect:
                        cap_gen = self.PCICapabilityGen.from_address(
                            ctypes.addressof(self) + next_cap_ptr)
                    else:
                        cap_gen._access_ = self._access_data_
                        cap_gen._base_offset_ = next_cap_ptr

                    # Now we can pull the real type from the table
                    cap_obj = PCIeCapabilityIdTable[cap_gen.CAP_ID]

                else:
                    # Make a generic capability first so we can find out what type it is
                    cap_gen_e = self.PCICapabilityGenExtended()

                    # Different handling for direct vs indirect registers
                    if type(self) is PCIeRegistersDirect:
                        cap_gen_e = self.PCICapabilityGenExtended.from_address(
                            ctypes.addressof(self) + next_cap_ptr)
                    else:
                        cap_gen_e._access_ = self._access_data_
                        cap_gen_e._base_offset_ = next_cap_ptr

                    # Now we can pull the real type from the table
                    cap_obj = PCIeCapabilityExtIdTable[cap_gen_e.CAP_ID]

                # Only add known types to the capabilities list
                if type(self) is PCIeRegistersDirect:
                    capability = cap_obj.from_address(ctypes.addressof(self.ID) + next_cap_ptr)
                else:
                    capability = cap_obj()
                    capability._access_ = self._access_data_
                    capability._base_offset_ = next_cap_ptr
                    capability.set_offsets(capability._base_offset_)

                # Only add if cap id is known
                if type(capability) in [self.PCICapabilityGen, self.PCICapabilityGenExtended]:
                    logging.info('Found unsupported Capability {}: 0x{:x}'.format(
                        'gen' if next_cap_ptr < 0x100 else 'ext', capability.CAP_ID))
                else:
                    self.capabilities.append(capability)

                # Advance to the next pointer
                next_cap_ptr = capability.NEXT_PTR

    def log(self):
        log = logging.getLogger('pcie_regs')
        for field, value in StructFieldsIterator(self):
            if 'RSVD' not in field:
                log.debug('{:50} 0x{:x}'.format(field, value))
                print('{:50} 0x{:x}'.format(field, value))


class PCIeRegistersDirect(pcie_reg_struct_factory(PCIeAccessData(None, None)), PCIeRegisters):
    pass
