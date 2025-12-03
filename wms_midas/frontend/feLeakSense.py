import midas.client
import midas
import midas.frontend
import midas.event

from Phidget22.Phidget import *
from Phidget22.Devices.VoltageInput import * 


class MultiLeakSensor(midas.frontend.EquipmentBase):
    def __init__(self, client:midas.client.MidasClient,id_number, *which:int):
        self.equip_name = "LeakSense{}".format(id_number)
        self._which = which 
        self._id_number = id_number

        self.N_MAX = 6

        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 21
        default_common.period_ms = 1000 # 
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        self.client = client 

        midas.frontend.EquipmentBase.__init__(self, client, self.equip_name, default_common)

        device_serial_number = 17 # fill in later... 
        #self.client.odb_get("/Equipment/LeakSense/Settings/SerialNo")

        self.all_hubs = [None for i in range(self.N_MAX)]
        for i_hub in which:
            assert (i_hub>-1 and i_hub<self.N_MAX)
            self.all_hubs[i_hub] = VoltageInput()
            self.all_hubs[i_hub].setHubPort(i_hub)
            #self.all_hubs[i_hub].setDeviceSerialNumber(which)
        
        for i in range(len(self.all_hubs)):
            if self.all_hubs[i] is not None:
                self.all_hubs[i].openWaitForAttachment(5000)

                print(self.all_hubs[i].getDeviceSerialNumber())
    
    def readout_func(self):
        __func = PhidgetSupport.getDll().PhidgetVoltageInput_getVoltage
        __func.restype = ctypes.c_int32

        result = [False for i in range(self.N_MAX)]
        _Voltage = ctypes.c_double()
        any_of_them = False 
        for i_hub in range(self.N_MAX):

            if self.all_hubs[i_hub] is not None:
                status = __func(self.all_hubs[i_hub].handle, ctypes.byref(_Voltage))
                result[i_hub] = abs(_Voltage.value-0.0813)>0.001
                any_of_them = result[i_hub] or any_of_them
        self.client.odb_set(
            "/Equipment/{}/Variables/Leak".format(self.equip_name), result, True 
        )
        if any_of_them:
            alarm_state = self.client.odb_get("/Equipment/Automator/Variables/complex_alarms")
            # 256 and 512 are reserved for water leaks 
            new_state = 256 | int(alarm_state) 
            self.client.odb_set("/Equipment/Automator/Variables/complex_alarms", new_state)


        

class feMidasLeakLooker(midas.frontend.FrontendBase):
    def __init__(self, multileak:MultiLeakSensor):
        midas.frontend.FrontendBase.__init__(self, "feMultiLeakSensor")

        self.pico = multileak(self.client, 0, 0)
        self.add_equipment(self.pico)

        

if __name__ == "__main__":

    # We must call this function to parse the "-i" flag, so it is available
    # as `midas.frontend.frontend_index` when we init the frontend object. 
    midas.frontend.parse_args()
    
    #if index is -1 (not provided) break
    if (midas.frontend.frontend_index == -1):
        raise SystemExit("No Index Provided")
        
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.

    my_fe = feMidasLeakLooker(MultiLeakSensor)
    my_fe.run()
    print("closed")
    
