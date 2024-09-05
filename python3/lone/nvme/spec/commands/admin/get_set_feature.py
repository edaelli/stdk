import copy
import ctypes
import enum
from lone.nvme.spec.structures import ADMINCommand, DataInCommon
from lone.nvme.spec.commands.status_codes import NVMeStatusCode, status_codes


class GetFeature(ADMINCommand):

    class Select(enum.Enum):
        CURRENT = 0
        DEFAULT = 1
        SAVED = 2
        SUPPORTED_CAPABILITIES = 3

    _pack_ = 1
    _fields_1_ = [
        ('FID', ctypes.c_uint32, 8),
        ('SEL', ctypes.c_uint32, 3),
        ('RSVD_0', ctypes.c_uint32, 21),
    ]

    _fields_2_ = [
        ('UIDX', ctypes.c_uint32, 7),
        ('RSVD_1', ctypes.c_uint32, 25),
        ('DW15', ctypes.c_uint32),
    ]

    _defaults_ = {
        'OPC': 0x0A
    }


# Status codes common to all Get Feature commands
get_feature_status_codes = [
    (0x37, 'Invalid Controller Data Queue'),
]


class SetFeature(ADMINCommand):

    _pack_ = 1
    _fields_1_ = [
        ('FID', ctypes.c_uint32, 8),
        ('RSVD_0', ctypes.c_uint32, 23),
        ('SV', ctypes.c_uint32, 1),
    ]

    _fields_2_ = [
        ('UIDX', ctypes.c_uint32, 7),
        ('RSVD_1', ctypes.c_uint32, 25),
        ('DW15', ctypes.c_uint32),
    ]

    _defaults_ = {
        'OPC': 0x09
    }


# Status codes common to all Set Feature commands
set_feature_status_codes = [
    (0x0d, 'Feature Identifier Not Saveable'),
    (0x0e, 'Feature Not Changeable'),
    (0x0f, 'Feature Not Namespace Specific'),
    (0x14, 'Overlapping Range'),
    (0x2b, 'I/O Command Set Combination Rejected'),
    (0x37, 'Invalid Controller Data Queue'),
]


def FeatureFactory(feature_info, data_in=None, data_out=None):

    # Get Features
    defaults = copy.deepcopy(GetFeature._defaults_)
    defaults['FID'] = feature_info.fid
    fields = (GetFeature._fields_1_ +
              feature_info.get_fields +
              GetFeature._fields_2_)

    # Create the class
    get_cls = type(f'Get{feature_info.__name__}', (ADMINCommand,),
               {'_fields_': fields,
                '_defaults_': defaults,
          })

    # Add status codes
    for code, string in get_feature_status_codes:
        status_codes.add(NVMeStatusCode(code, string, get_cls))

    # TODO: Add data_in_type and size

    # Response for get features when the data is in DW0 of CQE
    def _response(self, cqe):
        return feature_info.from_buffer(ctypes.c_uint32(cqe.CMD_SPEC))
    get_cls.response = _response

    # Set Features
    defaults = copy.deepcopy(SetFeature._defaults_)
    defaults['FID'] = feature_info.fid
    fields = (SetFeature._fields_1_ +
              feature_info._fields_ +
              feature_info.set_fields +
              SetFeature._fields_2_)

    # Create the class
    set_cls = type(f'Set{feature_info.__name__}', (ADMINCommand,),
               {'_fields_': fields,
                '_defaults_': defaults,
          })

    # Add status codes
    for code, string in set_feature_status_codes:
        status_codes.add(NVMeStatusCode(code, string, set_cls))

    # TODO: Add data_in_type and size

    # Return our created class
    return get_cls, set_cls


class FeatureArbitration(ctypes.Structure):
    fid = 0x01
    _fields_ = [
        ('AB', ctypes.c_uint32, 3),
        ('RSVD_0', ctypes.c_uint32, 5),
        ('LPW', ctypes.c_uint32, 8),
        ('MPW', ctypes.c_uint32, 8),
        ('HPW', ctypes.c_uint32, 8),
    ]
    get_fields = [
        ('DW11', ctypes.c_uint32),
        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
    ]
    set_fields = [
        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
    ]


GetFeatureArbitration, SetFeatureArbitration = FeatureFactory(FeatureArbitration)


class FeaturePowerManagement(ctypes.Structure):
    fid = 0x02
    _fields_ = [
        ('PS', ctypes.c_uint32, 4),
        ('WH', ctypes.c_uint32, 3),
        ('RSVD_0', ctypes.c_uint32, 25),
    ]
    get_fields = [
        ('DW11', ctypes.c_uint32),
        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
    ]
    set_fields = [
        ('DW12', ctypes.c_uint32),
        ('DW13', ctypes.c_uint32),
    ]


GetFeaturePowerManagement, SetFeaturePowerManagement = FeatureFactory(FeaturePowerManagement)

