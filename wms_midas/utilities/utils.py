import ctypes
from multiprocessing.sharedctypes import Value
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc
from contextlib import ContextDecorator # used to trigger the compilation

from enum import Enum
import matplotlib.pyplot as plt 

import numpy as np 
import time as pytime
from scipy.signal import find_peaks
from tqdm import tqdm
MAXSAMPLES = 25000
overflow = (ctypes.c_int16 * 60)()
cmaxSamples = ctypes.c_int32(MAXSAMPLES)
maxADC = ctypes.c_int16()

chARange = 5
nbuf = 10
channelInputRanges = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]

def get_cfd_time(times, signal, threshold, auto_adjust_ped = False, use_rise=False):
    if auto_adjust_ped:
        ped = np.mean( signal[np.abs(signal)<0.66*threshold] )
    else:
        ped = 0
    crossings = np.diff(np.sign((signal-ped) - threshold))
    if use_rise:
        crossings[crossings<0] = 0    
    else:
        crossings[crossings>0] = 0
    
    crossings = np.where(crossings)
    x0 = times[crossings[0]]
    return x0, x0

    y0 = signal[crossings[0]]
    y1 = signal[crossings[0]+1]
    slope = (y1-y0)/8
    b = y0 - slope*x0 
    return (threshold - b)/slope, (threshold - b)/slope -x0


def get_rtime(trigs, hits):
    min_time = 0
    max_time = 346

    tdiffs = []

    hit_index = 0
    for i in range(len(trigs)):
        while hits[hit_index]<(trigs[i]+max_time) and hit_index<len(hits)-1:

            # now the hit_index is the hit just after the trig we're on
            dif = hits[hit_index] - trigs[i]
            if dif>min_time and dif<max_time:
                tdiffs.append(dif)                

            hit_index+=1

    return tdiffs 


def get_valid(trigs, hits, is_rec, invalid=False):
    window = 24
    if invalid:
        shift = 150
    else:
        shift = 0
    if is_rec:
        min_time = 104+shift
        max_time = min_time+window
    else:
        min_time = 12+shift
        max_time = min_time+window

    hit_trig_time = hits - trigs[np.digitize(hits, trigs)-1]
    good = np.logical_and( hit_trig_time>min_time, hit_trig_time<max_time)
    return good, np.logical_not(good)

class ReturnType(Enum):
    PulseCount = 0
    Amplitudes = 1
    Area = 2

class Scope(ContextDecorator):
    """
        We use the contextdecorator so that this will perform certain actions upon closing
    """

    def __enter__(self):
        self._channels={}
        self._threshs={}

        # Displays the staus returns
        self._prepared = False 
        self.chandle = ctypes.c_int16()
        self.status = ps.ps3000aOpenUnit(ctypes.byref(self.chandle ), None)
        self.powerstat =  ps.ps3000aChangePowerSource(self.chandle , 282)

        self._min_offset = 25 # ns? 
        self._max_offset = 150
        self._time_per_sample = -1

    def __exit__(self, *exc):
        """
        We stop and close the connection to the picoscope 
        """
                
        # Stops the scope
        # Handle = chandle
        stat= ps.ps3000aStop(self.chandle)
        assert_pico_ok(stat)

        # Closes the unit
        # Handle = chandle
        stat = ps.ps3000aCloseUnit(self.chandle)
        assert_pico_ok(stat)

    def _prepare(self):
        """
            Prepare some memory stuff on the picoscope
            We don't want to do this until all of the channels are engaged though, so this function should be called before the bulk of sample happens 
        """
        timeIntervalns = ctypes.c_float()
        returnedMaxSamples = ctypes.c_int16()
        n_segments= 10*len(list(self._channels.keys()))
        print("Buffering {} segments".format(n_segments))
        status= ps.ps3000aGetTimebase2(self.chandle, 2, MAXSAMPLES, ctypes.byref(timeIntervalns), 1, ctypes.byref(returnedMaxSamples), 0)
        print("Using Time interval: {} ns".format(timeIntervalns))
        self._time_per_sample = float(timeIntervalns.value)*2

        assert_pico_ok(status)
        status=ps.ps3000aMemorySegments(self.chandle, n_segments, ctypes.byref(cmaxSamples))
        assert_pico_ok(status)
        status=ps.ps3000aSetNoOfCaptures(self.chandle, n_segments)
        assert_pico_ok(status)
        self._prepared = True 

    def enable_channel(self, channo, collect=True, pulse_threshold=25):
        """
            Enable the channel on the picoscope, and then prepare a Channel object where the buffers will be opened
        """
        print("enable channel, ", channo)
        status =ps.ps3000aSetChannel(self.chandle,channo, 1, 1, chARange, 0)
        assert_pico_ok(status)
        self._prepared = False
        if collect: 
            self._channels[channo] = Channel(self, channo)
            self._threshs[channo] = pulse_threshold
            return self._channels[channo]

    def disable_channel(self, channo):
        ps.ps3000aSetChannel(self.chandle,channo,0, 1, chARange, 0) 
        self._prepared = False 
        if channo in self._channels:
            del self._channels[channo]

    def set_trigger(self, channel, rising=True):
        print("Setting trigger", channel)
        status = ps.ps3000aSetSimpleTrigger(self.chandle, 1, channel, 1024, 2 if rising else 3, 0, 1000 )
        assert_pico_ok(status)


    def sample(self, return_kind=ReturnType.PulseCount):
        if not self._prepared:
            self._prepare()

        n_chan = len(list(self._channels.keys()))

        ps.ps3000aRunBlock(self.chandle, 0, MAXSAMPLES, 2, 1, None, 0, None, None)

        peaks = [0 for _ in self._channels.keys()]
        amps = [[] for _ in self._channels.keys()]
        times = [[] for _ in self._channels.keys()]

        for ic, chankey in enumerate(self._channels.keys()):
            for bx in range(len(self._channels[chankey].bufmin)):
                
                buffer_no = bx #+ic*len(self._channels[chankey].bufmin)
                status = ps.ps3000aSetDataBuffers(self.chandle, chankey, self._channels[chankey].bufmax[bx].ctypes.data, self._channels[chankey].bufmin[bx].ctypes.data, MAXSAMPLES, buffer_no, ps.PS3000A_RATIO_MODE["PS3000A_RATIO_MODE_NONE"] )
                assert_pico_ok(status)

        ready = ctypes.c_int(0)
        check = ctypes.c_int(0)
        bad_count =0
        while ready.value==check.value:
            status = ps.ps3000aIsReady(self.chandle, ctypes.byref(ready))
            pytime.sleep(0.02)
            if bad_count>40:
                assert_pico_ok(status)  
                if status==0:
                    break
                raise ValueError()
            bad_count+=1

        status = ctypes.c_int(1)
        while status!=0:
            # ps.ps3000aGetValuesBulk(chandle, ctypes.byref(cmaxSamples), 0, 9, 1, 0, ctypes.byref(overflow))
            status = ps.ps3000aGetValuesBulk(self.chandle, ctypes.byref(cmaxSamples), 0, 9,  0, ps.PS3000A_RATIO_MODE["PS3000A_RATIO_MODE_NONE"] , ctypes.byref(overflow))
            pytime.sleep(0.05)
        assert_pico_ok(status)  
        status = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(maxADC))
        assert_pico_ok(status)
        pytime.sleep(0.25)


        for ic, chankey in enumerate(self._channels.keys()):  
            sign = 1 if chankey==0 else -1
            for i in range(10):
                parsed = adc2mV(self._channels[chankey].bufmax[i], chARange, maxADC)
                #plt.plot(range(len(parsed)), sign*np.array(parsed), alpha=0.2)
                
                # find_peks returns only the index of the peaks, so we need to extrapolate out to get a time
                # and then also consider that each of these samples are sequential


                # on signal is 170ns, off is 200ns 
                if ic==0:
                    # we get the time when the trigger signal crosses the axis
                    crossings = np.argwhere(np.diff(np.sign(sign*np.array(parsed) - self._threshs[chankey]))).flatten()
                    if len(crossings)<1 or len(crossings)<2:
                        continue
                    start_on = crossings[1] - crossings[0] < 180
                    if start_on:
                        crossings = crossings[np.array(range(len(crossings)))%2==0]
                    else:
                        crossings = crossings[np.array(range(len(crossings)))%2==1]

                    shifted_times = np.array(crossings)*self._time_per_sample + i*self._time_per_sample*len(parsed)
                    peaks[ic] += len(shifted_times)
                    amps[ic] += list(np.array(parsed)[crossings]) 

                else:
                    peakfind = find_peaks(sign*np.array(parsed), height=self._threshs[chankey])
                    shifted_times = np.array(peakfind[0])*self._time_per_sample + i*self._time_per_sample*len(parsed)
                    peaks[ic] += len(peakfind[0])
                    amps[ic] += list(peakfind[1]["peak_heights"])
                times[ic] += shifted_times.tolist() 

       # print(times[2][:10])
        accepted = [[], []]

        if len(times[0]) >0:
            # iterate over the pulse times for channels
            for i, pulse_time in enumerate(times[1]):
                # binary search to find the trigger pulses bordering this one
                index = np.searchsorted(times[0], pulse_time)-1  # minus one to get the proper index of the proceeding pulse 
                if index>=len(times[0]):
                    index = len(times[0])-1
                
                tdiff = pulse_time - times[0][index]
          
                #accepted[0].append( tdiff>self._min_offset and tdiff<self._max_offset )
                accepted[0].append(True)
            
            for i, pulse_time in enumerate(times[2]):
                index = np.searchsorted(times[0], pulse_time)-1  # minus one to get the proper index of the proceeding pulse 
                if index>=len(times[0]):
                    index=len(times[0])-1
                tdiff = pulse_time - times[0][index]
                accepted[1].append(True)
                #accepted[1].append( tdiff>self._min_offset and tdiff<self._max_offset )
        accepted =[np.array(accepted[0]), np.array(accepted[1])]
        amps = [np.array(entry) for entry in amps ]

            #return self._channels[chankey].bufmax[i], self._channels[chankey].bufmin[i]
            #plt.show()
        if return_kind.value==ReturnType.PulseCount.value:
            #return peaks[0], times[0], times[1]
            if np.sum(accepted[0].astype(int))==0:
                acc0 = 0
            else:
                acc0 = len(amps[1][accepted[0]])
            if np.sum(accepted[1].astype(int))==0:
                acc1=0
            else:
                acc1 = len(amps[2][accepted[1]])
            return peaks[0], acc0, acc1

        elif return_kind.value==ReturnType.Amplitudes.value:
            return peaks[0], amps[1][accepted[0]], amps[2][accepted[1]]

    def adc2mV(self, bufferADC, maxADC):
        bufferV = bufferADC*channelInputRanges[chARange]/maxADC
        return bufferV

class Channel:
    """
        the scope of this class evolved as the code was written. 
        Right now, it's just an object for holding the buffers for the channels
        It may evolve down the line though
    """
    def __init__(self, scope:Scope, channel:int):
        """
            channel - 0, 1, 2, 3 
            for A, B, C, and D 
        """
 
        self.bufmin = [np.empty(MAXSAMPLES,dtype=np.dtype('int16')) for i in range(10)]
        self.bufmax = [np.empty(MAXSAMPLES,dtype=np.dtype('int16')) for i in range(10)]
        
