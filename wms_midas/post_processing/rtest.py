from wms_midas.utilities import PicoMeasure

import numpy as np
import json
import time
import matplotlib.pyplot as plt
from math import sqrt 
print("Initializing")
print("Receiving Waveforms")
test = PicoMeasure(True)
test.collection_time = 5


last_one = -1 

while True:

    start = time.time()

    trig, monitor, rec, md, mr = test.measure()
#    res = test.measure(True)

    md_err = sqrt(monitor)
    rec_err = sqrt(rec)

    ratio_error = (rec/monitor)*sqrt( (md_err/monitor)**2 +  (rec_err/rec)**2 )
    print(trig, "triggers", monitor/trig, rec/trig, "ratio", "{:.4f} +/- {:.4f}".format(rec/monitor, ratio_error))
    last_one = rec/monitor

    trig, mon, rec  = test.measure(True)

    plt.plot(trig[:1000]/200)
    plt.plot(mon[:1000])
    plt.plot(rec[:1000])
    plt.savefig("waveforms.png", dpi=400)
    plt.clf()
    continue