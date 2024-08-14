import ctypes
import mmap

from lone.nvme.spec.queues import QueueMgr
from lone.nvme.spec.commands.admin.identify import (IdentifyNamespaceData,
                                                    IdentifyControllerData,
                                                    IdentifyNamespaceListData,
                                                    IdentifyUUIDListData)
import logging
logger = logging.getLogger('nvsim_state')


class NVSimNamespace:

    def __init__(self, num_gbs, block_size, path='/tmp/nvsim.dat'):
        self.num_gbs = num_gbs
        self.block_size = block_size
        self.path = path

        if self.block_size == 512:
            self.num_lbas = int(97696368 + (1953504 * (int(num_gbs) - 50.0)))
        elif self.block_size == 4096:
            self.num_lbas = int(12212046 + (244188 * (int(num_gbs) - 50.0)))
        else:
            assert False, '{} block size not supported'.format(self.block_size)

        self.init_storage()

    def init_storage(self):
        # Create the file
        self.fh = open(self.path, 'w+b')
        self.fh.seek((self.num_lbas * self.block_size) - 1)
        self.fh.write(b'\0')
        self.fh.flush()

        # Mmap so we can easily access
        self.mm = mmap.mmap(self.fh.fileno(), 0)

    def idema_size_512(self, num_gbs):
        return int(97696368 + (1953504 * (int(num_gbs) - 50.0)))

    def idema_size_4096(self, num_gbs):
        return int(12212046 + (244188 * (int(num_gbs) - 50.0)))

    def read(self, lba, num_blocks, prp):
        start_byte = (lba * self.block_size)
        end_byte = start_byte + (num_blocks * self.block_size)
        prp.set_data_buffer(self.mm[start_byte:end_byte])

    def write(self, lba, num_blocks, prp):
        start_byte = (lba * self.block_size)
        end_byte = start_byte + (num_blocks * self.block_size)
        self.mm[start_byte:end_byte] = prp.get_data_buffer()[:(self.block_size * num_blocks)]

    def __del__(self):
        self.mm.close()
        self.fh.close()


class NVSimState:

    def __init__(self, pcie_regs, nvme_regs, mem_mgr, injectors):
        self.mps = 4096

        self.pcie_regs = pcie_regs
        self.nvme_regs = nvme_regs
        self.mem_mgr = mem_mgr
        self.injectors = injectors

        self.queue_mgr = QueueMgr()

        # Stores completion queues from CreateIOCompletionQueue commands that
        #   are not yet associated with a submission queue and therefore cannot
        #    go into the queue manager and be used
        self.completion_queues = []

        # Initalize stuff
        self.init_pcie_regs()
        self.init_nvme_regs()

        # Create a list of namespaces where the index is the nsid
        self.namespaces = [None]  # NSID 0 is not valid
        self.namespaces.append(NVSimNamespace(1, 512, '/tmp/ns_1.dat'))
        self.namespaces.append(NVSimNamespace(2, 4096, '/tmp/ns_2.dat'))
        self.namespaces.append(NVSimNamespace(3, 4096, '/tmp/ns_3.dat'))
        self.namespaces.append(NVSimNamespace(4, 4096, '/tmp/ns_4.dat'))

    def init_pcie_regs(self):
        self.pcie_regs.ID.VID = 0xEDDA
        self.pcie_regs.ID.DID = 0xE111

    def init_nvme_regs(self):
        self.nvme_regs.CAP.CSS = 0x40
        self.nvme_regs.VS.MJR = 0x02
        self.nvme_regs.VS.MNR = 0x01

    def identify_namespace_data(self, nsid):
        id_ns_data = IdentifyNamespaceData()

        # Get the namespace
        nvsim_ns = self.namespaces[nsid]

        # Simulate a drive with 1GB of data (IDEMA calculation)
        id_ns_data.NSZE = nvsim_ns.num_lbas
        id_ns_data.NCAP = nvsim_ns.num_lbas
        id_ns_data.NUSE = 0
        id_ns_data.NSFEAT = 0
        id_ns_data.NLBAF = 2
        id_ns_data.FLBAS = 0 if nvsim_ns.block_size == 512 else 1
        id_ns_data.MC = 0
        id_ns_data.DPC = 0
        id_ns_data.DPS = 0
        id_ns_data.NMIC = 0
        id_ns_data.RESCAP = 0
        id_ns_data.FPI = 0
        id_ns_data.DLFEAT = 0
        id_ns_data.NAWUN = 0

        # 2 supported
        id_ns_data.LBAF_TBL[0].MS = 0
        id_ns_data.LBAF_TBL[0].LBADS = 9
        id_ns_data.LBAF_TBL[0].RP = 0

        id_ns_data.LBAF_TBL[1].MS = 0
        id_ns_data.LBAF_TBL[1].LBADS = 12
        id_ns_data.LBAF_TBL[1].RP = 0

        return id_ns_data

    def identify_controller_data(self):
        id_ctrl_data = IdentifyControllerData()

        id_ctrl_data.MN = b'nvsim_0.1'
        id_ctrl_data.SN = b'EDDAE771'
        id_ctrl_data.FR = b'0.001'

        return id_ctrl_data

    def identify_namespace_list_data(self):
        id_ns_list_data = IdentifyNamespaceListData()

        # Add every namespace in self.namespaces to the list
        #  0 is not a valid ns, so skip it.
        for ns_id, ns in enumerate(self.namespaces[1:]):
            id_ns_list_data.Identifiers[ns_id] = ns_id + 1

        return id_ns_list_data

    def identify_uuid_list_data(self):
        id_uuid_list_data = IdentifyUUIDListData()

        id_uuid_list_data.UUIDS[0].UUID[0] = 1
        id_uuid_list_data.UUIDS[1].UUID[0] = 2
        id_uuid_list_data.UUIDS[2].UUID[0] = 3
        id_uuid_list_data.UUIDS[3].UUID[0] = 4
        id_uuid_list_data.UUIDS[4].UUID[0] = 5
        id_uuid_list_data.UUIDS[5].UUID[0] = 6
        id_uuid_list_data.UUIDS[6].UUID[0] = 7
        id_uuid_list_data.UUIDS[7].UUID[0] = 8
        id_uuid_list_data.UUIDS[8].UUID[0] = 9
        id_uuid_list_data.UUIDS[9].UUID[0] = 10
        id_uuid_list_data.UUIDS[10].UUID[0] = 11
        id_uuid_list_data.UUIDS[11].UUID[0] = 12
        id_uuid_list_data.UUIDS[12].UUID[0] = 13
        id_uuid_list_data.UUIDS[13].UUID[0] = 14
        id_uuid_list_data.UUIDS[14].UUID[0] = 15
        id_uuid_list_data.UUIDS[15].UUID[0] = 16

        return id_uuid_list_data

    def check_mem_access(self, mem):
        ''' Tries to access mem. If this is not successful, then you will see a segfault
        '''
        logger.info('Trying to access 0x{:x} size: {}'.format(mem.vaddr, mem.size))

        data = (ctypes.c_uint8 * (mem.size)).from_address(mem.vaddr)
        data[0] = 0xFF
        data[-1] = 0xFF

        logger.debug('Able to access all memory!')
