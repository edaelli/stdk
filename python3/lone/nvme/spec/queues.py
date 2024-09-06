import ctypes

from lone.nvme.spec.structures import CQE, Generic

import logging
logger = logging.getLogger('nvme_queues')


class NVMeHeadTail:
    def __init__(self, entries, address):
        self.entries = entries
        self._value = ctypes.c_uint32.from_address(address)

    def set(self, value):
        self._value.value = value

    def add(self, num):
        new_value = self._value.value + num
        if new_value == self.entries:
            new_value = 0
        self._value.value = new_value

    def incr(self, num):
        new_value = self._value.value + num
        if new_value == self.entries:
            new_value = 0
        return new_value

    @property
    def value(self):
        return self._value.value


class NVMeQueue:
    def __init__(self, base_address, entries, entry_size, qid, dbh_addr, dbt_addr):
        self.base_address = base_address
        self.entries = entries
        self.entry_size = entry_size
        self.qid = qid
        self.current_slot = 0

        self.head = NVMeHeadTail(self.entries, dbh_addr)
        self.tail = NVMeHeadTail(self.entries, dbt_addr)

    def is_full(self):
        return self.tail.incr(1) == self.head.value

    def num_entries(self):
        if self.tail.incr(1) == self.head.value:
            return self.entries - 1  # -1 because a full queue can only hold entries - 1 items
        elif self.tail.value == self.head.value:
            return 0
        else:
            if self.tail.value > self.head.value:
                return self.tail.value - self.head.value
            else:
                return (self.entries - self.head.value) + self.tail.value


class NVMeSubmissionQueue(NVMeQueue):
    def __init__(self, base_address, entries, entry_size, qid, dbt_addr):
        self.dbh_addr_obj = ctypes.c_uint32(0)
        dbh_addr = ctypes.addressof(self.dbh_addr_obj)
        super().__init__(base_address, entries, entry_size, qid, dbh_addr, dbt_addr)

    def post_command(self, command):
        # TODO: do something other than assert!
        assert self.is_full() is False, (
               "SQ FULL!! {} {} {}".format(self.tail.value, self.head.value, self.entries))

        # Post command
        next_slot_addr = self.base_address.vaddr + (self.tail.value * self.entry_size)
        ctypes.memmove(next_slot_addr, ctypes.addressof(command), self.entry_size)

        # Increment tail, with wrapping
        self.tail.add(1)

    def get_command(self):

        if self.num_entries() == 0:
            return None
        else:
            next_slot_addr = self.base_address.vaddr + (self.head.value * self.entry_size)
            command = Generic.from_address(next_slot_addr)
            self.head.add(1)
            return command


class NVMeCompletionQueue(NVMeQueue):
    def __init__(self, base_address, entries, entry_size, qid, dbh_addr, int_vector=None):
        self.int_vector = int_vector  # None means pooling, integer means msix
        self.dbt_addr_obj = ctypes.c_uint32(0)
        dbt_addr = ctypes.addressof(self.dbt_addr_obj)
        super().__init__(base_address, entries, entry_size, qid, dbh_addr, dbt_addr)
        self.phase = 1

    def get_next_completion(self):
        next_slot_addr = self.base_address.vaddr + (self.head.value * self.entry_size)
        return CQE.from_address(next_slot_addr)

    def consume_completion(self):
        self.head.add(1)
        if self.head.value == 0:
            self.phase = 0 if self.phase == 1 else 1

    def post_completion(self, cqe):
        # TODO: Check if full
        assert self.is_full() is False, "CQ FULL"
        next_slot_addr = self.base_address.vaddr + (self.tail.value * self.entry_size)

        # Update the phase bit to the inverse of what is there
        phase_bit = CQE.from_address(next_slot_addr).SF.P
        cqe.SF.P = 0 if phase_bit == 1 else 1

        ctypes.memmove(next_slot_addr, ctypes.addressof(cqe), self.entry_size)
        self.tail.add(1)


class QueueMgr:
    def __init__(self):
        # Dictionary where keys = (sqid, cqid), values = (sq, cq)
        self.nvme_queues = {}

        self.io_sqids = []
        self.io_sqid_index = 0

        self.io_cqids = []

    def add(self, sq, cq):
        self.nvme_queues[sq.qid, cq.qid] = (sq, cq)

        self.io_sqids = []
        self.io_cqids = []
        for k, v in self.nvme_queues.items():
            sqid, cqid = k
            sq, cq = v
            if sqid != 0 and cqid != 0:
                self.io_sqids.append(sqid)
                self.io_cqids.append(cqid)

    def remove_cq(self, rem_cqid):
        for (sqid, cqid), (sq, cq) in self.nvme_queues.items():
            if cqid == rem_cqid:
                assert sq is None, "Removing CQ with not None SQ! {}".format(cqid)
                self.nvme_queues[(sqid, cqid)] = (sq, None)
                self.io_cqids.remove(cqid)

        # Now remove any that are None, None from our list
        remove_qs = []
        for (sqid, cqid), (sq, cq) in self.nvme_queues.items():
            if self.nvme_queues[(sqid, cqid)] == (None, None):
                remove_qs.append((sqid, cqid))
        for (sqid, cqid) in remove_qs:
            self.nvme_queues.pop((sqid, cqid))

    def remove_sq(self, rem_sqid):
        for (sqid, cqid), (sq, cq) in self.nvme_queues.items():
            if sqid == rem_sqid:
                self.nvme_queues[(sqid, cqid)] = (None, cq)
                self.io_sqids.remove(sqid)
        # Now remove any that are None, None from our list
        remove_qs = []
        for (sqid, cqid), (sq, cq) in self.nvme_queues.items():
            if self.nvme_queues[(sqid, cqid)] == (None, None):
                remove_qs.append((sqid, cqid))
        for (sqid, cqid) in remove_qs:
            self.nvme_queues.pop((sqid, cqid))

    def get_cqs(self):
        cqs = []
        for k, v in self.nvme_queues.items():
            cqs.append(v[1])
        return cqs

    @property
    def all_cqids(self):
        return [0] + self.io_cqids

    @property
    def all_cq_vectors(self):
        vectors = []
        for k, v in self.nvme_queues.items():
            cq = v[1]
            vectors.append(cq.int_vector)
        return vectors

    def get(self, sqid=None, cqid=None):
        sq = None
        cq = None

        # If they are both not None
        if sqid is not None and cqid is not None:
            try:
                sq, cq = self.nvme_queues[(sqid, cqid)]
            except KeyError:
                raise KeyError('SQID: {} CQID: {} not a valid pair'.format(cqid, sqid))

        # Find first cqid associated with sqid
        elif sqid is not None and cqid is None:
            for k, v in self.nvme_queues.items():
                curr_sqid, curr_cqid = k
                sq, cq = v
                if sqid == curr_sqid:
                    break
            else:
                sq = None
                cq = None

        # Else means sqid is None and cqid is not None
        # Find first sqid associated with cqid
        else:
            for k, v in self.nvme_queues.items():
                curr_sqid, curr_cqid = k
                sq, cq = v
                if cqid == curr_cqid:
                    break
            else:
                sq = None
                cq = None

        if sq is None and cq is None:
            return None
        else:
            return sq, cq

    def next_iosq_id(self):
        ret = self.io_sqids[self.io_sqid_index]
        self.io_sqid_index += 1
        if self.io_sqid_index + 1 > len(self.io_sqids):
            self.io_sqid_index = 0
        return ret
