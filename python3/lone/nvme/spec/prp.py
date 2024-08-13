import ctypes
import math

from lone.system import DMADirection, MemoryLocation


import logging
logger = logging.getLogger('prp')


class PRP:

    def __init__(self, mem_mgr, num_bytes, mps, direction, client):
        self.mem_mgr = mem_mgr
        self.num_bytes = num_bytes
        self.mps = mps
        self.client = client

        self.prp1 = 0
        self.prp1_mem = None
        self.prp2 = 0
        self.prp2_mem = None

        self.mem_list = []

        assert num_bytes <= (2 * 1024 * 1024), 'Support for PRPs larger than 2M not implemented!'

        # How many PRPs fit in a mps sized page (-1 because the last address is
        #  a pointer to the next list)
        self.prps_per_page = (self.mps // 8) - 1

        # Calculate how many pages we need for num_bytes
        self.pages_needed = math.ceil(num_bytes / self.mps)
        assert self.pages_needed > 0, 'Pages needed cannot be 0'

        # How many list pages do we need? -1 because of PRP1
        self.lists_needed = math.ceil(
            (self.pages_needed - 1) / self.prps_per_page) if self.pages_needed > 2 else 0

        # Allocate memory
        self.alloc(direction)

    def malloc_page(self, direction, client):
        mem = self.mem_mgr.malloc(self.mps, direction, client=' '.join([self.client, client]))
        self.mem_list.append(mem)
        return mem

    def alloc(self, data_dma_direction):

        # Less than MPS, only need PRP1, no offset
        # The memory list has to be one item large enough for mps
        if self.pages_needed == 1:
            self.prp1_mem = self.malloc_page(data_dma_direction, client='prp1_only')
            self.prp1 = self.prp1_mem.iova

        # If exactly 2 * MPS, use 2 PRPs
        # The memory list has to be 2 items each large enough for 1/2 of the data
        elif self.pages_needed == 2:
            self.prp1_mem = self.malloc_page(data_dma_direction, client='prp1_prp2_1')
            self.prp1 = self.prp1_mem.iova
            self.prp2_mem = self.malloc_page(data_dma_direction, client='prp1_prp2_2')
            self.prp2 = self.prp2_mem.iova

        # We will need one or more lists
        else:
            rem_bytes = self.num_bytes

            self.prp1_mem = self.malloc_page(data_dma_direction, client='prp_list_1')
            self.prp1 = self.prp1_mem.iova
            rem_bytes -= self.mps

            # Allocate the first list element, make sure the direction is correct
            self.prp2_mem = self.malloc_page(DMADirection.HOST_TO_DEVICE, client='prp_list_2')
            self.prp2 = self.prp2_mem.iova

            # Make a pointer to the first list element so we can fill it in with pointers
            prp_list_data = (ctypes.c_uint64 * (
                self.mps // ctypes.sizeof(ctypes.c_uint64))).from_address(self.prp2_mem.vaddr)

            # Allocate all PRPs in the list
            for i in range(self.prps_per_page):

                # Allocate memory
                self.prp_segment = self.malloc_page(data_dma_direction,
                                                    client='prp_list_seg_{}'.format(i))

                prp_list_data[i] = self.prp_segment.iova
                rem_bytes -= self.mps

                if rem_bytes <= 0:
                    break
            else:
                assert False, 'Support for PRPs larger than 2M not implemented!'

    def from_address(self, prp1_address, prp2_address=0):
        ''' Returns a PRP object that starts at address, and is big enough for num_bytes.
                This assumes that a NVMe PRP starts at address and is properly formatted.
        '''

        # TODO: This is mostly untested!!!! ADD TESTS
        if self.pages_needed == 1:
            assert prp1_address != 0, (
                'Must have a PRP1 address for num_bytes {}'.format(self.num_bytes))
            self.prp1 = prp1_address
            self.prp1_mem = MemoryLocation(self.prp1, self.prp1, self.mps, 'prp.from_address')
            self.mem_list.append(self.prp1_mem)

        elif self.pages_needed == 2:
            assert prp2_address != 0, (
                'Must have a PRP2 address for num_bytes {}'.format(self.num_bytes))
            self.prp2 = prp2_address
            self.prp2_mem = MemoryLocation(self.prp2, self.prp2, self.mps, 'prp.from_address')
            self.mem_list.append(self.prp2_mem)

        else:
            assert prp1_address != 0, (
                'Must have a PRP1 address for num_bytes {}'.format(self.num_bytes))
            self.prp1 = prp1_address
            self.prp1_mem = MemoryLocation(self.prp1, self.prp1, self.mps, 'prp.from_address')
            self.mem_list.append(self.prp1_mem)

            assert prp2_address != 0, (
                'Must have a PRP2 address for num_bytes {}'.format(self.num_bytes))
            self.prp2 = prp2_address
            self.prp2_mem = MemoryLocation(self.prp2, self.prp2, self.mps, 'prp.from_address')
            self.mem_list.append(self.prp2_mem)

            # Make a pointer to the first list element so we can fill it in with pointers
            prp_list_data = (ctypes.c_uint64 * (
                self.mps // ctypes.sizeof(ctypes.c_uint64))).from_address(self.prp2_mem.vaddr)

            # Find all the segments
            for prp_segment in prp_list_data:
                if prp_segment:
                    prp_mem = MemoryLocation(prp_segment, prp_segment, self.mps, 'prp.from_address')
                    self.mem_list.append(prp_mem)

        return self

    def __str__(self):
        pages_printed = 0
        pages_to_print = self.pages_needed + self.lists_needed
        string_ret = ''

        def print_page(page):
            string_ret = ''
            string_ret += '  size:  {}\n'.format(page.size)
            string_ret += '  vaddr: 0x{:016x}\n'.format(page.vaddr)
            string_ret += '  iova:  0x{:016x}\n'.format(page.iova)
            return string_ret

        for page_index, page in enumerate(self.mem_list):

            # Print prp1
            if self.prp1 == page.iova:
                string_ret += 'PRP1: 0x{:016x}\n'.format(self.prp1)
                string_ret += print_page(page)
                pages_printed += 1

            # Print prp2
            if self.prp2 == page.iova:
                string_ret += 'PRP2: 0x{:016x}\n'.format(self.prp2)
                string_ret += print_page(page)
                pages_printed += 1
                prp_list_data = (ctypes.c_uint64 * (
                    self.mps // ctypes.sizeof(ctypes.c_uint64))).from_address(page.vaddr)

                # If it is a list print it
                for i, d in enumerate(prp_list_data):
                    string_ret += '  list[{:03d}]: 0x{:016x} 0x{:016x}\n'.format(
                        i, ctypes.addressof(prp_list_data) + (64 * i), d)
                    pages_printed += 1

                    # Are we done?
                    if pages_printed >= pages_to_print:
                        break

            # Are we done?
            if pages_printed >= pages_to_print:
                break

        return string_ret[:-1]

    def free_all_memory(self):
        for mem in self.mem_list:
            self.mem_mgr.free(mem)

    def get_data_segments(self):
        segments = []

        for page_index, page in enumerate(self.mem_list):

            # Get data from prp1
            if self.prp1 == page.iova:
                segments.append(page)

            # Get data from prp2 and lists
            if self.prp2 == page.iova:
                prp_list_data = (ctypes.c_uint64 * (
                    self.mps // ctypes.sizeof(ctypes.c_uint64))).from_address(page.vaddr)

                # If it is a list then get the data at that address
                for i, d in enumerate(prp_list_data):
                    if d != 0:
                        p = [p for p in self.mem_list if p.iova == d]
                        assert len(p) == 1, 'Something went wrong with this PRP'
                        segments.append(p[0])

            # TODO: This currently only handles one list segment

        return segments

    def get_data_buffer(self):
        data = bytearray()
        i = 0

        for segment in self.get_data_segments():
            b = (ctypes.c_uint8 * self.mps).from_address(segment.vaddr)
            data[i:i + segment.size] = b[:i + segment.size]
            i += segment.size
        return data

    def set_data_buffer(self, data):
        i = 0

        for segment in self.get_data_segments():
            b = (ctypes.c_uint8 * self.mps).from_address(segment.vaddr)

            # Truncate if we were told to set less bytes than a segment
            if (i + segment.size) > len(data):
                data_len = len(data)
            else:
                data_len = i + segment.size

            b[:data_len] = data[i:data_len]
            i += segment.size
