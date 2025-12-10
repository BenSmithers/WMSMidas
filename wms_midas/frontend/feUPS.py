import midas.client
import midas
import midas.frontend

from wms_midas.utilities import UPS

class UPSEquipment(midas.frontend.EquipmentBase, UPS):
    def __init__(self, client: midas.client.MidasClient):
        devName = "UPS"
        self.equip_name = "UPS"
    
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 22
        default_common.period_ms = 1000 # 
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        self.client = client 
        

        midas.frontend.EquipmentBase.__init__(self, client, self.equip_name, default_common)
        UPS.__init__(self)

    def readout_func(self):
        hid_data = self.read_status()
        self.client.odb_set("/Equipment/UPS/Variables/ac_on", [hid_data["on_ac"], ])



class feUPSMon(midas.frontend.FrontendBase):
    def __init__(self, ups_eq:UPSEquipment):
        midas.frontend.FrontendBase.__init__(self, "feUPS")
        
        self.add_equipment(ups_eq(self.client))

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

    my_fe = feUPSMon(UPSEquipment)
    my_fe.run()
    