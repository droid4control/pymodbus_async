from pymodbus.client.asynchronous.serial import AsyncModbusSerialClient as OriginalAsyncModbusSerialClient

from pymodbus.client.asynchronous import schedulers
from pymodbus.client.asynchronous.thread import EventLoopThread

def async_io_loop_factory(port=None, framer=None, **kwargs):
    from tornado.ioloop import IOLoop
    from pymodbus_async.client.asynchronous.tornado import (AsyncModbusSerialClient as Client)
    ioloop = IOLoop()
    protocol = EventLoopThread("ioloop", ioloop.start, ioloop.stop)
    protocol.start()
    client = Client(port=port, framer=framer, ioloop=ioloop, **kwargs)
    future = client.connect()
    return protocol, future

class AsyncModbusSerialClient(OriginalAsyncModbusSerialClient):
    def __new__(cls, scheduler, method, port,  **kwargs):
        if scheduler != schedulers.IO_LOOP:
            return super().__new__(cls)
        framer = cls._framer(method)
        yieldable = async_io_loop_factory(framer=framer, port=port, **kwargs)
        return yieldable
