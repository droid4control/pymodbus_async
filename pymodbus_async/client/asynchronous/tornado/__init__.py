import time

import logging
LOGGER = logging.getLogger(__name__)

from tornado import gen
from tornado.ioloop import IOLoop

from pymodbus.exceptions import ModbusIOException
from pymodbus.constants import Defaults
from pymodbus.utilities import hexlify_packets, ModbusTransactionState

from pymodbus.client.asynchronous.tornado import AsyncModbusSerialClient, BaseTornadoSerialClient

from pymodbus.exceptions import ModbusIOException
from pymodbus_async.exceptions import TimeOutException

class FixedAsyncModbusSerialClient(BaseTornadoSerialClient):
    state = ModbusTransactionState.IDLE
    _last_frame_end = 0.0
    timeout_handle = None

    def execute(self, request=None):
        """
        Executes a transaction
        :param request: Request to be written on to the bus
        :return:
        """
        request.transaction_id = self.transaction.getNextTID()

        def _clear_timer():
            LOGGER.debug("_clear_timer()")
            if self.timeout_handle:
                self.io_loop.remove_timeout(self.timeout_handle)
                self.timeout_handle = None

        def _on_timeout():
            LOGGER.warning("timeout")
            _clear_timer()
            if self.stream:
                self.io_loop.remove_handler(self.stream.fileno())
            self.framer.resetFrame()
            transaction = self.transaction.getTransaction(request.transaction_id)
            if self.state != ModbusTransactionState.IDLE:
                self.state = ModbusTransactionState.IDLE
                if self.stream:
                    try:
                        waiting = self.stream.connection.in_waiting
                        if waiting:
                            result = self.stream.connection.read(waiting)
                            LOGGER.info(
                                "Cleanup recv buffer after timeout: " + hexlify_packets(result))
                    except OSError as ex:
                        self.close()
                        if transaction:
                            transaction.set_exception(ModbusIOException(ex))
                        return
            if transaction:
                transaction.set_exception(TimeOutException())

        def _on_write_done(*args):
            LOGGER.debug("frame sent, waiting for a reply")
            self.last_frame_end = round(time.time(), 6)
            self.state = ModbusTransactionState.WAITING_FOR_REPLY
            self.io_loop.add_handler(self.stream.fileno(), _on_receive, IOLoop.READ)

        def _on_receive(fd, events):
            LOGGER.debug("_on_receive: %s, %s", fd, events)

            try:
                waiting = self.stream.connection.in_waiting
                if waiting:
                    LOGGER.debug("waiting = %d", waiting)
                    data = self.stream.connection.read(waiting)
                    LOGGER.debug(
                        "recv: " + hexlify_packets(data))
            except OSError as ex:
                _clear_timer()
                self.close()
                self.transaction.getTransaction(request.transaction_id).set_exception(ModbusIOException(ex))
                return

            self.framer.addToFrame(data)

            # check if we have regular frame or modbus exception
            fcode = self.framer.decode_data(self.framer.getRawFrame()).get("fcode", 0)
            if fcode and (
                  (fcode > 0x80 and len(self.framer.getRawFrame()) == exception_response_length)
                or
                  (len(self.framer.getRawFrame()) == expected_response_length)
            ):
                _clear_timer()
                self.io_loop.remove_handler(fd)
                self.state = ModbusTransactionState.IDLE
                self.framer.processIncomingPacket(
                    b'',            # already sent via addToFrame()
                    self._handle_response,
                    0,              # don't care for `single=True`
                    single=True,
                    tid=request.transaction_id
                )

        LOGGER.debug("set timeout for %f sec", self.timeout)
        self.timeout_handle = self.io_loop.add_timeout(time.time() + self.timeout, _on_timeout)

        response_pdu_size = request.get_response_pdu_size()
        expected_response_length = self.transaction._calculate_response_length(response_pdu_size)
        LOGGER.debug("expected_response_length = %d", expected_response_length)
        exception_response_length = self.transaction._calculate_exception_length() # TODO: this does not change

        packet = self.framer.buildPacket(request)
        LOGGER.debug("send: " + hexlify_packets(packet))
        self.state = ModbusTransactionState.SENDING
        f = self._build_response(request.transaction_id)
        self._sendPacket(packet, callback=_on_write_done)
        return f

    def _sendPacket(self, message, callback):
        """
        Sends packets on the bus with 3.5char delay between frames
        :param message: Message to be sent over the bus
        :return:
        """
        @gen.coroutine
        def sleep(timeout):
            yield gen.sleep(timeout)

        try:
            waiting = self.stream.connection.in_waiting
            if waiting:
                result = self.stream.connection.read(waiting)
                LOGGER.info(
                    "Cleanup recv buffer before send: " + hexlify_packets(result))
        except OSError as e:
            self.transaction.getTransaction(request.transaction_id).set_exception(ModbusIOException(e))
            return

        start = time.time()
        if self.last_frame_end:
            waittime = self.last_frame_end + self.silent_interval - start
            if waittime > 0:
                LOGGER.debug("Waiting for 3.5 char before next send - %f ms", waittime)
                sleep(waittime)

        self.stream.write(message, callback)

class AsyncModbusSerialClient(FixedAsyncModbusSerialClient, AsyncModbusSerialClient):
    state = ModbusTransactionState.IDLE
    silent_interval = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = kwargs.get('timeout', Defaults.Timeout)
        self.last_frame_end = 0.0
        self.baudrate = kwargs.get('baudrate', Defaults.Baudrate)
        if self.baudrate > 19200:
            self.silent_interval = 1.75 / 1000  # ms
        else:
            self._t0 = float((1 + 8 + 2)) / self.baudrate
            self.silent_interval = 3.5 * self._t0
        self.silent_interval = round(self.silent_interval, 6)
