"""
    I want this to run separately from the pump control 

    It will be called periodically (every three seconds?)
    and then check on all of the PumpControl variables. 
    These will influence its actions

    Automation Steps and Statuses (State and Substates)
    
    state_change_time 
    substate_change_time 
scr
    0 - Idle
        0 - No substates, just idle. 
    
    1 - Draining, exclusive 
        0 - Run pump 2, actively draining 
    
    2 - Drain then Refill 

        While Draining, states are: 

        10 - Filling with Supply, no filter
        11 - Filling with Supply, 1um/charcoal
        12 - Filling with Supply, UV Lamp
        13 - Filling with Supply, 1um/Charcoal + UV 
        14 - Filling with Supply, Ion filter
        15 - Filling with Supply, 1um/Charcoal + Ion Filter 
        16 - Filling with supply, UV + Ion Filter 
        17 - Filling with supply, 1um/Charcoal + UV + Ion Filter 

        20 - Filling with Return, no filter
        21 - Filling with Return, 1um/charcoal
        22 - Filling with Return, UV Lamp
        23 - Filling with Return, 1um/Charcoal + UV 
        24 - Filling with Return, Ion filter
        25 - Filling with Return, 1um/Charcoal + Ion Filter 
        26 - Filling with Return, UV + Ion Filter 
        27 - Filling with Return, 1um/Charcoal + UV + Ion Filter 

        31 - Pressurizing 
        32 - Filling RO Tank 
        33 - Filling Chamber 
        34 - Bleeding RO Tank 

        While filling, add 128 to minor state 

    3 - Refilling on a schedule 
        0 - Run pump 2, actively draining
        1 - Waiting to pump again 

        10-34 shared with state 2 
        

    4 - Continuous passive flow
        10-34 shared with state 2; pump only on for RO 

    5 - Continuous pumped flow 
        in principle these might need a "waiting state"

        1 - Pause required before resuming flow 

        10-27 shared with state 2; pump on regardless of source 

    6 - Smart Pumped Flow 
        Same as 4 or 5, but pump only on for return water 

"""

import midas.client
import midas
import midas.frontend
import midas.event

import numpy as np 
import collections
import time 

class Automator(midas.frontend.EquipmentBase):
    def __init__(self, client:midas.client.MidasClient):
        devName = "Automator"
        equip_name = "Automator"
        
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 11
        default_common.period_ms = 2250 # every two seconds? 
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        self._drain_ticks = 5
        self._overflow_ticks = 5

        default_settings = collections.OrderedDict([  
            ("dev",devName),
            ("state_major", 0),
            ("state_minor", 0)
        ]) 

        self.client = client 
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common, default_settings)

    def clear_state(self):
        self.client.msg("Exiting Automation")
        self.client.odb_set("Equipment/Automator/Settings/state_major", 0, False)
        self.client.odb_set("Equipment/Automator/Settings/state_minor", 0, False)
        self.client.odb_set("/Equipment/Automator/Variables/counter", 0)

    def disable_all(self):
        # disable all pumps, solenoid valves, and ball valves 
        if self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[0]"): self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[0]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[1]"): self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[1]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[2]"): self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[2]", 0)

        if self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[0]"): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[0]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[1]"): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[1]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[2]"): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[2]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[3]"): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[3]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[4]"): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[4]", 0)
        if self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[5]"): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[5]", 0)

        if self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[0]"): self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[0]", 0)        
        if self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[1]"): self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[1]", 0)      
        if self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[2]"): self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[2]", 0)      
        

    def readout_func(self):
        """
            Progress the automator 
        """
        major_state = self.settings["state_major"]
        minor_state = self.settings["state_minor"]

        is_draining = major_state==1 or (major_state==2 and minor_state<128) or (major_state==3 and minor_state<128)

        if major_state==0:
            """
            Do some simple checks against danger
            """
            return 
        
        elif is_draining: # we are draining 
            drain_pump = self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[1]")
            if drain_pump!=1: 
                # just starting - set turn the pump on. Set the counter to zero
                self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[1]", 1)
                self.client.odb_set("/Equipment/Automator/Variables/counter", 0)
            else: 
                counter_value = self.client.odb_get("/Equipment/Automator/Variables/counter")

                if counter_value>=self._drain_ticks:
                    # disable pump, disable automation 
                    if major_state==1:
                        self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[1]", 0)
                    else:
                        # we shift the minor state up by 128
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 128, False)
                        self.client.odb_set("/Equipment/Automator/Variables/counter", 0)
                        self.client.msg("Beginning to Fill Chamber")

                    
                else:
                    self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)
        elif major_state==2: # actively filling! 
            counter_value = self.client.odb_get("/Equipment/Automator/Variables/counter")

            overflow = bool(self.client.odb_get("/Equipment/PumpConnection/Settings/Flow[2]"))
            input_pump_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[0]")
            sv1_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[0]")
            sv2_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[0]")
            bv1_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[0]")
            bv2_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[1]")
            bv3_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[2]")
            bv4_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[3]")
            bv6_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[5]")

            if not sv1_state:
                self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[0]", 1)
            if not sv2_state:
                self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[1]", 1)

            if not input_pump_state:
                # turn it on... 
                self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[0]", 1)


            # determine desired settings based on micro state 
            # the first 128 are reserved for draining
            filter_number = minor_state - 128 
            supply_water = filter_number<20 
            return_water = filter_number<30 and not supply_water
            reverse_osmosis = (not supply_water) and not(return_water)

            if supply_water:
                shift = 10
            elif return_water:
                shift = 20
            else:
                shift = 30

            if supply_water or return_water:
                micro_charcoal = (filter_number - shift) % 1 == 1
                if ((not bv2_state) and micro_charcoal) or ((bv2_state) and (not micro_charcoal)):
                    self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[1]", int(micro_charcoal))

                uv_lamp = (filter_number - shift) % 2 == 2
                if ((not bv3_state) and uv_lamp) or (bv3_state and (not uv_lamp)):
                    self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[2]", int(uv_lamp))

                ion_filter = (filter_number - shift) % 4 == 4
                if ((not bv4_state) and ion_filter) or (bv4_state and (not ion_filter)):
                    self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[3]", int(ion_filter))
                
                # bv 6 should only be turned on after a little bit 
                # we wait 10 counts
                if counter_value<10:
                    self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)
                else:
                    if not bv6_state:
                        self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[5]", 1)

                    # water may be overflowing -  meaning the chamber is full
                    if overflow:
                        if counter_value>self._overflow_tick:
                            # we have finished filling! 
                            self.clear_state()
                            self.disable_all()
                        self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)


                    else: # if it's not overflowing, keep the counter at 10 
                        self.client.odb_set("/Equipment/Automator/Variables/counter",10)
        else:
            self.client.msg("Unrecognized states: {} and {}".format(major_state, minor_state), True)
            self.clear_state()


        


class feAutomation(midas.frontend.FrontendBase):
    def __init__(self, frontend_name):
        midas.frontend.FrontendBase.__init__(self, "feAutomation")
        self.add_equipment(frontend_name(self.client))


if __name__ == "__main__":

    # We must call this function to parse the "-i" flag, so it is available
    # as `midas.frontend.frontend_index` when we init the frontend object. 
    midas.frontend.parse_args()
    
    #if index is -1 (not provided) break
    if (midas.frontend.frontend_index == -1):
        raise SystemExit("No Index Provided")
        
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.

    my_fe = feAutomation(Automator)
    my_fe.run()
    print("closed")
    