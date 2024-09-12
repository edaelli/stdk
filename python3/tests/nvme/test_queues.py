import pytest
import ctypes

from lone.system import MemoryLocation
from lone.nvme.spec.structures import CQE, Generic
from lone.nvme.spec.queues import NVMeHeadTail, NVMeQueue, NVMeSubmissionQueue, NVMeCompletionQueue
from lone.nvme.spec.queues import QueueMgr


# Generic memory locationis for tests below
mem = (ctypes.c_uint8 * 4096)()
mem_address = ctypes.addressof(mem)
mem_loc = MemoryLocation(mem_address, mem_address, 4096, 'test')
mem1 = (ctypes.c_uint8 * 4096)()
mem1_address = ctypes.addressof(mem1)
mem1_loc = MemoryLocation(mem1_address, mem1_address, 4096, 'test1')
mem2 = (ctypes.c_uint8 * 4096)()
mem2_address = ctypes.addressof(mem2)
mem2_loc = MemoryLocation(mem2_address, mem2_address, 4096, 'test2')


####################################################################################################
# NVMeHeadTail tests
####################################################################################################
def test_nvme_head_tail_init():
    ''' def __init__(self, entries, address):
    '''
    mem[0] = 5
    nht = NVMeHeadTail(10, mem_address)
    assert nht.entries == 10
    assert nht.value == 5


def test_nvme_head_tail_set():
    ''' def set(self, value):
    '''
    nht = NVMeHeadTail(10, mem_address)
    nht.set(6)
    assert nht.value == 6


def test_nvme_head_tail_advance():
    ''' def addvance(self):
    '''
    nht = NVMeHeadTail(3, mem_address)
    nht.set(0)

    nht.advance()
    assert nht.value == 1

    nht.advance()
    assert nht.value == 2

    # Test wrapping
    nht.advance()
    assert nht.value == 0


def test_nvme_head_tail_peek():
    ''' def incr(self):
    '''
    nht = NVMeHeadTail(3, mem_address)
    nht.set(0)

    assert nht.peek() == 1

    nht.set(1)
    assert nht.peek() == 2

    # Test wrapping
    nht.set(2)
    assert nht.peek() == 0


def test_nvme_head_tail_value():
    ''' def value(self):
    '''
    nht = NVMeHeadTail(10, mem_address)
    nht.set(0)
    assert nht.value == 0


####################################################################################################
# NVMeQueue tests
####################################################################################################
def test_nvme_queue_init():
    ''' def __init__(self, base_address, entries, entry_size, qid, dbh_addr, dbt_addr):
    '''
    q = NVMeQueue(mem_address, 10, 16, 0, mem1_address, mem2_address)
    assert q.entries == 10
    assert q.entry_size == 16


def test_nvme_queue_is_full():
    ''' def is_full(self):
    '''
    q = NVMeQueue(mem_address, 3, 16, 0, mem1_address, mem2_address)
    assert q.is_full() is False

    # Create q full condition by advancing the tail
    assert q.tail.value == 0
    q.tail.advance()
    q.tail.advance()
    assert q.is_full() is True


def test_nvme_queue_num_entries():
    ''' def num_entries(self):
    '''
    q = NVMeQueue(mem_address, 4, 16, 0, mem1_address, mem2_address)
    q.tail.set(0)
    q.head.set(0)
    assert q.num_entries() == 0

    q.tail.advance()
    assert q.num_entries() == 1

    q.tail.advance()
    assert q.num_entries() == 2

    q.tail.advance()
    assert q.num_entries() == 3

    q.tail.advance()
    assert q.num_entries() == 0

    q.tail.set(1)
    q.head.set(3)
    assert q.num_entries() == 2


####################################################################################################
# NVMeSubmissionQueue tests
####################################################################################################
def test_nvme_subq_init():
    ''' def __init__(self, base_address, entries, entry_size, qid, dbt_addr):
    '''
    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    assert sq.entries == 16
    assert sq.entry_size == 64


def test_nvme_subq_post_command(mocked_admin_cmd):
    ''' def post_command(self, command):
    '''
    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    sq.tail.set(0)
    sq.post_command(mocked_admin_cmd)
    assert sq.tail.value == 1


def test_nvme_subq_get_command():
    ''' def get_command(self):
    '''
    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    sq.tail.set(0)
    assert sq.get_command() is None

    sq.tail.set(1)
    cmd = sq.get_command()
    assert cmd is not None
    assert type(cmd) is Generic


####################################################################################################
# NVMeCompletionQueue tests
####################################################################################################
def test_nvme_cmpq_init():
    ''' def __init__(self, base_address, entries, entry_size, qid, dbh_addr, int_vector=None):
    '''
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    assert cq.entries == 16
    assert cq.entry_size == 16


def test_nvme_cmpq_get_next_completion():
    ''' def get_next_completion(self):
    '''
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    cqe = cq.get_next_completion()
    assert type(cqe) is CQE


def test_nvme_cmpq_consume_completion():
    ''' def consume_completion(self):
    '''
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)

    cq.head.set(0)
    cq.consume_completion()
    assert cq.head.value == 1

    # With wrapping
    cq.head.set(15)
    cq.consume_completion()
    assert cq.head.value == 0


def test_nvme_cmpq_post_completion():
    ''' def post_completion(self, cqe):
    '''
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    cqe = CQE()

    cq.tail.set(0)
    cq.post_completion(cqe)
    assert cq.tail.value == 1


####################################################################################################
# QueueMgr tests
####################################################################################################
def test_queue_mgr_init():
    ''' def __init__(self):
    '''
    qm = QueueMgr()
    assert len(qm.nvme_queues) == 0
    assert len(qm.io_sqids) == 0
    assert qm.io_sqid_index == 0
    assert len(qm.io_cqids) == 0


def test_queue_mgr_add():
    ''' def add(self, sq, cq):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    qm.add(sq, cq)
    assert len(qm.nvme_queues) == 1

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 1, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 1, mem1_address, 0)
    qm.add(sq, cq)
    assert qm.io_sqids[0] == 1
    assert qm.io_cqids[0] == 1


def test_queue_mgr_remove_cq():
    ''' def remove_cq(self, rem_cqid):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    qm.add(sq, cq)

    qm.remove_sq(0)
    qm.remove_cq(0)


def test_queue_mgr_remove_sq():
    ''' def remove_sq(self, rem_sqid):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    qm.add(sq, cq)

    qm.remove_sq(0)


def test_queue_mgr_get_cqs():
    ''' def get_cqs(self):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    qm.add(sq, cq)
    assert len(qm.get_cqs()) == 1

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 1, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 1, mem1_address, 0)
    qm.add(sq, cq)
    assert len(qm.get_cqs()) == 2


def test_queue_mgr_all_cqids():
    ''' def all_cqids(self):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    qm.add(sq, cq)
    assert len(qm.all_cqids) == 1
    assert qm.all_cqids[0] == 0

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 1, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 1, mem1_address, 0)
    qm.add(sq, cq)
    assert len(qm.all_cqids) == 2
    assert qm.all_cqids[0] == 0
    assert qm.all_cqids[1] == 1


def test_queue_mgr_all_cq_vectors():
    ''' def all_cq_vectors(self):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)
    qm.add(sq, cq)
    assert len(qm.all_cq_vectors) == 1
    assert qm.all_cq_vectors[0] == 0

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 1, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 1, mem1_address, 3)
    qm.add(sq, cq)
    assert len(qm.all_cq_vectors) == 2
    assert qm.all_cq_vectors[0] == 0
    assert qm.all_cq_vectors[1] == 3


def test_queue_mgr_get():
    ''' def get(self, sqid=None, cqid=None):
    '''
    qm = QueueMgr()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 0, mem1_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 0, mem1_address, 0)

    with pytest.raises(KeyError):
        qm.get(sqid=0, cqid=0)

    qm.add(sq, cq)
    sq, cq = qm.get(sqid=0, cqid=0)
    assert sq.qid == 0
    assert cq.qid == 0

    sq, cq = qm.get(sqid=0, cqid=None)
    assert sq.qid == 0
    assert cq.qid == 0

    sq, cq = qm.get(sqid=1, cqid=None)
    assert sq is None
    assert cq is None

    sq, cq = qm.get(sqid=None, cqid=None)
    assert sq == 0
    assert cq == 0

    qm = QueueMgr()
    sq, cq = qm.get(sqid=None, cqid=None)
    assert sq is None
    assert cq is None


def test_queue_mgr_next_iosq_id():
    ''' def next_iosq_id(self):
    '''
    qm = QueueMgr()

    qm.next_iosq_id()

    sq = NVMeSubmissionQueue(mem_loc, 16, 64, 1, mem_address)
    cq = NVMeCompletionQueue(mem_loc, 16, 16, 1, mem_address, 0)
    qm.add(sq, cq)

    sq = NVMeSubmissionQueue(mem1_loc, 16, 64, 2, mem1_address)
    cq = NVMeCompletionQueue(mem1_loc, 16, 16, 2, mem1_address, 0)
    qm.add(sq, cq)

    assert qm.next_iosq_id() == 1
    assert qm.next_iosq_id() == 2
