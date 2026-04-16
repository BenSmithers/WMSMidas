import midas.frontend
import midas.event
from midas import file_reader

import numpy as np
import matplotlib.pyplot as plt 
import os 


def fold(thisdat, nmerge=2):
    if nmerge==1:
        return thisdat
    # cut off the extra so it's divisible 
    if int(len(thisdat)%nmerge)!=0:
        thisdat = thisdat[:-(len(thisdat)%nmerge)]
    holder =np.nansum(np.reshape(thisdat, (int(len(thisdat)/nmerge), nmerge)), axis=1)
    return holder

def average(thisdat, nmerge=3):
    if nmerge==1:
        return thisdat
    if int((len(thisdat)%nmerge))!=0:
        thisdat = thisdat[:-(len(thisdat)%nmerge)]
    return np.mean(np.reshape(thisdat, (int(len(thisdat)/nmerge), nmerge)), axis=1)
    

def load_file(filename, **special_banks):
    data = file_reader.MidasFile(filename)
    triggers = []
    times = []
    mon = []
    rec = []
    mon_dark = []
    rec_dark = []
    waves = []

    slow_control_data = {}

    for event in data:
        timestamp = event.header.timestamp
        found_led = False 
        found_counts = False 
        if len(event.banks)==1:
            continue
        for bank_name, bank in event.banks.items():
            if "NCNT" == bank.name: 
                found_counts = True 
                triggers.append(bank.data[0])
                mon.append(bank.data[1])
                rec.append(bank.data[2])
                mon_dark.append(bank.data[3])
                rec_dark.append(bank.data[4])
            elif "LEDO" == bank.name:
                found_led = True 
                waves.append(bank.data[0])
            else:
                if bank_name not in slow_control_data:
                    slow_control_data[bank_name]={
                        "values":[],
                        "times":[]
                    }
                slow_control_data[bank_name]["values"].append(bank.data)
                slow_control_data[bank_name]["times"].append(timestamp)
                
        if found_led and found_counts:
            times.append(timestamp)
        elif (found_led or found_counts):
            raise KeyError("{} LED; {} Counts".format(
                "Found" if found_led else "Did not find",
                "Found" if found_counts else "Did not find"
            ))
    
    return {
        "times":np.array(times),
        "triggers":np.array(triggers),
        "mon":np.array(mon),
        "rec":np.array(rec),
        "waves":np.array(waves),
        "mon_dark":np.array(mon_dark),
        "rec_dark":np.array(rec_dark),
        "slow_control":slow_control_data
    }
