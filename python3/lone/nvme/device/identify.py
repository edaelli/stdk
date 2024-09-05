from types import SimpleNamespace

from lone.nvme.spec.commands.admin.identify import (IdentifyController,
                                                    IdentifyNamespace,
                                                    IdentifyNamespaceList,
                                                    IdentifyUUIDList)
from lone.nvme.spec.commands.status_codes import NVMeStatusCodeException

import logging
logger = logging.getLogger('nvme_device')


class NVMeDeviceIdentifyData:

    def __init__(self, nvme_device):
        self.nvme_device = nvme_device

        self.identify_data = {}
        self.controller = self.identify_controller()
        self.namespace, self.namespaces = self.identify_namespaces()
        self.uuid_list = self.identify_uuid_list()

    def ns_size(self, lba_ds_bytes, nsze, nuse):

        unit = 'B'
        divisor = 1
        usage = lba_ds_bytes * nuse
        total = lba_ds_bytes * nsze

        if total < (10 ** 3):
            unit = 'B'
            divisor = 1
        elif total < (10 ** 6):
            unit = 'KB'
            divisor = (10 ** 3)
        elif total < (10 ** 9):
            unit = 'MB'
            divisor = (10 ** 6)
        elif total < (10 ** 12):
            unit = 'GB'
            divisor = (10 ** 9)
        else:
            unit = 'TB'
            divisor = (10 ** 12)

        usage = round(((lba_ds_bytes * nuse) / divisor), 2)
        total = round(((lba_ds_bytes * nsze) / divisor), 2)

        return usage, total, unit

    def lba_ds_size(self, lba_ds_bytes):

        unit = 'B'
        divisor = 1

        if lba_ds_bytes > 1024:
            unit = 'KiB'
            divisor = 1024

        size = lba_ds_bytes // divisor
        return size, unit

    def identify_namespaces(self):

        # Send an Indentify Namespace List command to get all used namespaces
        id_ns_list_cmd = IdentifyNamespaceList()
        self.nvme_device.alloc(id_ns_list_cmd)
        self.nvme_device.sync_cmd(id_ns_list_cmd)

        # Loop through all active namespaces and send each one IdentifyNamespace commands
        namespaces = [None] * 1024

        for ns_id in [id_ns_list_cmd.data_in.Identifiers[i] for
                      i in range(1024)
                      if id_ns_list_cmd.data_in.Identifiers[i] != 0]:

            # Create an object with namespace data
            ns = SimpleNamespace(NSID=ns_id)

            # Send an Identify Namespace command, check response
            id_ns_cmd = IdentifyNamespace(NSID=ns_id)
            self.nvme_device.alloc(id_ns_cmd)
            self.nvme_device.sync_cmd(id_ns_cmd)
            ns.id_ns_data = id_ns_cmd.data_in

            # Get information on supported LBAF formats for this namespace
            ns.nsze = id_ns_cmd.data_in.NSZE
            ns.nuse = id_ns_cmd.data_in.NUSE
            ns.flbas = id_ns_cmd.data_in.FLBAS
            ns.lba_ds = id_ns_cmd.data_in.LBAF_TBL[ns.flbas].LBADS
            ns.ms_bytes = id_ns_cmd.data_in.LBAF_TBL[ns.flbas].MS
            assert ns.lba_ds != 0, 'Invalid LBADS = 0'

            # From the identify namespace data we can calculate some information to
            #   present to the user

            # LBA data size in bytes
            ns.lba_ds_bytes = 2 ** ns.lba_ds
            ns.ns_usage, ns.ns_total, ns.ns_unit = self.ns_size(ns.lba_ds_bytes, ns.nsze, ns.nuse)
            ns.lba_size, ns.lba_unit = self.lba_ds_size(ns.lba_ds_bytes)

            namespaces[ns_id] = ns

        return id_ns_list_cmd.data_in, namespaces

    def identify_uuid_list(self):
        id_uuid_list_cmd = IdentifyUUIDList()
        self.nvme_device.alloc(id_uuid_list_cmd)
        try:
            self.nvme_device.sync_cmd(id_uuid_list_cmd)
        except NVMeStatusCodeException:
            logger.info('Device failed id uuid list command!')
        self.uuid_list = id_uuid_list_cmd.data_in

    def identify_controller(self):
        # Send an Identify controller command, check response
        id_ctrl_cmd = IdentifyController()
        self.nvme_device.alloc(id_ctrl_cmd)
        self.nvme_device.sync_cmd(id_ctrl_cmd)
        return id_ctrl_cmd.data_in
