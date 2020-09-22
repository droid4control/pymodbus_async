"""
Implementation of a Modbus Client Using Tornado
-----------------------------------------------

Tested with:
    tornado 4.5.2
    pymodbus 2.4.0

"""

from tornado.ioloop import IOLoop
from pymodbus.client.asynchronous import schedulers
from pymodbus_async.client.asynchronous.serial import AsyncModbusSerialClient


if __name__ == "__main__":
    def read_async():
        _, f = AsyncModbusSerialClient(schedulers.IO_LOOP, method='rtu', stopbits=1, bytesize=8, parity='E', baudrate=19200, timeout=1, port='/dev/ttyUSB0')
        f.add_done_callback(_on_connect)

    def _on_connect(future):
        client = future.result()
        _send_request(client)

    def _send_request(client):
        f = client.read_holding_registers(address=0, count=1, unit=1)
        f.add_done_callback(_on_done)

    def _on_done(f):
        val = f.result()
        exc = f.exception()
        if exc:
            print("ERROR: %s" % str(exc))
        else:
            if hasattr(val,  "bits"):
                t = val.bits
            elif hasattr(val, "registers"):
                t = val.registers
            else:
                t = val
            print(f"register = {t}")
        IOLoop.instance().stop()

    read_async()
    IOLoop.instance().start()
