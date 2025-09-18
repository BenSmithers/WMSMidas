import serial 
import time 
from contextlib import ContextDecorator
import os 

DATABIT = 8
PARITY=serial.PARITY_NONE
HANDSHAKE=False
STOP_BIT=serial.STOPBITS_ONE

BAUD = 115200

class LEDNotFound(Exception):
    pass 

class LEDBoard:
    """
        opens and manages a connection with an LED flasher board 
    """
    def __init__(self, usb_interface, fake=False ):
        self._fake = fake 
        if not self._fake:
            if not os.path.exists(usb_interface):
                raise LEDNotFound("Could not find LED board!")
            self._con = serial.Serial(usb_interface, baudrate=BAUD, parity=PARITY, bytesize=DATABIT, stopbits=STOP_BIT)
        time.sleep(1)
    def __del__(self):
        self.disable()
        self._con.close()
        
    def send_generic(self, message):
        self._con.write((message ).encode("ASCII"))
        return self._con.readline()
    
    def set_int_trigger(self):
        if not self._fake:
            self._con.write("TI".encode())
        return "TI"
    def set_ext_trigger(self):
        if not self._fake:
            self._con.write("TE".encode())
        return "TE"
    def set_fast_rate(self):
        if not self._fake:
            self._con.write("RF".encode())
        return "RF"
    
    def set_slow_rate(self):
        if not self._fake:
            self._con.write("RS".encode())
        return "RS"

    def set_adc(self, value:int):
        if not isinstance(value, int):
            raise TypeError("`which` must be an integer; found {}".format(type(which)))
        if value<0 or value>1023:
            raise ValueError("Invalid no {}".format(value))

        msg = "S{0:04d}".format(value)
        
        if not self._fake:
            for letter in msg:
                self._con.write(bytes(letter, 'ascii'))
                time.sleep(0.25)
        return "LED -- {}".format(msg)
    
    def activate_led(self, which:int):
        if not isinstance(which, int):
            raise TypeError("`which` must be an integer; found {}".format(type(which)))
        if which<1 or which>9:
            raise ValueError("Invalid no {}".format(which))
        msg = "L{}".format(which).encode("ASCII")
        if not self._fake:
            self._con.write(msg)
        return "LED -- {}".format(msg.decode())
    
    def led_off(self):
        msg = "L0".encode()
        if not self._fake:
            self._con.write(msg)
            self._con.readline()
        return "LED -- {}".format(msg.decode())
    def enable(self, *args):
        if not self._fake:
            self._con.write("E".encode())
        time.sleep(1)
        return "LED -- enable\n"
        
    def disable(self, *args):
        if not self._fake:
            self._con.write("L0\n".encode())
            self._con.write("D\n".encode())
    def __enter__(self, *args):
        self.enable()
    def __exit__(self, *args):
        self.disable()
