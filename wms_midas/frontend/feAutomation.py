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

    10 - explicit stop! 

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
        default_common.event_id = 17
        default_common.period_ms = 2500 # every two seconds? 
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 60 #NOT SURE IF THIS MUST BE UNIQUE 

        self._drain_ticks = 5
        self._overflow_ticks = 5
        self._pump_worry_ticks = 0
        self._pressure_worry_ticks = 0

        self.client = client 
        self._running = False 
        self._rotating_waves = False 
        self._waiting_for_event = False 
        self._refill_period = -1 
        self._waiting_for_led_stage = False 
        self._last_fill_time = -1 

        self._rotation_indexer = -1 
        self._rotation_steps = [1, 2, 3, 4, 5, 6, 7, -1]
        self._rotation_steps = [2, 3, 4, 5, -1]

        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)

        self.buffer_handle = self.client.open_event_buffer("SYSTEM")
        self.request_id = client.register_event_request(self.buffer_handle, event_id=19)

    def run_start(self, run_no):
        self._running = True
        self._waiting_for_event = False
        self._rotation_indexer = -1 
        auto_refill = self.client.odb_get("/Equipment/Automator/Settings/auto_refill")
        auto_circulate = self.client.odb_get("/Equipment/Automator/Settings/auto_circulate")
        self._rotating_waves = self.client.odb_get("/Equipment/Automator/Settings/rotate_waves")
        self._refill_period = self.client.odb_get("/Equipment/Automator/Settings/refill_period")

        # we need to pull automation 

    def run_end(self, run_no):
        self._running = False 
        self._waiting_for_event = False

    def clear_state(self):
        self.client.msg("Exiting Automation")
        self._last_fill_time = time.time()
        self.client.odb_set("/Equipment/Automator/Settings/state_major", 0, False)
        self.client.odb_set("/Equipment/Automator/Settings/state_minor", 0, False)
        self.client.odb_set("/Equipment/Automator/Variables/counter", 0)

    def configure_state(self, pumps, ballvalves, solenoids):
        print("configuring state",pumps, ballvalves, solenoids)
        if not len(pumps)==3:
            self.client.msg("Incorrectly configured pump-state config received: {}".format(pumps), is_error=True)
        if not len(ballvalves)==6:
            self.client.msg("Incorrectly configured ball-valve-state config received: {}".format(ballvalves), is_error=True)
        if not len(solenoids)==3:
            self.client.msg("Incorrectly configured solenoid-state config received: {}".format(solenoids), is_error=True)

        # pumps should be the first thing turned off, and last thing enabled
        for i in range(len(pumps)):
            if pumps[i]: # if pump should be off 
                # check - is it on? If so, turn it off 
                if (not self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[{}]".format(i))): self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[{}]".format(i), 1)
            else:
                if (self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[{}]".format(i))): self.client.odb_set("/Equipment/PumpConnection/Settings/Pump[{}]".format(i), 0)

        # then check the ball valves 
        for i in range(len(ballvalves)):
            if ballvalves[i]: # turn it on if it's off 
                if (not self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[{}]".format(i))): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[{}]".format(i), 1)
            else: # turn it off if it's on 
                if (self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[{}]".format(i))): self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[{}]".format(i), 0)

        # then check the ball valves 
        for i in range(len(solenoids)):
            if solenoids[i]: # turn it on if it's off 
                if (not self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[{}]".format(i))): self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[{}]".format(i), 1)
            else: # turn it off if it's on 
                if (self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[{}]".format(i))): self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[{}]".format(i), 0)

    def disable_all(self):
        # disable all pumps, solenoid valves, and ball valves 
        self.client.odb_set("/Equipment/Automator/Settings/state_minor", 0, False)
        self.client.odb_set("/Equipment/Automator/Settings/state_major", 0, False)

        self.configure_state([0,0,0], [0,0,0,0,0,0], [0,0,0])

    def step_wavelength(self):
        self._waiting_for_led_stage = True 
        self._rotation_indexer = (self._rotation_indexer + 1) % len(self._rotation_steps)

        which_led = self._rotation_steps[self._rotation_indexer]
        if which_led == -1:
            adc = 1023
            led = 7
        else:
            led = which_led
            # get ADC 
            adc = self.client.odb_get("/Equipment/LEDBoard/Settings/adc_base[{}]".format(which_led - 1))
        position = self.client.odb_get("/Equipment/ELLXStage/Settings/positions[{}]".format(led - 1))

        self.client.odb_set("/Equipment/ELLXStage/Settings/dest", position)
        self.client.odb_set("/Equipment/LEDBoard/Settings/ADC", adc)
        self.client.odb_set("/Equipment/LEDBoard/Settings/LED", led)

    def readout_func(self):
        """
            Progress the automator 
        """
        evt_return = None 
        if self._waiting_for_event and self._running:
            event = self.client.receive_event(self.buffer_handle, async_flag=True)
            if event is None:
                pass 
            else:
                self._waiting_for_event = False  # no longer waiting! 


        """
            This function gets regularly called. It manages requesting picoscope events from the Picoscope frontend
            It also manages reconfiguring the LED board and ELLX stage

            So, if this is waiting for an event from the picoscope, it will only do the pump stuff

            If we're _not_ waiting for an event, then we have tasks to do until we can _request_ an event from the Picoscope frontend  
            These depend on the configuration of the run

            If we're NOT rotating between LEDs - we immediately request another event from the picoscope 

            Otherwise, we check if we're waiting on the LED/Stage
                if we are waiting on them, we check the values and settings. If they match, great! All good. Then we request an event

                if we aren't waiting on them (yet!), we step to the next LED and start waiting 
        """
        # we're not longer waiting for an event, so we're ready to go
        if (not self._waiting_for_event) and self._running:
            if self._rotating_waves:
                if self._waiting_for_led_stage:
                    # just check if the LED board and stage are ready 
                    adc_value = self.client.odb_get("/Equipment/LEDBoard/Variables/ADC") 
                    adc_target = self.client.odb_get("/Equipment/LEDBoard/Settings/ADC") 

                    pos_value = self.client.odb_get("/Equipment/ELLXStage/Variables/dest")
                    pos_target = self.client.odb_get("/Equipment/ELLXStage/Variables/dest")

                    led_value = self.client.odb_get("/Equipment/LEDBoard/Variables/LED")
                    led_target = self.client.odb_get("/Equipment/LEDBoard/Settings/LED")
                    
                    ready = (adc_value == adc_target) and (led_value==led_target) and (abs(pos_target - pos_value)<0.1)
                    if ready:
                        self._waiting_for_led_stage = False 
                        evt_return = midas.event.Event()
                        evt_return.create_bank("REQE", midas.TID_BOOL, (True, ))
                        self._waiting_for_event = True 
                else:
                    # move led board and stage to the next logical position
                    self.step_wavelength()
            else:
                evt_return = midas.event.Event()
                evt_return.create_bank("REQE", midas.TID_BOOL, (True, ))
                self._waiting_for_event = True 

        alarm_state = self.client.odb_get("/Equipment/Automator/Variables/complex_alarms")
        if alarm_state!=0:
            self.disable_all()
        on_ac = bool(self.client.odb_get("/Equipment/UPS/Variables/on_ac"))
        if not on_ac:
            self.disable_all()


        major_state = self.settings["state_major"]
        minor_state = self.settings["state_minor"]

        is_draining = major_state==1 or (major_state==2 and minor_state<128) or (major_state==3 and minor_state<128)

        # check the alarms
        all_flow = [bool(entry) for entry in self.client.odb_get("/Equipment/PumpConnection/Variables/FLOW")]
        overflow = all_flow[2]
        outflow = all_flow[4]
        input_pump_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[0]")
        drain_pump = self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[1]")
        return_pump_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Pump[2]")
        sv1_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[0]")
        sv2_state = self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[0]")
        bv1_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[0]")
        bv2_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[1]")
        bv3_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[2]")
        bv4_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[3]")
        bv5_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[4]")
        bv6_state = self.client.odb_get("/Equipment/PumpConnection/Settings/BallValve[5]")

        p1 = self.client.odb_get("/Equipment/PumpConnection/Variables/PRES[0]") 
        p4 = self.client.odb_get("/Equipment/PumpConnection/Variables/PRES[3]") 
        filter_number = minor_state - 128 

        # pump on but no flow and we're not pressurizing 
        pump1_alarm = False 
        pump2_alarm = False 
        pump3_alarm = False 
        low_pressure_alarm = False 
        if input_pump_state and (not all_flow[0]) and (filter_number!=31):
            if self._pump_worry_ticks > 2:
                pump1_alarm = True 
            self._pump_worry_ticks +=1 
        elif drain_pump and (not all_flow[3]):
            if self._pump_worry_ticks > 2:
                pump2_alarm = True 
            self._pump_worry_ticks +=1 
        elif return_pump_state and (not outflow):
            if self._pump_worry_ticks > 2:
                pump3_alarm = True 
            self._pump_worry_ticks +=1 
        else:
            self._pump_worry_ticks = 0
        
        if input_pump_state and (p1<20):
            if self._pressure_worry_ticks > 2:
                low_pressure_alarm = True 
            self._pressure_worry_ticks += 1
        else:
            self._pressure_worry_ticks = 0
            



        if major_state==10:
            self.disable_all()
        elif major_state==0:
            """
            Do some simple checks against danger
            """
            return evt_return
        
        elif is_draining: # we are draining 
            
            if drain_pump!=1: 
                # just starting - set turn the pump on. Set the counter to zero
                self.configure_state([0,1,0], [0,0,0,0,0,0], [0,0,0])
                self.client.odb_set("/Equipment/Automator/Variables/counter", 0)
            else: 
                counter_value = self.client.odb_get("/Equipment/Automator/Variables/counter")

                if counter_value>=self._drain_ticks:
                    # disable pump, disable automation 
                    if major_state==1:
                        self.configure_state([0,0,0], [0,0,0,0,0,0], [0,0,0])
                        self.clear_state()
                    else:
                        # we shift the minor state up by 128
                        self.configure_state([0,0,0], [0,0,0,0,0,0], [0,0,0])
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 128, False)
                        self.client.odb_set("/Equipment/Automator/Variables/counter", 0)
                        self.client.msg("Beginning to Fill Chamber")

                    
                else:
                    self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)
        elif major_state==2: # actively filling! 
            counter_value = self.client.odb_get("/Equipment/Automator/Variables/counter")
            
            # determine desired settings based on micro state 
            # the first 128 are reserved for draining
            
            
            supply_water = filter_number<20 
            return_water = filter_number<30 and not supply_water
            reverse_osmosis = (not supply_water) and not(return_water)
            
            if supply_water:
                shift = 10
            elif return_water:
                shift = 20
            else:
                shift = 30


            if reverse_osmosis:
                if not bv5_state:
                    self.client.odb_set("/Equipment/PumpConnection/Settings/BallValve[4]", 1)
                if filter_number==31: # pressurizing
                    self.client.odb_set("/Equipment/Automator/Variables/timestamp", time.time())
                    self.configure_state([1,0,0], [0,0,0,0,1,1], [1,0,0])

                    if p1>70: # input pressure check 
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 1, False)
                    elif p4>22: # check osmo pressure 
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 2, False)


                elif filter_number==32: # filling RO tank 
                    osmo_last_time = self.client.odb_get("/Equipment/Automator/Variables/timestamp")

                    self.configure_state([0,0,0], [0,0,0,0,1,1], [0,0,0])
                    if overflow:
                        self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)
                        if counter_value>5:
                            if evt_return is None:
                                evt_return = midas.event.Event()
                            evt_return.create_bank(
                                "TUBE", midas.TID_FLOAT, time.time()
                            )
                            self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 2, False)
                            return evt_return 
                    else:
                        self.client.odb_set("/Equipment/Automator/Variables/counter",0) 
                    if (p4>22 or ((time.time()-osmo_last_time)/60)>1): # fill chamber 
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 1, False)
                    elif p1<50: # re-pressurize
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state - 1, False)

                elif filter_number==33: # filling chamber
                    self.client.odb_set("/Equipment/Automator/Variables/timestamp", time.time())
                    if overflow:
                        self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)
                        if counter_value>5:
                            if evt_return is None:
                                evt_return = midas.event.Event()
                            evt_return.create_bank(
                                "TUBE", midas.TID_FLOAT, time.time()
                            )
                            self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state + 1, False)
                            return evt_return 
                    else:
                        self.client.odb_set("/Equipment/Automator/Variables/counter",0) 
                    self.configure_state([0,0,0], [0,0,0,0,1,1], [1,0,1])
                    if p4<5.6 or p1<35:
                        self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state - 2, False)
                        
                    else:
                        self.configure_state([0,0,0], [0,0,0,0,1,1], [1,1,1])
                        if (not self.client.odb_get("/Equipment/PumpConnection/Settings/Solenoid[1]")): self.client.odb_set("/Equipment/PumpConnection/Settings/Solenoid[1]", 1)

                elif filter_number==34: # bleeding RO tank 
                    self.configure_state([0,0,0], [0,0,0,0,1,0], [0,1,0])
                    self.client.odb_set("Equipment/Automator/Settings/state_minor", minor_state +1 , False)
                elif filter_number==35:
                    if not outflow:
                        self.configure_state([0,0,0], [0,0,0,0,0,0], [0,0,0])
                        self.clear_state()
                    
                else:
                    self.client.msg("Unrecognized minor state {} - exiting ".format(filter_number))
                    self.disable_all()


            else:
                if supply_water or return_water:
                    print(counter_value)
                    bvs = [0,0,0,0,0,0]
                    micro_charcoal = (filter_number - shift) & 1 == 1
                    if micro_charcoal:
                        bvs[1] = int(micro_charcoal)

                    uv_lamp = (filter_number - shift) & 2 == 2
                    if uv_lamp:
                        bvs[2] = int(uv_lamp)

                    ion_filter = (filter_number - shift) & 4 == 4
                    if ion_filter:
                        bvs[3] = int(ion_filter)
                    # bv 6 should only be turned on after a little bit 
                    # we wait 10 counts
                    if counter_value<10:
                        self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)
                        bvs[5] = 0
                        
                    else:
                        bvs[5] = 1

                        # water may be overflowing -  meaning the chamber is full
                        if overflow:
                            if counter_value>self._overflow_ticks:
                                # we have finished filling! 
                                self.clear_state()
                                self.disable_all()
                            self.client.odb_set("/Equipment/Automator/Variables/counter",counter_value+1)


                        else: # if it's not overflowing, keep the counter at 10 
                            self.client.odb_set("/Equipment/Automator/Variables/counter",10)
                self.configure_state([1,0,0], bvs, [1,1,0])
        else:
            self.client.msg("Unrecognized states: {} and {}".format(major_state, minor_state), True)
            self.clear_state()

        return evt_return


class feAutomation(midas.frontend.FrontendBase):
    def __init__(self, frontend_name):
        midas.frontend.FrontendBase.__init__(self, "feAutomation")
        self.add_equipment(frontend_name(self.client))

    def begin_of_run(self, run_number):
        self.equipment["Automator"].run_start(run_number)


    def end_of_run(self, run_number):
        self.equipment["Automator"].run_end(run_number) 
    

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
    