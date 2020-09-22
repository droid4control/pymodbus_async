from pymodbus.exceptions import ModbusException

class TimeOutException(ModbusException):
    """ Error resulting from modbus response timeout """

    def __init__(self, string=""):
        """ Initialize the exception

        :param string: The message to append to the error
        """
        message = "[Timeout] %s" % string
        ModbusException.__init__(self, message)
