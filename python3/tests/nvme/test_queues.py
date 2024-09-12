import pytest
import ctypes

from lone.nvme.spec.queues import NVMeHeadTail, NVMeQueue, NVMeSubmissionQueue, NVMeCompletionQueue
from lone.nvme.spec.queues import QueueMgr

# Generic memory location for tests below
mem = (ctypes.c_uint8 * 4096)()
mem_address = ctypes.addressof(mem)

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


def test_nvme_head_tail_add():
    ''' def add(self, num):
    '''
    nht = NVMeHeadTail(10, mem_address)
    nht.set(1)

    nht.add(1)
    assert nht.value == 2

    nht.add(3)
    assert nht.value == 5

    #TODO check where used, but in wrapping, do we really need add AND incr?
    nht.add(6)
    assert nht.value == 1

def test_nvme_head_tail_incr():
    ''' def incr(self, num):
    '''
    pass


def test_nvme_head_tail_value():
    ''' def value(self):
    '''
    pass


####################################################################################################
# NVMeQueue tests
####################################################################################################
def test_nvme_queue_init():
    ''' def __init__(self, base_address, entries, entry_size, qid, dbh_addr, dbt_addr):
    '''
    pass


def test_nvme_queue_is_full():
    ''' def is_full(self):
    '''
    pass


def test_nvme_queue_num_entries():
    ''' def num_entries(self):
    '''
    pass


####################################################################################################
# NVMeSubmissionQueue tests
####################################################################################################
def test_nvme_subq_init():
    ''' def __init__(self, base_address, entries, entry_size, qid, dbt_addr):
    '''
    pass


def test_nvme_subq_post_command():
    ''' def post_command(self, command):
    '''
    pass


def test_nvme_subq_get_command():
    ''' def get_command(self):
    '''
    pass


####################################################################################################
# NVMeCompletionQueue tests
####################################################################################################
def test_nvme_cmpq_init():
    ''' def __init__(self, base_address, entries, entry_size, qid, dbh_addr, int_vector=None):
    '''
    pass


def test_nvme_cmpq_get_next_completion():
    ''' def get_next_completion(self):
    '''
    pass


def test_nvme_cmpq_consume_completion():
    ''' def consume_completion(self):
    '''
    pass


def test_nvme_cmpq_post_completion():
    ''' def post_completion(self, cqe):
    '''
    pass


####################################################################################################
# QueueMgr tests
####################################################################################################
def test_queue_mgr_init():
    ''' def __init__(self):
    '''
    pass


def test_queue_mgr_add():
    ''' def add(self, sq, cq):
    '''
    pass


def test_queue_mgr_remove_cq():
    ''' def remove_cq(self, rem_cqid):
    '''
    pass


def test_queue_mgr_remove_sq():
    ''' def remove_sq(self, rem_sqid):
    '''
    pass


def test_queue_mgr_get_cqs():
    ''' def get_cqs(self):
    '''
    pass


def test_queue_mgr_all_cqids():
    ''' def all_cqids(self):
    '''
    pass


def test_queue_mgr_all_cq_vectors():
    ''' def all_cq_vectors(self):
    '''
    pass


def test_queue_mgr_get():
    ''' def get(self, sqid=None, cqid=None):
    '''
    pass


def test_queue_mgr_next_iosq_id():
    ''' def next_iosq_id(self):
    '''
    pass
