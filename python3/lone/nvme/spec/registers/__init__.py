import ctypes
from lone.util.struct_tools import ComparableStruct


class RegsStructAccess(ComparableStruct):

    def read_data(self, get_func, offset, size_bytes):
        read_data = bytearray()
        for read_byte in range(size_bytes):
            read_data += get_func(offset).to_bytes(1, 'little')
            offset += 1
        return read_data

    def __setattr__(self, name, value):

        # If _access_.set_func is not set, just use ctypes
        #  This is how "direct access" works when the object
        #  is just in userspace memory
        if not self._access_.set_func:
            object.__setattr__(self, name, value)

        # If we are not accessing it directly, but the user requested
        #   something that is not in the _fields_ attribute, just
        #   use the regular __setattr__
        elif name not in [f[0] for f in object.__getattribute__(self, '_fields_')]:
            object.__setattr__(self, name, value)

        # User requested a field that is in _fields_, and the structure
        #   has the _access_ attribute. Use the _access_.get_func to
        #   read bytes and make up the requested return value
        else:
            # Get offset and size for the structure that contains
            #   "name". We read/modify/write below
            #   We read/modify/write below because the user may be
            #   setting an arbitraty number of bits/bytes/etc in the
            #   structure
            size_bytes = ctypes.sizeof(self.__class__)
            offset = self._base_offset_

            # Raise to debug if the offset was not set!
            if offset is None:
                raise Exception('Trying to set {} on {}, but offset is None!'.format(
                                name, self.__class__.__name__))

            # READ size_bytes from offset into a temporary bytearray, then make up an
            #   object of the type we are modifying
            read_data = self.read_data(self._access_.get_func, offset, size_bytes)
            read_obj = self.__class__.from_buffer(read_data)

            # MODIFY our read data with the new value at name
            object.__setattr__(read_obj, name, value)

            # WRITE the full structure back to the registers
            offset = self._base_offset_
            for write_byte in (ctypes.c_uint8 * size_bytes).from_address(
                    ctypes.addressof(read_obj)):
                self._access_.set_func(offset, write_byte)
                offset += 1

        if self._access_.set_notify is not None:
            self._access_.set_notify()

    def __getattribute__(self, name):

        # If _access_.get_func is not set, just use ctypes
        #  This is how "direct access" works when the object
        #  is just in userspace memory
        if not object.__getattribute__(self, '_access_').get_func:
            return object.__getattribute__(self, name)

        # If we are not accessing it directly, but the user requested
        #   something that is not in the _fields_ attribute, just
        #   use the regular __getattribute__
        elif name not in [f[0] for f in object.__getattribute__(self, '_fields_')]:
            return object.__getattribute__(self, name)

        # User requested a field that is in _fields_, and the structure
        #   has the _access_ attribute. Use the _access_.get_func to
        #   read bytes and make up the requested return value
        else:
            # Get registers offset and size for this structure
            size_bytes = ctypes.sizeof(self.__class__)
            offset = self._base_offset_

            # Raise to debug if the offset was not set!
            if offset is None:
                raise Exception('Trying to get {} on {}, but offset is None!'.format(
                                name, self.__class__.__name__))

            # READ the latest value from registers
            read_data = self.read_data(self._access_.get_func, offset, size_bytes)

            # Create an object with the read value
            data = self.__class__.from_buffer(read_data)
            value = object.__getattribute__(data, name)
            return value
