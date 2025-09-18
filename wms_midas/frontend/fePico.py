import midas.client
import midas
import midas.frontend
import midas.event

import collections

from pexpect import pxssh 
import numpy as np 
import time 
import ast 

from wms_midas.utilities import HOST, USER, PASSWORD, PORT, KEY, PicoMeasure

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
        #default_common.period_ms = 2000 # every two seconds? 
        default_common.read_when = midas.RO_RUNNING
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

        self._picoscope = PicoMeasure(True)
        self._picoscope.collection_time = 30 

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
        return self._adc_updated and self._led_updated and self._stage_updated 

    def readout_func(self):
        self._waiting = True 
        self._adc_updated = False 
        self._led_updated = False 
        self._stage_updated = False

        # make measurement... 

        # set new target and start waiting again 

class fePicoScope(midas.frontend.FrontendBase):
    def __init__(self, picoscope:PicoScope):
        midas.frontend.FrontendBase.__init__(self, "feButtonManager")
        self.pico = picoscope(self.client)
        self.add_equipment(self.pico)

        # these can be changed by the user 
        self.client.odb_watch("/Equipment/ELLxStage/Variables/destination",self.check_readout)
        self.client.odb_watch("/Equipment/LEDBoard/Variables/adc",self.check_readout)
        self.client.odb_watch("/Equipment/LEDBoard/Variables/LED",self.check_readout)        

    def begin_of_run(self, run_number):
        self.set_all_equipment_status("Running", "greenLight")
        self.client.msg("Frontend has seen start of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]
        
    def end_of_run(self, run_number):
        self.set_all_equipment_status("Finished", "greenLight")
        self.client.msg("Frontend has seen end of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]

