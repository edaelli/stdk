import pytest
import ctypes
from lone.nvme.spec.structures import SQECommon, DataOutCommon, DataInCommon, CQE, DataDumper


def test_sqe_common(mocked_nvme_device):
    sqe = SQECommon()
    assert sqe.OPC == 0x00
    assert sqe.DW2 == 0x00
    assert len(sqe) == 40
    assert sqe.time_ns == 0
    assert sqe.time_us == 0
    assert sqe.time_ms == 0
    assert sqe.time_s == 0

    if False:
        with pytest.raises(AttributeError):
            sqe.NOT_VALID = 1

    class SQEWithDefaults(SQECommon):
        _defaults_ = {
            'OPC': 0x01,
            'DW2': 0x02,
        }
    sqe = SQEWithDefaults()
    assert sqe.OPC == 0x01
    assert sqe.DW2 == 0x02

    class SQEWithDataIn(SQECommon):
        data_in_type = DataInCommon
    sqe = SQEWithDataIn()
    assert type(sqe.data_in) is DataInCommon

    class SQEWithDataOut(SQECommon):
        data_out_type = DataOutCommon
    sqe = SQEWithDataOut()
    assert type(sqe.data_out) is DataOutCommon

    class DataOutWithSize(DataOutCommon):
        _fields_ = [
            ('data', ctypes.c_uint8 * 4096),
        ]

    # Check free_prps path, with and without allocation
    class SQEWithDataOut(SQECommon):
        data_out_type = DataOutWithSize
    sqe = SQEWithDataOut()
    assert type(sqe.data_out) is DataOutWithSize

    sqe.free_prps()
    mocked_nvme_device.alloc(sqe)
    sqe.free_prps()


def test_dump():
    class TestStruct(ctypes.Structure, DataDumper):
        _fields_ = [
            ('test', ctypes.c_uint8),
            ('test_1', (ctypes.c_uint8 * 8)),
            ('RSVD_1', ctypes.c_uint8),
            ('float', ctypes.c_float),
        ]
    d = TestStruct()
    d.dump(printer=print)
    d.dump(prefix='p')
    d.dump(postfix='p')
    d.dump(oneline=False)
    d.dump(prefix='p', oneline=False)
    d.dump(postfix='p', oneline=False)
    d.dump(dump_hex=True)


def test_data_common():
    d_in = DataInCommon()
    assert len(d_in) == 0

    d_out = DataOutCommon()
    assert len(d_out) == 0


def test_cqe():
    cqe = CQE()
    assert cqe.P == 0
    with pytest.raises(AttributeError):
        assert cqe.A is None
    assert len(cqe) == 16

    cqe.P = 1
    assert cqe.P == 1

    cqe.CID = 1
    assert cqe.CID == 1
