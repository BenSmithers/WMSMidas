import serial 
import time 
from contextlib import ContextDecorator
from StageControl.utils import LEDNotFound
import os 
from enum import Enum, Flag, auto

DATABIT = 8
PARITY=serial.PARITY_NONE
HANDSHAKE=False
STOP_BIT=serial.STOPBITS_ONE
BAUD = 9600

class Status(Flag):
    on = auto()
    RUP = auto()
    RDW = auto()
    OVC = auto()
    OVV = auto()
    UNV = auto()
    MAXV = auto()
    TRIP = auto()
    OVP = auto()
    RES0 = auto()
    DIS = auto()
    KILL = auto()
    ILK = auto()
    NOCAL = auto()
    RES1 = auto()
    RES2 = auto()

class Command(Enum):
    MON = 0
    SET = 1
class Param(Enum):
    STAT = 0
    BDNAME = 1
    POLARITY = 2
    VSET = 3
    VMON =4 
    ISET =5 
    IMON =6
    RUP=7
    RDW =8
    PDWN = 9
    IMRANGE =10
    TRIP = 11
    MAXV = 12
    IMAX=13
    ON = 14
    OFF = 15
DTYPE=[
    None, 
    None,
    None,
    float, 
    None,
    float, 
    None, 
    float,
    float,
    str, # RAMP/KILL
    str, # LOW/HIGH 
    float,
    None, 
    None, 
    None, 
]


class CAENBox:
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
        
    def _send_and_receive(self, command:str)->dict:
        if command[-1]!="\n":
            command = command+"\n"
        self._con.write((command ).encode())
        response = self._con.readline().decode().split(",")
        if len(response)==1:
            return {
                "state": response[0].split(":")[1] 
            }
        elif len(response)==2:
            return {
                "state": response[0].split(":")[1] ,
                "value": response[1].split(":")[1]
            }
    
    def send_command(self, command:Command, parameter:Param, value=None):
        toggle_on_off = (
            parameter.value == Param.ON.value or parameter.value==Param.OFF.value 
        )

        if command.value==Command.SET.value and (not toggle_on_off):
            if value is None:
                raise ValueError("Must specify value for {}".format(command))

            if DTYPE[parameter.value]==float:
                formatted_com = "$CMD:{},PAR:{},VAL:{:.3f}\n".format(command.name, parameter.name, value)
            elif DTYPE[parameter.value]==str:
                formatted_com = "$CMD:{},PAR:{},VAL:{}\n".format(command.name, parameter.name, value)
            else:
                raise ValueError("Cannot set value for parameter {}. That's illegal!".format(parameter.name))
        else :
            if value is not None:
                raise ValueError("Cannot specify value for command {}".format(command)) # monitor
        
            formatted_com = "$CMD:{},PAR:{}\n".format(command.name, parameter.name)

        return self._send_and_receive(formatted_com)
    
    def turn_on(self):
        return self.send_command(Command.SET, Param.ON)

    def turn_off(self):
        return self.send_command(Command.SET, Param.OFF)
    
    def read_voltage(self):
        return self.send_command(Command.MON, Param.VMON)
        
    def read_current(self):
        return self.send_command(Command.MON, Param.IMON)
    def set_voltage(self, voltage):
        if not isinstance(voltage, float):
            raise TypeError("Voltage must be float, not {}".format(type(voltage)))
        if voltage<1 or voltage>1000:
            raise ValueError("Voltage invalid: {}. Should be >1 and <1000".format(voltage))
        
        return self.send_command(Command.SET, Param.IMON, voltage)

    def read_name(self):
        return self.send_command(Command.MON, Param.BDNAME)
    def read_state(self):
        return Status(int(self.send_command(Command.MON, Param.STAT)["value"]))
    
    def read_polarity(self):
        return self.send_command(Command.MON, Param.POLARITY)
    def read_vset(self):
        return self.send_command(Command.MON, Param.VSET)
    def read_iset(self):
        return self.send_command(Command.MON, Param.ISET)
    def read_trip(self):
        return self.send_command(Command.MON, Param.TRIP)
    def set_trip(self, value):
        return self.send_command(Command.SET, Param.TRIP, value)