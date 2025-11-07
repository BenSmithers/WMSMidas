import midas.client
import midas
import midas.frontend
import midas.event

import collections
import matplotlib.pyplot as plt 
plt.style.use("wms.mplstyle")
import numpy as np 
from datetime import datetime
import os 
wavelens = [np.nan, 450, 410, 365, 295, 278, 255]


def get_color(n, colormax=3.0, cmap="viridis"):
    """
        Discretize a colormap. Great getting nice colors for a series of trends on a single plot! 
    """
    this_cmap = plt.get_cmap(cmap)
    return this_cmap(n/colormax)


if __name__ == "__main__":
    # Create our client
    client = midas.client.MidasClient("PlotMaker")
    
    # Define which buffer we want to listen for events on (SYSTEM is the 
    # main midas buffer).
    buffer_handle = client.open_event_buffer("SYSTEM")
    
    # Request events from this buffer that match certain criteria. In this
    # case we will only be told about events with an "event ID" of 14.
    request_id = client.register_event_request(buffer_handle, event_id = 19)
    
    tstamps = []
    triggers = []
    mons = []
    recs = []
    mon_dark = []
    recs_dark = []
    waves = []

    while True:
        # If there's an event ready, `event` will contain a `midas.event.Event`
        # object. If not, it will be None. If you want to block waiting for an
        # event to arrive, you could set async_flag to False.
        event = client.receive_event(buffer_handle, async_flag=True)
        
        if event is not None:
            plt.clf()
            # Print some information to screen about this event.
            bank_names = ", ".join(b.name for b in event.banks.values())
            print("Received event with timestamp %s containing banks %s" % (event.header.timestamp, bank_names))
            found_data = False 
            found_time = False 
            found_led = False
            for bank in event.banks.values():
                if "NCNT" == bank.name:
                    print("{} {} {}".format(bank.data[0], bank.data[1], bank.data[2]))
                    triggers.append(bank.data[0])
                    mons.append(bank.data[1])
                    recs.append(bank.data[2])
                    mon_dark.append(bank.data[3])
                    recs_dark.append(bank.data[4])
                    found_data = True                 
                elif "TIME"==bank.name:
                    if found_time:
                        client.msg("Plotter found multiple timestamps", True)
                    tstamps.append(event.header.timestamp)
                    found_time = True 
                elif "LEDO"==bank.name:
                    if found_led:
                        client.msg("Plotter found multiple timestamps", True)
                    waves.append(bank.data[0])
                    found_led = True 
                else:
                    client.msg("Impossible bank name {}".format(bank.name), True)
            if not found_data:
                client.msg("Event without data!", True)
            if not found_time:
                client.msg("Event without timestamp!", True)
            if not found_led:
                client.msg("Event without LED number!" ,True)

            if len(mons)!=len(tstamps):
                client.msg("Inconsistent data numbers and timestamp numbers: {} and {}".format(len(mons), len(tstamps)))

            plt.figure(figsize=(10,6))
            dark_date = np.array([datetime.fromtimestamp(entry) for entry in tstamps])

            np_tstamp = np.array(tstamps)
            np_trig = np.array(triggers)
            np_mon = np.array(mons)
            np_recs = np.array(recs)
            mdark = np.array(mon_dark)
            np_recd = np.array(recs_dark)
            np_waves = np.array(waves)
            monitor_adj = np.log((np_trig - np_mon)/(np_trig - mdark))
            rec_adj = np.log((np_trig - np_recs)/(np_trig - np_recd))
            ratio = monitor_adj / rec_adj

            for i in range(1,7):
                mask= np_waves==i     

                plt.plot(dark_date[mask], ratio[mask], color=get_color(i+1, 8, 'nipy_spectral_r'), label="{} nm".format(wavelens[i]) )        

            plt.legend(loc='lower right', facecolor='white', framealpha=1.0, frameon=True, fancybox=True)
            plt.gcf().autofmt_xdate()
            plt.savefig(
                os.path.join(
                    os.path.dirname(__file__), 
                    "..","..",
                    "custom_html",
                    "example.png"
                ),
                dpi=400
            )
            plt.close()

        # Talk to midas so it knows we're alive, or can kill us if the user
        # pressed the "stop program" button.
        client.communicate(100)
