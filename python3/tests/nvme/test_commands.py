import pytest

# ADMIN commands
from lone.nvme.spec.structures import Generic
from lone.nvme.spec.commands.admin.create_io_completion_q import CreateIOCompletionQueue
from lone.nvme.spec.commands.admin.create_io_submission_q import CreateIOSubmissionQueue
from lone.nvme.spec.commands.admin.delete_io_completion_q import DeleteIOCompletionQueue
from lone.nvme.spec.commands.admin.delete_io_submission_q import DeleteIOSubmissionQueue
from lone.nvme.spec.commands.admin.format_nvm import FormatNVM
from lone.nvme.spec.commands.admin.get_log_page import GetLogPage
from lone.nvme.spec.commands.admin.get_set_feature import (GetFeature,
                                                           SetFeature,
                                                           GetFeatureArbitration)
from lone.nvme.spec.commands.admin.identify import (Identify,
                                                    IdentifyNamespace,
                                                    IdentifyController,
                                                    IdentifyNamespaceList,
                                                    IdentifyUUIDList,
                                                    IdentifyNamespaceZoned,
                                                    IdentifyIoCmdSet)
from lone.nvme.spec.commands.admin.sanitize import Sanitize

# NVM commands
from lone.nvme.spec.commands.nvm.flush import Flush
from lone.nvme.spec.commands.nvm.write import Write
from lone.nvme.spec.commands.nvm.read import Read

# Status Codes
from lone.nvme.spec.commands.status_codes import (NVMeStatusCodeException,
                                                  NVMeStatusCode,
                                                  NVMeStatusCodes)


def test_admin_commands():
    assert DeleteIOSubmissionQueue().OPC == 0x00
    assert CreateIOSubmissionQueue().OPC == 0x01
    assert GetLogPage().OPC == 0x02
    assert DeleteIOCompletionQueue().OPC == 0x04
    assert CreateIOCompletionQueue().OPC == 0x05
    assert Identify().OPC == 0x06
    assert IdentifyNamespace().OPC == 0x06
    assert IdentifyController().OPC == 0x06
    assert IdentifyNamespaceList().OPC == 0x06
    assert IdentifyUUIDList().OPC == 0x06
    assert IdentifyNamespaceZoned().OPC == 0x06
    assert IdentifyIoCmdSet().OPC == 0x06
    assert SetFeature().OPC == 0x09
    assert GetFeature().OPC == 0x0A
    assert FormatNVM().OPC == 0x80
    assert Sanitize().OPC == 0x84


def test_gsf_response(mocked_admin_cmd):
    arb_gf = GetFeatureArbitration()
    arb_gf.response(mocked_admin_cmd.cqe)


def test_nvm_commands():
    assert Flush().OPC == 0x00
    assert Write().OPC == 0x01
    assert Read().OPC == 0x02


def test_status_code():
    sc = NVMeStatusCode(0x00, 'test')
    assert int(sc) == 0
    assert str(sc) == 'test'
    assert sc.failure is False
    assert sc.success is True

    sc = NVMeStatusCode(0x01, 'test')
    assert sc.failure is True
    assert sc.success is False

    sc = NVMeStatusCode(0x02, 'test')
    e = NVMeStatusCodeException(sc)
    assert str(e) == 'SF.SC: 0x02 "test" cmd: Generic'


def test_status_codes(mocked_admin_cmd):
    scs = NVMeStatusCodes()
    scs.add(NVMeStatusCode(0xED, 'Testing'))

    # Check type of get return
    assert scs.get(mocked_admin_cmd).cmd_type.__name__ == 'Generic'

    # Check type of get return on failure
    mocked_admin_cmd.cqe.SF.SCT = 1
    assert scs.get(mocked_admin_cmd).cmd_type.__name__ == 'ADMINCommand'

    # Check that getting a good status does not raise and exception
    mocked_admin_cmd.cqe.SF.SCT = 0
    scs.check(mocked_admin_cmd, raise_exc=True)

    # Check that getting a bad status raises an exception
    mocked_admin_cmd.cqe.SF.SCT = 1
    with pytest.raises(NVMeStatusCodeException):
        scs.check(mocked_admin_cmd, raise_exc=True)

    # Check that a bad status with raise_exc = False does not raise an exception
    scs.check(mocked_admin_cmd, raise_exc=False)

    # Test __getitem__
    scs = NVMeStatusCodes()
    scs.add(NVMeStatusCode(0xED, 'Testing', Identify))
    assert scs[Identify].cmd_type.__name__ == 'Generic'
    assert scs[(0xED, Identify)].cmd_type.__name__ == 'Identify'
    assert scs[('Successful Completion', Generic)].cmd_type.__name__ == 'Generic'
    scs[('Testing', Identify)]

    with pytest.raises(AssertionError):
        scs[([], Identify)]
