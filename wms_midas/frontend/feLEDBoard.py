
import midas.client
import midas
import midas.frontend
import midas.event

import collections

from wms_midas.utilities import LEDBoard

class LEDMidas(midas.frontend.EquipmentBase, LEDBoard):
    def __init__(self, client: midas.client.MidasClient):
        devName = "LEDBoard"
        equip_name = "LEDBoard"
    
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 16
        default_common.period_ms = 10000 # not really doing anything...
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        self.client = client 

        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)

        LEDBoard.__init__(self,self.settings["USB"])

    def readout_func(self):
        return None 
    
    def detailed_settings_changed_func(self, path, idx, new_value):
        """
            0 - disabled / enabled
            1 - ADC
            2 - LED 
            3 - RS/RF 
            4 - TI/TE 
        """
        if path=="/Equipment/LEDBoard/Settings/configuration":
            if idx==0:
                self.enable() if new_value else self.disable()
            elif idx==1:
                self.set_adc(new_value)
            elif idx==2:
                self.activate_led(new_value)
            elif idx==3:
                self.set_fast_rate() if new_value else self.set_slow_rate()
            elif idx==4:
                self.set_int_trigger() if new_value else self.set_ext_trigger()
            else:
                self.client.msg("No handler for index {}".format(idx))
                return 
            
            new_path = "/Equipment/LEDBoard/Variables/configuration"
            self.client.odb_set(new_path+"[{}]".format(idx),new_value,False ,resize_arrays=False)
        else:
            self.client.msg("No handler for {}".format(path))


class feLEDBoard(midas.frontend.FrontendBase):
    def __init__(self, ledmidas:LEDMidas):
        midas.frontend.FrontendBase.__init__(self, "feLEDBoard")
        
        self.add_equipment(ledmidas(self.client))

    def begin_of_run(self, run_number):
        self.set_all_equipment_status("Running", "greenLight")
        self.client.msg("Frontend has seen start of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]
        
    def end_of_run(self, run_number):
        self.set_all_equipment_status("Finished", "greenLight")
        self.client.msg("Frontend has seen end of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]



if __name__ == "__main__":

    # We must call this function to parse the "-i" flag, so it is available
    # as `midas.frontend.frontend_index` when we init the frontend object. 
    midas.frontend.parse_args()
    
    #if index is -1 (not provided) break
    if (midas.frontend.frontend_index == -1):
        raise SystemExit("No Index Provided")
        
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.

    my_fe = feLEDBoard(LEDMidas)
    my_fe.run()
    print("closed")
    