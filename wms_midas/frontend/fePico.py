import midas.client
import midas
import midas.frontend
import midas.event

import collections

from pexpect import pxssh 
import numpy as np 

from wms_midas.utilities import PicoMeasure

class PicoScope(midas.frontend.EquipmentBase):
    """
        Handles the measurements
            - can make a PicoScope measurement and create a Midas event with the data. 
            - should include start time stamp and end time stamp 
            - 
    """
    def __init__(self, client:midas.client.MidasClient):
        devName = "PicoScope"
        equip_name = "PicoScope"
    
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_POLLED
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 10
        default_common.period_ms = 500 # every half second? 

        # change to RO_RUNNING 
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        default_settings = collections.OrderedDict([  
            ("dev",devName),

        ]) 
        self.client = client 

        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common, default_settings)

        self._waiting = False 
        self._adc_updated = False 
        self._led_updated = False 
        self._stage_updated = False
        self._rotating = False 

        self._picoscope = PicoMeasure(True)
        self._picoscope.collection_time = 30 

        self.readout_func()

    def start_run(self):
        pass 

    def adc_updated(self):
        pass 
    def led_updated(self):
        pass 
    def stage_updated(self):
        pass 
    
    def poll_func(self):
        """
            Check if we're ready to make a measurement 
        """
        if self._rotating:
            return self._adc_updated and self._led_updated and self._stage_updated 
        else:
            return True 

    def readout_func(self):
        self._waiting = True 
        self._adc_updated = False 
        self._led_updated = False 
        self._stage_updated = False

        # make measurement... 
        trig, mon, rec, mond, recd = self._picoscope.measure()
        data = {
            "TRIG":trig, 
            "MONC":mon,
            "RECC":rec,
            "MOND":mond, 
            "RECD":recd 
        }
        # self.client.odb_set("/Equipment/PicoScope/Variables/Measure", data, create_if_needed=True)
        # set new target and start waiting again 
        event = midas.event.Event()

        event.create_bank("NCNT", midas.TID_INT, (trig, mon, rec, mond, recd))
        return event 
    
        
        

class fePicoScope(midas.frontend.FrontendBase):
    def __init__(self, picoscope:PicoScope):
        midas.frontend.FrontendBase.__init__(self, "fePicoScope")
        self.pico = picoscope(self.client)
        self.add_equipment(self.pico)

        # these can be changed by the user 
        #self.client.odb_watch("/Equipment/ELLxStage/Variables/destination",self.check_readout)
        #self.client.odb_watch("/Equipment/LEDBoard/Variables/adc",self.check_readout)
        #self.client.odb_watch("/Equipment/LEDBoard/Variables/LED",self.check_readout)        

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

    my_fe = fePicoScope(PicoScope)
    my_fe.run()
    print("closed")
    
