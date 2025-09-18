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
        0 - Run pump 2, actively draining
        
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