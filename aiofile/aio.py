import os
from typing import Union

import asyncio

try:
    from .posix_aio import IO_NOP, IO_WRITE, IO_READ, AIOOperation
except ImportError:
    from .thread_aio import IO_READ, IO_WRITE, IO_NOP, ThreadedAIOOperation as AIOOperation


def mode_to_flags(mode: str):
    if len(set("awrb+") | set(mode)) > 5:
        raise ValueError('Invalid mode %s' % repr(mode))

    if len(set(mode) & set("awr")) > 1:
        raise ValueError('must have exactly one of create/read/write/append mode')

    flags = 0
    flags |= os.O_NONBLOCK

    if '+' in mode:
        flags |= os.O_CREAT
    if "a" in mode:
        flags |= os.O_RDWR
        flags |= os.O_APPEND
    elif "w" in mode:
        flags |= os.O_RDWR
    elif "r" in mode:
        flags |= os.O_RDONLY

    return flags


class AIOFile:
    __slots__ = '__fileno', '__fname', '__mode', '__access_mode', '__loop'

    OPERATION_CLASS = AIOOperation
    IO_READ = IO_READ
    IO_WRITE = IO_WRITE
    IO_NOP = IO_NOP

    def __init__(self, filename: str, mode: str="r", access_mode: int=0o644, loop=None):
        self.__loop = loop or asyncio.get_event_loop()
        self.__fname = filename
        self.__mode = mode
        self.__access_mode = access_mode

        self.__fileno = os.open(
            self.__fname,
            flags=mode_to_flags(self.__mode),
            mode=self.__access_mode
        )

    def __repr__(self):
        return "<AIOFile: %r>" % self.__fname

    def close(self):
        if self.__fileno == -2:
            return

        os.close(self.__fileno)
        self.__fileno = -2

    def fileno(self):
        return self.__fileno

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()

    def read(self, size: int=-1, offset: int=0, priority: int=0):
        if size < -1:
            raise ValueError("Unsupported value %d for size" % size)

        if size == -1:
            size = os.stat(self.__fileno).st_size

        return self.OPERATION_CLASS(self.IO_READ, self.__fileno, offset, size, priority, self.__loop)

    def write(self, data: Union[str, bytes], offset: int=0, priority: int=0):
        if isinstance(data, str):
            bytes_data = data.encode()
        elif isinstance(data, bytes):
            bytes_data = data
        else:
            raise ValueError("Data must be str or bytes")

        op = self.OPERATION_CLASS(self.IO_WRITE, self.__fileno, offset, len(bytes_data), priority, self.__loop)
        op.buffer = bytes_data
        return op

    def fsync(self, priority: int=0):
        return self.OPERATION_CLASS(self.IO_NOP, self.__fileno, 0, 0, priority, self.__loop)