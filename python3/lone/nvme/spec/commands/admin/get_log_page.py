import ctypes
import enum
from lone.nvme.spec.structures import ADMINCommand, DataInCommon
from lone.nvme.spec.commands.status_codes import NVMeStatusCode, status_codes


class GetLogPage(ADMINCommand):
    _pack_ = 1
    _fields_ = [
        ('LID', ctypes.c_uint32, 8),
        ('LSP', ctypes.c_uint32, 7),
        ('RAE', ctypes.c_uint32, 1),
        ('NUMDL', ctypes.c_uint32, 16),

        ('NUMDU', ctypes.c_uint32, 16),
        ('LID_SPEC', ctypes.c_uint32, 16),

        ('LPOL', ctypes.c_uint32),

        ('LPOU', ctypes.c_uint32),

        ('UUID_IDX', ctypes.c_uint32, 7),
        ('RSVD_0', ctypes.c_uint32, 16),
        ('OT', ctypes.c_uint32, 1),
        ('CSI', ctypes.c_uint32, 8),

        ('DW15', ctypes.c_uint32),
    ]

    _defaults_ = {
        'OPC': 0x02
    }


status_codes.add([
    NVMeStatusCode(0x09, 'Invalid Log Page', GetLogPage),
    NVMeStatusCode(0x29, 'I/O Command Set Not Supported', GetLogPage),
])


def GetLogPageFactory(name, lid, data_in_type):
    # Get the GetLogPage defaults and update them with
    #  LID and NUMDL/H
    import copy
    defaults = copy.deepcopy(GetLogPage._defaults_)
    defaults['LID'] = lid
    num_dw = int(ctypes.sizeof(data_in_type) / 4) - 1
    defaults['NUMDL'] = num_dw & 0xFFFF
    defaults['NUMDH'] = num_dw >> 16

    # Create the class
    cls = type(name, (ADMINCommand,),
               {'_fields_': GetLogPage._fields_,
                '_defaults_': defaults,
          })

    # Add data_in_type and size
    cls.data_in_type = data_in_type
    cls.data_in_type.size = ctypes.sizeof(data_in_type)

    # Return our created class
    return cls


class GetLogPageSupportedLogPagesData(DataInCommon):

    class LIDSupportedAndEffectsData(ctypes.Structure):
        _pack_ = 1

        class LIDSupportedAndEffectsDataLIDSPECD(ctypes.Structure):
            _pack_ = 1
            _fields_ = [
                ('ESTCTXRD512HDSUP', ctypes.c_uint16, 1),
                ('RSVD_0', ctypes.c_uint16, 15),
            ]

        _fields_ = [
            ('LSUPP', ctypes.c_uint32, 1),
            ('IOS', ctypes.c_uint32, 1),
            ('RSVD_0', ctypes.c_uint32, 14),  # IS THIS A BUG IN THE SPEC???
            ('LIDSPEC', ctypes.c_uint32, 16)
        ]

    _fields_ = [
        # Note: When using LID 0x0D, the caller can do a
        # GetLogPageSupportedLogPagesData.LIDSupportedAndEffectsDataLIDSPECD.from_buffer
        #   to get the right type on the LIDS data.
        ('LIDS', LIDSupportedAndEffectsData * 256),
    ]


GetLogPageSupportedLogPages = GetLogPageFactory('GetLogPageSupportedLogPages',
                                                0x00,
                                                GetLogPageSupportedLogPagesData)

assert ctypes.sizeof(GetLogPageSupportedLogPagesData) == 1024


class GetLogPageErrorInformationData(DataInCommon):

    class ErrorInformationEntry(ctypes.Structure):
        _pack_ = 1
        _fields_ = [
            ('ErrorCount', ctypes.c_uint64),
            ('SQID', ctypes.c_uint16),
            ('CID', ctypes.c_uint16),

            ('P', ctypes.c_uint16, 1),
            ('SF', ctypes.c_uint16, 15),

            ('ParameterErrLocByte', ctypes.c_uint16, 8),
            ('ParameterErrLocBit', ctypes.c_uint16, 3),
            ('RSVD_0', ctypes.c_uint16, 5),

            ('LBA', ctypes.c_uint64),
            ('NS', ctypes.c_uint32),
            ('VSINFO', ctypes.c_uint8),
            ('TRTYPE', ctypes.c_uint8),
            ('RSVD_1', ctypes.c_uint16),
            ('CMDSPECINFO', ctypes.c_uint64),
            ('TRTYPESPECINFO', ctypes.c_uint16),
            ('RSVD_2', ctypes.c_uint8 * 22),
        ]

    _pack_ = 1
    _fields_ = [
        ('ERRORS', ErrorInformationEntry * 256),
    ]


GetLogPageErrorInformation = GetLogPageFactory('GetLogPageErrorInformation',
                                               0x01,
                                               GetLogPageErrorInformationData)

assert ctypes.sizeof(GetLogPageErrorInformationData) == 16384


class GetLogPageSMARTData(DataInCommon):

    class CriticalWarning(ctypes.Structure):
        _pack_ = 1
        _fields_ = [
            ('AvailableSpareBelowThreshold', ctypes.c_uint8, 1),
            ('TemperatureThreshold', ctypes.c_uint8, 1),
            ('NVMeSubsystemReliabilityDegraded', ctypes.c_uint8, 1),
            ('ReadOnlyMode', ctypes.c_uint8, 1),
            ('VolatileMemBackupFailed', ctypes.c_uint8, 1),
            ('PersistentMemRegionReadOnly', ctypes.c_uint8, 1),
            ('RSVD_0', ctypes.c_uint8, 2),
        ]

    class EnduranceGroupCriticalWarning(ctypes.Structure):
        _pack_ = 1
        _fields_ = [
            ('AvailableSpareBelowThreshold', ctypes.c_uint8, 1),
            ('RSVD_0', ctypes.c_uint8, 1),
            ('ReliabilityDegraded', ctypes.c_uint8, 1),
            ('NamespaceInReadOnlyMode', ctypes.c_uint8, 1),
            ('RSVD_1', ctypes.c_uint8, 4),
        ]

    class TemperatureSensorData(ctypes.Structure):
        _pack_ = 1
        _fields_ = [
            ('TST', ctypes.c_uint16),
        ]

    _pack_ = 1
    _fields_ = [
        ('CriticalWarning', CriticalWarning),
        ('CompositeTemperature', ctypes.c_uint16),
        ('AvailableSpare', ctypes.c_uint8),
        ('AvailableSpareThreshold', ctypes.c_uint8),
        ('PercentageUsed', ctypes.c_uint8),
        ('EnduranceGrpCriticalWarnSummary', EnduranceGroupCriticalWarning),
        ('RSVD_0', ctypes.c_uint8 * 25),
        ('DataUnitsReadLo', ctypes.c_uint64),
        ('DataUnitsReadHi', ctypes.c_uint64),
        ('DataUnitsWrittenLo', ctypes.c_uint64),
        ('DataUnitsWrittenHi', ctypes.c_uint64),
        ('HostReadCommandsLo', ctypes.c_uint64),
        ('HostReadCommandsHi', ctypes.c_uint64),
        ('HostWriteCommandsLo', ctypes.c_uint64),
        ('HostWriteCommandsHi', ctypes.c_uint64),
        ('ControllerBusyTimeLo', ctypes.c_uint64),
        ('ControllerBusyTimeHi', ctypes.c_uint64),
        ('PowerCyclesLo', ctypes.c_uint64),
        ('PowerCyclesHi', ctypes.c_uint64),
        ('PowerOnHoursLo', ctypes.c_uint64),
        ('PowerOnHoursHi', ctypes.c_uint64),
        ('UnsafeShutdownsLo', ctypes.c_uint64),
        ('UnsafeShutdownsHi', ctypes.c_uint64),
        ('MediaAndDataIntegrityErrorsLo', ctypes.c_uint64),
        ('MediaAndDataIntegrityErrorsHi', ctypes.c_uint64),
        ('NumberofErrorInformationLogEntriesLo', ctypes.c_uint64),
        ('NumberofErrorInformationLogEntriesHi', ctypes.c_uint64),
        ('WarningCompTempTime', ctypes.c_uint32),
        ('CriticalCompTempTime', ctypes.c_uint32),
        ('TempSensors', TemperatureSensorData * 8),
        ('ThermalMgmtTemp1TransitionCount', ctypes.c_uint32),
        ('ThermalMgmtTemp2TransitionCount', ctypes.c_uint32),
        ('TotalTimeThermalMgmtTemp1', ctypes.c_uint32),
        ('TotalTimeThermalMgmtTemp2', ctypes.c_uint32),
        ('RSVD_1', ctypes.c_uint8 * 280),
    ]


GetLogPageSMART = GetLogPageFactory('GetLogPageSMART',
                                    0x02,
                                    GetLogPageSMARTData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageSMARTData) == 512
assert GetLogPageSMARTData.ThermalMgmtTemp2TransitionCount.offset == 220
assert GetLogPageSMARTData.ControllerBusyTimeLo.offset == 96


class GetLogPageFirmwareSlotInfoData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('AFI', ctypes.c_uint8),
        ('RSVD_0', ctypes.c_uint8 * 7),
        ('FRS1', ctypes.c_char * 8),
        ('FRS2', ctypes.c_char * 8),
        ('FRS3', ctypes.c_char * 8),
        ('FRS4', ctypes.c_char * 8),
        ('FRS5', ctypes.c_char * 8),
        ('FRS6', ctypes.c_char * 8),
        ('FRS7', ctypes.c_char * 8),
        ('RSVD_0', ctypes.c_uint8 * 448),
    ]


GetLogPageFirmwareSlotInfo = GetLogPageFactory('GetLogPageFirmwareSlotInfo',
                                               0x03,
                                               GetLogPageFirmwareSlotInfoData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageFirmwareSlotInfoData) == 512
assert GetLogPageFirmwareSlotInfoData.FRS3.offset == 24


class GetLogPageChangedNamespaceListData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('CHANGED_NS', ctypes.c_uint32 * 1024),
    ]


GetLogPageChangedNamespaceList = GetLogPageFactory('GetLogPageChangedNamespaceList',
                                                   0x04,
                                                   GetLogPageChangedNamespaceListData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageChangedNamespaceListData) == 4096


class GetLogPageCommandsSupportedAndEffectsData(DataInCommon):

    class CommandsSupportedAndEffects(ctypes.Structure):
        _pack_ = 1
        _fields_ = [
            ('CSUPP', ctypes.c_uint32, 1),
            ('LBCC', ctypes.c_uint32, 1),
            ('NCC', ctypes.c_uint32, 1),
            ('NIC', ctypes.c_uint32, 1),
            ('CCC', ctypes.c_uint32, 1),
            ('RSVD_0', ctypes.c_uint32, 9),
            ('CSER', ctypes.c_uint32, 2),
            ('CSE', ctypes.c_uint32, 3),
            ('USS', ctypes.c_uint32, 1),
            ('CSP', ctypes.c_uint32, 12),
        ]

    _pack_ = 1
    _fields_ = [
        ('ACS', CommandsSupportedAndEffects * 256),
        ('IOCS', CommandsSupportedAndEffects * 256),
        ('RSVD_0', ctypes.c_uint8 * 2048),
    ]


GetLogPageCommandsSupportedAndEffects = GetLogPageFactory(
    'GetLogPageCommandsSupportedAndEffects',
    0x05,
    GetLogPageCommandsSupportedAndEffectsData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageCommandsSupportedAndEffectsData) == 4096


class GetLogPageDeviceSelfTestData(DataInCommon):

    class DeviceSelfTestResult(ctypes.Structure):

        class Code(enum.Enum):
            SHORT_DST_OPERATION = 1
            EXT_DST_OPERATION = 2
            VENDOR_SPECIFIC = 2

        class Result(enum.Enum):
            SUCCESS = 0
            ABORTED_DST_CMD = 1
            ABORTED_CTRL_LEVEL_RESET = 2
            ABORTED_NS_REMOVAL = 3
            ABORTED_NVM_FORMAT = 4
            FATAL_ERROR = 5
            UNKNOWN_FAILED_SEGMENT = 6
            FAILED_SEGMENT = 7
            ABORTED_UNKNOWN = 8
            ABORTED_SANITIZE = 9

        _pack_ = 1
        _fields_ = [
            ('Code', ctypes.c_uint8, 4),
            ('Result', ctypes.c_uint8, 4),
        ]

        _pack_ = 1
        _fields_ = [
            ('Status', ctypes.c_uint8, 4),
            ('Code', ctypes.c_uint8, 4),
            ('SegmentNumber', ctypes.c_uint8),
            ('ValidDiagInfo', ctypes.c_uint8),
            ('RSVD_0', ctypes.c_uint8),
            ('POH', ctypes.c_uint64),
            ('NSID', ctypes.c_uint32),
            ('FAIL_LBA', ctypes.c_uint64),
            ('SCT', ctypes.c_uint8),
            ('SC', ctypes.c_uint8),
            ('VU', ctypes.c_uint16),
        ]

    _pack_ = 1
    _fields_ = [
        ('Operation', ctypes.c_uint8),
        ('Completion', ctypes.c_uint8),
        ('RSVD_0', ctypes.c_uint8 * 2),
        ('Results', DeviceSelfTestResult * 20),
    ]


GetLogPageDeviceSelfTest = GetLogPageFactory(
    'GetLogPageDeviceSelfTest',
    0x06,
    GetLogPageDeviceSelfTestData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageDeviceSelfTestData) == 564


class TelemetryDataBlock(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('Data', ctypes.c_uint8 * 512),
    ]


class GetLogPageTelemetryHostInitiatedData(DataInCommon):
    # Limit the page to 512 data blocks, which makes the
    #  data size to around 256k. This can be bigger, just
    #  needed a limit to create the structure here
    max_data_blocks = 512

    _pack_ = 1
    _fields_ = [
        ('LogIdentifier', ctypes.c_uint8),
        ('RSVD_0', ctypes.c_uint8 * 4),
        ('IEEE', ctypes.c_uint8 * 3),
        ('DataArea1LastBlock', ctypes.c_uint16),
        ('DataArea2LastBlock', ctypes.c_uint16),
        ('DataArea3LastBlock', ctypes.c_uint16),
        ('RSVD_1', ctypes.c_uint8 * 2),
        ('DataArea4LastBlock', ctypes.c_uint32),
        ('RSVD_2', ctypes.c_uint8 * 361),
        ('HostInitDataGenerationNumber', ctypes.c_uint8),
        ('ControllerDataAvailable', ctypes.c_uint8),
        ('ControllerDataGenerationNumber', ctypes.c_uint8),
        ('ReaonIdentifier', ctypes.c_uint8 * 128),
        ('DataBlocks', TelemetryDataBlock * max_data_blocks),
    ]


GetLogPageTelemetryHostInitiated = GetLogPageFactory(
    'GetLogPageTelemetryHostInitiated',
    0x07,
    GetLogPageTelemetryHostInitiatedData)
# GetLogPageTelemetryHostInitiated.LSP = 0x01 Create Telemetry host-init data

# Perform some checks to make sure it matches the spec
assert (ctypes.sizeof(GetLogPageTelemetryHostInitiatedData) ==
       (GetLogPageTelemetryHostInitiatedData.max_data_blocks * 512) + 512)


class GetLogPageTelemetryControllerInitiatedData(DataInCommon):
    # Limit the page to 512 data blocks, which makes the
    #  data size to around 256k. This can be bigger, just
    #  needed a limit to create the structure here
    max_data_blocks = 512

    _pack_ = 1
    _fields_ = [
        ('LogIdentifier', ctypes.c_uint8),
        ('RSVD_0', ctypes.c_uint8 * 4),
        ('IEEE', ctypes.c_uint8 * 3),
        ('DataArea1LastBlock', ctypes.c_uint16),
        ('DataArea2LastBlock', ctypes.c_uint16),
        ('DataArea3LastBlock', ctypes.c_uint16),
        ('RSVD_1', ctypes.c_uint8 * 2),
        ('DataArea4LastBlock', ctypes.c_uint32),
        ('RSVD_2', ctypes.c_uint8 * 362),
        ('ControllerDataAvailable', ctypes.c_uint8),
        ('ControllerDataGenerationNumber', ctypes.c_uint8),
        ('ReaonIdentifier', ctypes.c_uint8 * 128),
        ('DataBlocks', TelemetryDataBlock * max_data_blocks),
    ]


GetLogPageTelemetryControllerInitiated = GetLogPageFactory(
    'GetLogPageTelemetryControllerInitiated',
    0x08,
    GetLogPageTelemetryControllerInitiatedData)

# Perform some checks to make sure it matches the spec
assert (ctypes.sizeof(GetLogPageTelemetryControllerInitiatedData) ==
       (GetLogPageTelemetryControllerInitiatedData.max_data_blocks * 512) + 512)


class GetLogPageEnduranceGroupInformationData(DataInCommon):

    class CriticalWarning(DataInCommon):
        _pack_ = 1
        _fields_ = [
            ('AvailableSpareCapLow', ctypes.c_uint8, 1),
            ('RSVD_0', ctypes.c_uint8, 1),
            ('ReliabilityDegraded', ctypes.c_uint8, 1),
            ('AllReadOnly', ctypes.c_uint8, 1),
            ('RSVD_1', ctypes.c_uint8, 4),
        ]

    class EnduranceGroupFeatures(DataInCommon):
        _pack_ = 1
        _fields_ = [
            ('EGRMEDIA', ctypes.c_uint8, 1),
            ('RSVD_0', ctypes.c_uint8, 7),
        ]

    _pack_ = 1
    _fields_ = [
        ('CriticalWarning', CriticalWarning),
        ('EGFEAT', EnduranceGroupFeatures),
        ('RSVD_0', ctypes.c_uint8),
        ('AvailableSpare', ctypes.c_uint8),
        ('AvailableSpareThreshold', ctypes.c_uint8),
        ('PercentageUsed', ctypes.c_uint8),
        ('DomainIdentifier', ctypes.c_uint16),
        ('RSVD_1', ctypes.c_uint8 * 24),
        ('EnduranceEstimateLo', ctypes.c_uint64),
        ('EnduranceEstimateHi', ctypes.c_uint64),
        ('DataUnitsReadLo', ctypes.c_uint64),
        ('DataUnitsReadHi', ctypes.c_uint64),
        ('DataUnitsWrittenLo', ctypes.c_uint64),
        ('DataUnitsWrittenHi', ctypes.c_uint64),
        ('MediaUnitsWrittenLo', ctypes.c_uint64),
        ('MediaUnitsWrittenHi', ctypes.c_uint64),
        ('HostReadCommandsLo', ctypes.c_uint64),
        ('HostReadCommandsHi', ctypes.c_uint64),
        ('HostWriteCommandsLo', ctypes.c_uint64),
        ('HostWriteCommandsHi', ctypes.c_uint64),
        ('MediaAndDataIntegrityErrorsLo', ctypes.c_uint64),
        ('MediaAndDataIntegrityErrorsHi', ctypes.c_uint64),
        ('NumberofErrorInformationLogEntriesLo', ctypes.c_uint64),
        ('NumberofErrorInformationLogEntriesHi', ctypes.c_uint64),
        ('TEGCAP_LO', ctypes.c_uint64),
        ('TEGCAP_HI', ctypes.c_uint64),
        ('UEGCAP_LO', ctypes.c_uint64),
        ('UEGCAP_HI', ctypes.c_uint64),
        ('RSVD_2', ctypes.c_uint8 * 320),
    ]


GetLogPageEnduranceGroupInformation = GetLogPageFactory(
    'GetLogPageEnduranceGroupInformation',
    0x09,
    GetLogPageEnduranceGroupInformationData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageEnduranceGroupInformationData) == 512


class GetLogPagePredictableLatencyPerNVMSetData(DataInCommon):

    class Status(enum.Enum):
        NOT_USED = 0
        DTWIN = 1
        NDWIN = 2

    class EventType(enum.Enum):
        DTWIN_READS_WARNING = 0
        DTWIN_WRITES_WARNING = 1
        DTWIN_TIME_WARNING = 2
        AUTO_TRANSITION_DTWIN_TO_NDWIN_TYP_OR_MAX = 14
        AUTO_TRANSITION_DTWIN_TO_NDWIN_DETERMINISTIC_EXCURSION = 15

    _pack_ = 1
    _fields_ = [
        ('Status', ctypes.c_uint8),
        ('RSVD_0', ctypes.c_uint8),
        ('EventType', ctypes.c_uint16),
        ('RSVD_1', ctypes.c_uint8 * 28),
        ('DTWIN_ReadsTypical', ctypes.c_uint64),
        ('DTWIN_WritesTypical', ctypes.c_uint64),
        ('DTWIN_TimeMax', ctypes.c_uint64),
        ('NDWIN_TimeMinHi', ctypes.c_uint64),
        ('NDWIN_TimeMinLo', ctypes.c_uint64),
        ('RSVD_2', ctypes.c_uint8 * 56),
        ('DTWIN_ReadsEstimate', ctypes.c_uint64),
        ('DTWIN_WritesEstimate', ctypes.c_uint64),
        ('DTWIN_TimeEstimate', ctypes.c_uint64),
        ('RSVD_3', ctypes.c_uint8 * 360),
    ]


GetLogPagePredictableLatencyPerNVMSet = GetLogPageFactory(
    'GetLogPagePredictableLatencyPerNVMSet',
    0x0a,
    GetLogPagePredictableLatencyPerNVMSetData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPagePredictableLatencyPerNVMSetData) == 512


class GetLogPagePredictableLatencyEventAggregateData(DataInCommon):
    max_entries = 256

    _pack_ = 1
    _fields_ = [
        ('NumberOfEntries', ctypes.c_uint64),
        ('Entries', ctypes.c_uint16 * max_entries),
    ]


GetLogPagePredictableLatencyEventAggregate = GetLogPageFactory(
    'GetLogPagePredictableLatencyEventAggregate',
    0x0b,
    GetLogPagePredictableLatencyEventAggregateData)

# Perform some checks to make sure it matches the spec
assert (ctypes.sizeof(GetLogPagePredictableLatencyEventAggregateData) ==
       (8 + (GetLogPagePredictableLatencyEventAggregateData.max_entries * 2)))


class GetLogPageAsymetricNamespaceAccessData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageAsymetricNamespaceAccess = GetLogPageFactory(
    'GetLogPageAsymetricNamespaceAccess',
    0x0c,
    GetLogPageAsymetricNamespaceAccessData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageAsymetricNamespaceAccessData) == 4096


class GetLogPagePersistentEventLogData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPagePersistentEventLog = GetLogPageFactory(
    'GetLogPagePersistentEventLog',
    0x0d,
    GetLogPagePersistentEventLogData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPagePersistentEventLogData) == 4096


class GetLogPageEnduranceGroupEventAggregateData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageEnduranceGroupEventAggregate = GetLogPageFactory(
    'GetLogPageEnduranceGroupEventAggregate',
    0x0f,
    GetLogPageEnduranceGroupEventAggregateData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageEnduranceGroupEventAggregateData) == 4096


class GetLogPageMediaUnitStatusData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageMediaUnitStatus = GetLogPageFactory(
    'GetLogPageMediaUnitStatus',
    0x10,
    GetLogPageMediaUnitStatusData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageMediaUnitStatusData) == 4096


class GetLogPageSupportedCapacityConfigurationListData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageSupportedCapacityConfigurationList = GetLogPageFactory(
    'GetLogPageSupportedCapacityConfigurationList',
    0x11,
    GetLogPageSupportedCapacityConfigurationListData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageSupportedCapacityConfigurationListData) == 4096


class GetLogPageFeatureIdentifiersSupportedAndEffectsData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageFeatureIdentifiersSupportedAndEffects = GetLogPageFactory(
    'GetLogPageFeatureIdentifiersSupportedAndEffects',
    0x12,
    GetLogPageFeatureIdentifiersSupportedAndEffectsData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageFeatureIdentifiersSupportedAndEffectsData) == 4096


class GetLogPageNVMeMICommandsSupportedAndEffectsData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageNVMeMICommandsSupportedAndEffects = GetLogPageFactory(
    'GetLogPageNVMeMICommandsSupportedAndEffects',
    0x13,
    GetLogPageNVMeMICommandsSupportedAndEffectsData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageNVMeMICommandsSupportedAndEffectsData) == 4096


class GetLogPageCommandAndFeatureLockdownData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageCommandAndFeatureLockdown = GetLogPageFactory(
    'GetLogPageCommandAndFeatureLockdown',
    0x14,
    GetLogPageCommandAndFeatureLockdownData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageCommandAndFeatureLockdownData) == 4096


class GetLogPageBootPartitionData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageBootPartition = GetLogPageFactory(
    'GetLogPageBootPartition',
    0x15,
    GetLogPageBootPartitionData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageBootPartitionData) == 4096


class GetLogPageRotationalMediaInformationData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageRotationalMediaInformation = GetLogPageFactory(
    'GetLogPageRotationalMediaInformation',
    0x16,
    GetLogPageRotationalMediaInformationData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageRotationalMediaInformationData) == 4096


class GetLogPageDiscoveryData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageDiscovery = GetLogPageFactory(
    'GetLogPageDiscovery',
    0x70,
    GetLogPageDiscoveryData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageDiscoveryData) == 4096


class GetLogPageReservationNotificationData(DataInCommon):
    _pack_ = 1
    _fields_ = [
        ('placeholder', ctypes.c_uint8 * 4096),
    ]


GetLogPageReservationNotification = GetLogPageFactory(
    'GetLogPageReservationNotification',
    0x80,
    GetLogPageReservationNotificationData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageReservationNotificationData) == 4096


class GetLogPageSanitizeStatusData(DataInCommon):
    class SStat(ctypes.Structure):
        class Sos(enum.IntEnum):
            NEVER_STARTED = 0
            SANITIZED = 1
            SANITIZING = 2
            FAILED = 3
            UNEXPECTED_DEALLOCATE = 4

        _pack_ = 1
        _fields_ = [
            ('SOS', ctypes.c_uint16, 3),
            ('OPC', ctypes.c_uint16, 5),
            ('GDE', ctypes.c_uint16, 1),
            ('MVCNCLD', ctypes.c_uint16, 1),
            ('RSVD_0', ctypes.c_uint16, 6),
        ]

    _pack_ = 1
    _fields_ = [
        ('SPROG', ctypes.c_uint16),
        ('SSTAT', SStat),
        ('SCDW10', ctypes.c_uint32),
        ('OVERW_TIME', ctypes.c_uint32),
        ('BLKERASE_TIME', ctypes.c_uint32),
        ('CRYPTO_TIME', ctypes.c_uint32),
        ('OVERWNODEALLOC_TIME', ctypes.c_uint32),
        ('BLOCKERASENODEALLOC_TIME', ctypes.c_uint32),
        ('CRYPTOERASENODEALLOC_TIME', ctypes.c_uint32),
        ('RESERVED', ctypes.c_uint8 * 480),
    ]


GetLogPageSanitizeStatus = GetLogPageFactory(
    'GetLogPageSanitizeStatus',
    0x81,
    GetLogPageSanitizeStatusData)

# Perform some checks to make sure it matches the spec
assert ctypes.sizeof(GetLogPageSanitizeStatusData) == 512
