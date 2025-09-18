import midas.client
import midas
import midas.frontend
import midas.event

import collections

from wms_midas.utilities import ELLxConnection

class ELLxStageMidas(midas.frontend.EquipmentBase, ELLxConnection):
    def __init__(self, client: midas.client.MidasClient):
        devName = "ELLXStage"
        equip_name = "ELLXStage"

        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 16
        default_common.period_ms = 10000 # not really doing anything...
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        default_settings = collections.OrderedDict([  
            ("dev",devName),

        ]) 
        self.client = client 

        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        print(self.settings["USB"])
        ELLxConnection.__init__(self, self.settings["USB"])


    def readout_func(self):
        pass

    def detailed_settings_changed_func(self, path, idx, new_value):
        if path=="/Equipment/ELLXStage/Settings/dest":
            new_path = "/Equipment/ELLXStage/Variables/dest"
            self.move_absolute(new_value)
            new_destination= self.get_position()
            if isinstance(new_destination["data"], (float, int)):
                self.client.odb_set(new_path,float(new_destination["data"]),True)
            else:
                self.client.msg(str(new_destination["data"]), True)
        else: 
            self.client.msg("No handler for {}".format(path))

class feStage(midas.frontend.FrontendBase):
    def __init__(self, stagemidas:ELLxStageMidas):
        midas.frontend.FrontendBase.__init__(self, "feStageControl")
        
        self.add_equipment(stagemidas(self.client))

        # these can be changed by the user 
        #self.client.odb_watch("/Equipment/ELLXStage/Settings/dest",self.update_position)

    def update_position(self):
        pass 


if __name__ == "__main__":

    # We must call this function to parse the "-i" flag, so it is available
    # as `midas.frontend.frontend_index` when we init the frontend object. 
    midas.frontend.parse_args()
    
    #if index is -1 (not provided) break
    if (midas.frontend.frontend_index == -1):
        raise SystemExit("No Index Provided")
        
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.

    my_fe = feStage(ELLxStageMidas)
    my_fe.run()
    print("closed")
    