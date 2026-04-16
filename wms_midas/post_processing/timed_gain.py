import os

from wms_midas.utilities import PicoMeasure
from wms_midas.utilities.read_pico import get_cfd_time
import numpy as np 
import json 
import time 
import matplotlib.pyplot as plt 

#set reference values and call Pico measurements
N_GRAB = 500
thres = 10 
test = PicoMeasure(True)

#set arrays to store targeted and measured values
trig_time = []
rec_dip_times = []
mon_dip_times = []
total_his_mon = []
total_his_rec = []
total_bins_mon = []
total_bins_rec = []

#grab raw data cuz don't want original masks that looks at historgram 
for i in range(N_GRAB):
    
    trigger, chanb, chand = test.measure(True) #raw data
    time_sample = np.linspace(0, (test.totalSamples - 1) * test.actualSampleIntervalNs, test.totalSamples) #time

    #trigger time
    ctime, trig_bin = get_cfd_time(time_sample, trigger, 1000,auto_adjust_ped=False, use_rise=True) #get trigger time

    #cut waveforms around trigger
    chunk_length = 90
    chunk_offsets = np.arange(chunk_length)
    trig_bin = trig_bin[:-1]
    chunk_indices = trig_bin[:, None] + chunk_offsets[None, :]
    cut_waveforms_rec = chand[chunk_indices]
    cut_waveforms_mon = chanb[chunk_indices]
    cut_times = time_sample[chunk_indices]
    rel_time = cut_times - cut_times[:,0][:, None]

    print(cut_waveforms_mon.max(), cut_waveforms_mon.min())

    #dips and respective times
    rec_dip_mask = cut_waveforms_rec < -thres
    rec_dip_pts = np.where(rec_dip_mask)[0]
    rec_dip_times.append(rel_time[rec_dip_mask])

    mon_dip_mask = cut_waveforms_mon < -thres
    mon_dip_pts = np.where(mon_dip_mask)[0]
    mon_dip_times.append(rel_time[mon_dip_mask])   
    #make bins
    time_bins = np.arange(0, 90*test.actualSampleIntervalNs, 4)
    hist_rec, bins_rec = np.histogram(np.concatenate(rec_dip_times), bins=time_bins)
    hist_mon, bins_mon = np.histogram(np.concatenate(mon_dip_times), bins=time_bins)
    total_his_rec.append(hist_rec)
    total_his_mon.append(hist_mon)
    total_bins_rec.append(bins_rec)
    total_bins_mon.append(bins_mon)
    
print(hist_mon[:10])
#print (np.max(mon_dip_times), np.min(mon_dip_times), np.max(rec_dip_times), np.min(rec_dip_times))

bin_centers_rec = (bins_rec[:-1] + bins_rec[1:]) / 2
bin_centers_mon = (bins_mon[:-1] + bins_mon[1:]) / 2

#plot
plt.figure()
plt.plot(bin_centers_rec, np.sum(total_his_rec, axis=0), '.-', label='Receiver')
plt.plot(bin_centers_mon, np.sum(total_his_mon, axis=0), '.-', label='Monitor')
plt.yscale('log')
plt.title("Timed Gain Measurement for 278nm LED")
plt.xlabel("Time since trigger(ns)")
plt.ylabel("Signal counts")
plt.legend()
plt.savefig(
    os.path.join(os.path.dirname(__file__), "plots", "timed_gain.png"), dpi=400
)
plt.show()

np.savetxt(
    os.path.join(os.path.dirname(__file__), "plots", "timed_gain_data_278_fast.txt"),
    np.column_stack((bin_centers_mon, np.sum(total_his_mon, axis=0), np.sum(total_his_rec, axis=0))),
    delimiter=" ",
    header="Time since trigger(ns)     Monitor signal counts    Receiver Signal counts"
)