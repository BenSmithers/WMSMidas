import midas.client
import midas
import midas.frontend
import midas.event

import collections

from pexpect import pxssh 
import numpy as np 
import time 
import ast 

from wms_midas.utilities import HOST, USER, PASSWORD, PORT, KEY

class PumpConnection(midas.frontend.EquipmentBase):
    def __init__(self, client:midas.client.MidasClient):
        devName = "PumpConnection"
        equip_name = "PumpConnection"

        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 11
        default_common.period_ms = 2000 # every two seconds? 
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        default_settings = collections.OrderedDict([  
            ("dev",devName),
            ("BallValve", [0,0,0,0,0,0]),
            ("Solenoid", [0,0,0]),
            ("Pump", [0,0,0]),
        ]) 
        self.client = client 

        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common, default_settings)

        self._initialized = False
        self.initialize()        

        self._state = 0 
        """
            0 - idle 
        """
        self._substate = 0 
        """
            0:0 - idle 
        """

        self._pumps = [False, False, False]
        self._svs = [False, False, False]
        self._bvs = [False, False, False, False, False, False]

    def initialize(self):
        self._initialized = True 
        self._connection = pxssh.pxssh() 
        self._connection.login(
            server = HOST,
            username = USER,
            ssh_key=KEY,
            #password = PASSWORD,
            auto_prompt_reset=False
        ) 
        self.client.msg("changing to labview folder")
        self._connection.set_unique_prompt()

        self.send_receive("cd wmsLabview")
        self.client.msg("starting wms_main\n")

        self.send_receive("ps aux | grep -ie wms_main | awk '{print $2}' | xargs kill -9")

        self.send_receive("python3 wms_main.py")
        self.client.msg("started!\n")

    def send_receive(self, what):
        self._connection.sendline(what)
        success = self._connection.prompt()
        if not success:
            self.client.msg("Timeout waiting for response to {}\n".format(what), is_error = True)
        # get response, split by carriage return 
        raw = self._connection.before.decode('UTF-8').split("\r")
        return raw
    
    def readout_func(self):
        self._connection.sendline("data")
        success = self._connection.prompt()
        if not success:
            self.client.msg("Timeout waiting for response to data request\n", is_error=True)
        
        raw_response = self._connection.before.decode('UTF-8').split("\r")
        try:
            
            raw_data = raw_response[-2]


            data_list = ast.literal_eval(raw_data.strip())
            pressure = np.array([row[0] for row in data_list[1:]])
            flow = np.array([row[1] for row in data_list[1:]]).astype(bool).astype(int)
            temperature = np.array([row[2] for row in data_list[1:]])
            waterlevel = np.array([row[4] for row in data_list[1:]])
            light = np.array([row[5] for row in data_list[1:]])
            #raise NotImplementedError("Add data parser!")
            ret_dat = {
                "flow":flow,
                "pressure":pressure,
                "temperature":temperature,
                "waterlevel":(waterlevel>0.5).astype(int),
                "light":light
            }   

            self.client.odb_set("/Equipment/PumpConnection/Variables/Sensors", ret_dat, create_if_needed=True)
            event = midas.event.Event()
            for key in ret_dat:
                if key=="waterlevel":
                    event.create_bank(
                        key[:4].upper(), midas.TID_INT, ret_dat[key]
                    )
                else:
                    event.create_bank(
                        key[:4].upper(), midas.TID_FLOAT, ret_dat[key]
                    )
            return event
        
        except Exception as e:
            self.client.msg("Failed to parse response {}\n".format(e), is_error=True) 

    def set_pump(self, number, value):
        message = "pu{} {}".format(
            number+1, "on" if value else "off"
        )
        self.send_receive(message)
        self.client.msg(message)
    def set_sv(self, number, value):
        message = "sv{} {}".format(
            number+1, "on" if value else "off"
        )
        self.send_receive(message)
        self.client.msg(message)
    def set_bv(self, number, value):
        message = "bv{} {}".format(
            number+1, "on" if value else "off"
        )
        self.send_receive(message)
        self.client.msg(message)

    def detailed_settings_changed_func(self, path, idx, new_value):
        
        if path=="/Equipment/PumpConnection/Settings/Pump":
            self.set_pump(idx, new_value) 
        elif path=="/Equipment/PumpConnection/Settings/Solenoid":
            self.set_sv(idx, new_value)  
        elif path=="/Equipment/PumpConnection/Settings/BallValve":
            self.set_bv(idx, new_value) 
        else:
            self.client.msg("No handler for {}".format(path))

class feWMSPump(midas.frontend.FrontendBase):
    def __init__(self, PumpCon):
        midas.frontend.FrontendBase.__init__(self, "feWMSBench")
        
        self.add_equipment(PumpCon(self.client))

        # these can be changed by the user 
        #self.client.odb_watch("/Equipment/PumpConnection/Settings/pumpstate",self.update_pumps)
        #self.client.odb_watch("/Equipment/PumpConnection/Settings/svstate",self.update_sv)
        #self.client.odb_watch("/Equipment/PumpConnection/Settings/bvstate",self.update_bv)


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

    my_fe = feWMSPump(PumpConnection)
    my_fe.run()
    print("closed")
    