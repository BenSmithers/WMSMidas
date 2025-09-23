
import midas.client
import midas
import midas.frontend
import midas.event

import collections

from wms_midas.utilities import CAENBox
from wms_midas.utilities import Status


class HVBox(midas.frontend.EquipmentBase, CAENBox):
    def __init__(self, client: midas.client.MidasClient, which=0):
        devName = "CAENBox{}".format(which)
        self.equip_name = "CAENBox{}".format(which)
    
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 16
        default_common.period_ms = 3000 # not really doing anything...
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        self.client = client 


        midas.frontend.EquipmentBase.__init__(self, client, self.equip_name, default_common)




        CAENBox.__init__(self, self.settings["USB"])

    def readout_func(self):
        status = self.read_state()
        this_v = self.read_voltage()["value"]
        this_i = self.read_current()["value"]


        status_vector = []
        for i, name in enumerate(Status):
            status_vector.append(name in status)

        self.client.odb_set("/Equipment/{}/Variables/voltage_read".format(self.equip_name), this_v, True)
        self.client.odb_set("/Equipment/{}/Variables/current_read".format(self.equip_name), this_i, True)
        self.client.odb_set("/Equipment/{}/Variables/status".format(self.equip_name), status_vector, True)
    
    def detailed_settings_changed_func(self, path, idx, new_value):
        """
            0 - disabled / enabled
            1 - ADC
            2 - LED 
            3 - RS/RF 
            4 - TI/TE 
        """
        
        if path=="/Equipment/{}/Settings/enabled".format(self.equip_name):
            self.client.msg("Enabling HV" if new_value else "Disabling HV")
            self.turn_on() if new_value else self.turn_off()
        elif path=="/Equipment/{}/Settings/voltage".format(self.equip_name):
            self.set_voltage(new_value)
        elif path=="/Equipment/{}/Settings/USB".format(self.equip_name):
            self.client.msg("USB Port changed - restart HV frontend")
        else:
            self.client.msg("No handler for path {}".format(path))
            return 


class feHVBox(midas.frontend.FrontendBase):
    def __init__(self, hvmidas:HVBox):
        midas.frontend.FrontendBase.__init__(self, "feHVBox")
        
        self.add_equipment(hvmidas(self.client, 0))
        self.add_equipment(hvmidas(self.client, 1))

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

    my_fe = feHVBox(HVBox)
    my_fe.run()
    print("closed")
    