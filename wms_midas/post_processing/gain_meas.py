from wms_midas.utilities import PicoMeasure
import numpy as np 
import json 
import time 
import matplotlib.pyplot as plt 
print("Initializing")
#plt.style.use("wms.mplstyle")

N_GRAB = 10
test = PicoMeasure(True)
keepon = False
mon_run = None
rec_run = None

# if True, it uses the height of the tallest pulse
# otherwise it sums up the waveform (pedestal-subtracted)
use_peak = False
for i in range(N_GRAB):

    od = test.calibrate(False, peak=use_peak)
   
    if mon_run is None:
        mon_run =np.array( od["monitor"])
        rec_run = np.array(od["rec"])
    else:
        mon_run = np.array(od["monitor"])
        rec_run = np.array(od["rec"])
        
    plt.stairs(rec_run, od["bins"], alpha=0.2, color='blue')
    plt.stairs(mon_run,  od["bins"],alpha=0.2, color='orange')
plt.plot([], [], color='blue', label="Receiver")
plt.plot([], [], color='orange', label="Monitor")
if use_peak:
    plt.xlabel("Pulse Height [ADC]")
else:
    plt.xlabel("Waveform Sum [ADC]")
plt.yscale('log')
#plt.xlim([0, 200])
plt.legend()
plt.tight_layout()
plt.savefig("./plots/gain.png")
plt.show()

