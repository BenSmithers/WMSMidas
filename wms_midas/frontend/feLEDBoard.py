
import midas.client
import midas
import midas.frontend
import midas.event

import collections

from wms_midas.utilities import LEDBoard

waves = ["",
    "450nm",
    "410nm",
    "365nm",
    "295nm",
    "278nm",
    "255nm",
    "235nm",
    "Align 1",
    "Align 2"
]

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
        
        if path=="/Equipment/LEDBoard/Settings/enabled":
            self.client.msg("Enabling LED" if new_value else "Disabling LED")
            self.enable() if new_value else self.disable()
        elif path=="/Equipment/LEDBoard/Settings/ADC":
            self.client.msg("Setting ADC to {}".format(new_value))
            self.set_adc(new_value)
        elif path=="/Equipment/LEDBoard/Settings/LED":
            self.activate_led(new_value) 
            self.client.msg("Activating {} LED".format(waves[new_value]))
        elif path=="/Equipment/LEDBoard/Settings/rate":
            self.set_fast_rate() if new_value else self.set_slow_rate()
            self.client.msg("Fast Rate" if new_value else "Slow Rate")
        elif path=="/Equipment/LEDBoard/Settings/IntTrigger":
            self.set_int_trigger() if new_value else self.set_ext_trigger() 
        else:
            self.client.msg("No handler for index {}".format(idx))
            return 
        newpath = path.replace("Settings", "Variables")
        self.client.odb_set(newpath,new_value,True ,resize_arrays=False)


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
    