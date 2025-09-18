
        
import os 
import ctypes
import numpy as np
import h5py as h5 
from picosdk.ps3000a import ps3000a as ps
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok, PICO_STATUS_LOOKUP
import time
from scipy.signal import find_peaks
from StageControl.picocode.utils import get_valid, get_cfd_time, count_hits
import json 
from picosdk.PicoDeviceEnums import picoEnum

thresh = 10


channelInputRanges = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]
def adc2mV(buffer, rang, maxADC):
    """
    Rewrote the picoscode version of this to use vectorized numpy math
    Got some 100x speed improvements 
    """
    return (buffer.astype(float)*channelInputRanges[rang])/maxADC.value 

def fold_min(thisdat, nmerge=370):
    if nmerge==1:
        raise NotImplementedError("This is nonsense")

    if int(len(thisdat)%nmerge)!=0:
        thisdat = thisdat[:-(len(thisdat)%nmerge)]
    return np.nanmin(np.reshape(thisdat, (int(len(thisdat)/nmerge),nmerge)), axis=1)


class PicoMeasure:
    def __init__(self, block_mode = False):
        self.nextSample = 0
        self.bped = 0 # 1.54
        self.dped = 0 # 3.54 -0.5
        self.autoStopOuter = False
        self.wasCalledBack = False
        self._initialized = False
        self._block_mode = block_mode
        print("In {} mode".format("block" if block_mode else "stream"))
        self.collection_time = 30

        self.rec_lt_good = 40./376
        self.mon_lt_good = 40./376


        # Create self.chandle and self.status ready for use
        self.chandle = ctypes.c_int16()
        self.status = {}
        self._good = False 
        self.start()
        
        self.collection_time = 30
        return
        while not self._good:
            print("Check")
            self.start()
            self.collection_time = 10
            self.calibrate() 
            if not self._good:
                self.close()
        self.collection_time = 30


    def start(self):

        # Open PicoScope 5000 Series device
        self.status["openunit"] = ps.ps3000aOpenUnit(ctypes.byref(self.chandle), None)

        try:
            assert_pico_ok(self.status["openunit"])
        except: # PicoNotOkError:

            powerStatus = self.status["openunit"]

            # try powering it up in a few ways. AC adapter or USB 
            if powerStatus == 286:
                self.status["changePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, powerStatus)
            elif powerStatus == 282:
                self.status["changePowerSource"] = ps.ps3000aChangePowerSource(self.chandle, powerStatus)
            else:
                raise

            assert_pico_ok(self.status["changePowerSource"])


        enabled = 1
        disabled = 0
        trig_off = -1.5
        analogue_offset = 0.0

        # Set up channel A
        # handle = self.chandle
        # channel = PS3000A_CHANNEL_A = 0
        # enabled = 1
        # coupling type = PS3000A_DC = 1
        # range = PS3000A_2V = 7
        # analogue offset = 0 V
        self.channel_range = ps.PS3000A_RANGE['PS3000A_2V']
        self.ch_range_2 = ps.PS3000A_RANGE['PS3000A_200MV'] 
        self.ch_range_3 = ps.PS3000A_RANGE['PS3000A_200MV'] 
        self.status["setChA"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                self.channel_range,
                                                trig_off)
        
        #ps.ps3000aGetChannelInformation()
        assert_pico_ok(self.status["setChA"])
        
        # Set up channel B
        # handle = self.chandle
        # channel = PS3000A_CHANNEL_B = 1
        # enabled = 1
        # coupling type = PS3000A_DC = 1
        # range = PS3000A_2V = 7
        # analogue offset = 0 V
        self.status["setChB"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                self.ch_range_2,
                                                analogue_offset)
        assert_pico_ok(self.status["setChB"])
        self.status["setChC"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_C'],
                                                disabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                self.ch_range_2,
                                                analogue_offset)
        assert_pico_ok(self.status["setChC"])       

        self.status["setChD"] = ps.ps3000aSetChannel(self.chandle,
                                                ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'],
                                                enabled,
                                                ps.PS3000A_COUPLING['PS3000A_DC'],
                                                self.ch_range_3,
                                                analogue_offset)
        assert_pico_ok(self.status["setChD"])
        

        bw = picoEnum.PICO_BANDWIDTH_LIMITER["PICO_BW_FULL"]
        self.status["band"] = ps.ps3000aSetBandwidthFilter( self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'], bw)
        assert_pico_ok(self.status["band"])
        self.status["band"] = ps.ps3000aSetBandwidthFilter( self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'], bw)
        assert_pico_ok(self.status["band"])
        self.status["band"] = ps.ps3000aSetBandwidthFilter( self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'], bw)
        assert_pico_ok(self.status["band"])
        # Size of capture
        # we want a lot of these. The more the better. Eventually reached diminishing returns 
        if self._block_mode:
            self.sizeOfOneBuffer = 370*100000
            self.totalSamples = self.sizeOfOneBuffer*1
        else:
            self.sizeOfOneBuffer = 500 # 0000
            self.sizeOfOneBuffer *= 100000

            numBuffersToCapture = 1

            self.totalSamples = self.sizeOfOneBuffer * numBuffersToCapture

        # Create buffers ready for assigning pointers for data collection
        self.bufferAMax = np.zeros(shape=self.sizeOfOneBuffer, dtype=np.int16)
        self.bufferBMax = np.zeros(shape=self.sizeOfOneBuffer, dtype=np.int16)
        self.bufferDMax = np.zeros(shape=self.sizeOfOneBuffer, dtype=np.int16)
        self.memory_segment = 0

        # Set data buffer location for data collection from channel A
        # handle = self.chandle
        # source = PS3000A_CHANNEL_A = 0
        # pointer to buffer max = ctypes.byref(self.bufferAMax)
        # pointer to buffer min = ctypes.byref(bufferAMin)
        # buffer length = maxSamples
        # segment index = 0
        # ratio mode = PS3000A_RATIO_MODE_NONE = 0
        self.status["setDataBuffersA"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                            self.bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            self.sizeOfOneBuffer,
                                                            self.memory_segment,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersA"])
        
        # Set data buffer location for data collection from channel B
        # handle = self.chandle
        # source = PS3000A_CHANNEL_B = 1
        # pointer to buffer max = ctypes.byref(self.bufferBMax)
        # pointer to buffer min = ctypes.byref(bufferBMin)
        # buffer length = maxSamples
        # segment index = 0
        # ratio mode = PS3000A_RATIO_MODE_NONE = 0
        self.status["setDataBuffersB"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                            self.bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            self.sizeOfOneBuffer,
                                                            self.memory_segment,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersB"])
        
        self.status["setDataBuffersD"] = ps.ps3000aSetDataBuffers(self.chandle,
                                                            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'],
                                                            self.bufferDMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                            None,
                                                            self.sizeOfOneBuffer,
                                                            self.memory_segment,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(self.status["setDataBuffersD"])
        
        self.sampleInterval = ctypes.c_int32(8)
        self.actualSampleInterval = self.sampleInterval.value

        if self._block_mode:
            self._timebase = 2
            timeIntervalns = ctypes.c_float()
            returnedMaxSamples = ctypes.c_int32()
            n_segments= 1

            status= ps.ps3000aGetTimebase2(self.chandle, self._timebase, self.totalSamples, ctypes.byref(timeIntervalns), 1, ctypes.byref(returnedMaxSamples), 0)
            
            self.actualSampleInterval = timeIntervalns.value
            self.actualSampleIntervalNs = self.actualSampleInterval
            self.cmax = ctypes.c_int32(self.totalSamples)
            assert_pico_ok(status)
            status=ps.ps3000aMemorySegments(self.chandle, n_segments, ctypes.byref(self.cmax))
            assert_pico_ok(status)
            status=ps.ps3000aSetNoOfCaptures(self.chandle, n_segments)
    
    def close(self):
                
        # Stop the scope
        # handle = chandle
        self.status["stop"] = ps.ps3000aStop(self.chandle)
        assert_pico_ok(self.status["stop"])

        # Disconnect the scope
        # handle = chandle
        self.status["close"] = ps.ps3000aCloseUnit(self.chandle)
        assert_pico_ok(self.status["close"])

    def calibrate(self, hack=False, peak=True):
        """
            Get trigger times.
            Then chop up waveforms. 
            Sum over each waveform, minus the pedestal
            Make distribution. Run fit. 
            Get threshold
        """
        trigger, chanb, chand = self.measure(True)
        #time_sample = np.linspace(0, (self.totalSamples - 1) * self.sampleIntervalNs, self.totalSamples)
        if peak:
            bins = np.linspace(0, 200, 129)
        else:
            bins = np.linspace(-20, 20, 129)
        
        if hack:
            mon_peaks = -1*fold_min(chanb, nmerge=370)
            rec_peaks = -1*fold_min(chand, nmerge=370)
        else:
            # we drop this down to just a difference in the sign (-2, 0, +2)
            # but shifted down by the threshold 
            # so +2 is crossing up, -2 is crossing down, 0 is staying above/below 
            crossings = np.diff(np.sign(trigger - 1000))
            #  call the crossing-down ones nothing
            crossings[crossings<0] = 0
            # and get the places where we are crossing up. hit times! 
            crossings = np.where(crossings)[0]

            window = int(370 / self.actualSampleIntervalNs)
            skip = 0 # 42  int(0.6*window)
            
            mon_peaks = []
            rec_peaks = []
            for ic in crossings:
                if len(chanb[ic+skip:ic+window])==0:
                    continue
                #print(window*np.sum(chanb[ic+360:ic+window])/10)
                # peak distribution
                if peak:
                    mon_peaks.append(-1*np.min(chanb[ic+skip:ic+window]) + np.mean(chanb[ic+window-10:ic+window]))
                    rec_peaks.append(-1*np.min(chand[ic+skip:ic+window]) + np.mean(chand[ic+window-10:ic+window]) )
                else:
                # waveform sum with pedestal subtraction
                    mon_peaks.append(np.sum(chanb[ic+skip:ic+window])/window - np.sum(chanb[ic+window-10:ic+window]/10) )
                    rec_peaks.append(np.sum(chand[ic+skip:ic+window])/window - np.sum(chand[ic:ic+10])/10)

                #mon_peaks.append(np.sum(chanb[ic+skip:ic+window]) )
                #rec_peaks.append(np.sum(chand[ic+skip:ic+window]) -400)

        print(np.mean(mon_peaks))
        print(np.mean(rec_peaks))
        mon_data = np.histogram(mon_peaks, bins)[0]
        rec_data = np.histogram(rec_peaks, bins)[0]

#        self._good = mon_data[-2]>20 and rec_data[-2]>20
        


        out_data = {
            "bins" : bins.tolist(),
            "monitor":mon_data.tolist(),
            "rec":rec_data.tolist()
        }
        
        _obj = open(os.path.join(os.path.dirname(__file__), "charge.json"), 'wt')
        json.dump(out_data, _obj,indent=4)
        _obj.close()
        return out_data

    def measure(self, give_waves=False, raw_dat = False):
        if self._block_mode:
            return self._rapidblock(give_waves, raw_dat)
        else:
            return self._stream(give_waves, raw_dat)
    def _rapidblock(self, give_waves, raw_dat):
        start = time.time()
        trig = 0
        mon = 0
        mond = 0
        rec = 0
        recd = 0

        while (time.time() - start)<self.collection_time:
            res = self._rbe(give_waves, raw_dat)
            if give_waves:
                return res 
            trig += res[0]
            mon += res[1]
            rec += res[2]
            mond+= res[3]
            recd+= res[4]
        return trig, mon, rec, mond, recd

    def _rbe(self, give_waves=False, raw_dat=False):
        status = ps.ps3000aRunBlock(self.chandle, 0, self.totalSamples, self._timebase, 1, None, 0, None, None) 
        assert_pico_ok(status)

        ready= ctypes.c_int(0)
        while ready==ctypes.c_int(0):
            status = ps.ps3000aIsReady(self.chandle, ctypes.byref(ready))
            time.sleep(0.04)

        self.bufferAMax*=0
        self.bufferBMax*=0
        self.bufferDMax*=0
        status = ps.ps3000aSetDataBuffer(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'], self.bufferAMax.ctypes.data,  self.totalSamples, 0, ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(status)
        status = ps.ps3000aSetDataBuffer(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'], self.bufferBMax.ctypes.data,self.totalSamples, 0, ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(status)
        status = ps.ps3000aSetDataBuffer(self.chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_D'], self.bufferDMax.ctypes.data,  self.totalSamples, 0, ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
        assert_pico_ok(status)



        overflow = (ctypes.c_int16 * 60)()        
        nstat = ctypes.c_int(1)
        while nstat!=0:
            nstat = ps.ps3000aGetValuesBulk(self.chandle, ctypes.byref(self.cmax), 0, 0,  0, ps.PS3000A_RATIO_MODE["PS3000A_RATIO_MODE_NONE"] , ctypes.byref(overflow))
            time.sleep(0.04)
        
        maxADC = ctypes.c_int16()
        status = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(maxADC))
        assert_pico_ok(status)
        if give_waves:
            if raw_dat:
                return self.bufferAMax, self.bufferBMax, self.bufferDMax     
        adc2mVChAMax = adc2mV(self.bufferAMax, self.channel_range, maxADC)
        adc2mVChBMax = adc2mV(self.bufferBMax, self.ch_range_2, maxADC) -self.bped
        adc2mVChDMax = adc2mV(self.bufferDMax, self.ch_range_3, maxADC) -self.dped
        if give_waves:
            return adc2mVChAMax, adc2mVChBMax, adc2mVChDMax 

        time_sample = np.linspace(0, (self.totalSamples - 1) * self.actualSampleIntervalNs, self.totalSamples)

        t1 = time.time()
        ctime, trig_bin = get_cfd_time(time_sample, adc2mVChAMax, 1000,auto_adjust_ped=False, use_rise=True)
        ntrig = len(ctime)
       
        nmon = count_hits(trig_bin,adc2mVChBMax, thresh,True,  90, False)
        nrec = count_hits(trig_bin,adc2mVChDMax, thresh,False, 90, False)
        mon_bad = count_hits(trig_bin,adc2mVChBMax, thresh,True,  90, True)
        rec_bad = count_hits(trig_bin,adc2mVChDMax, thresh,False, 90, True)

        return ntrig, nmon, nrec, mon_bad, rec_bad

    def _stream(self, give_waves = False, raw_data=False):

        self.bufferAMax*=0
        self.bufferBMax*=0
        self.bufferDMax*=0

        # Begin streaming mode:
        
        sampleUnits = ps.PS3000A_TIME_UNITS['PS3000A_NS']
        # We are not triggering:
        maxPreTriggerSamples = 0
        autoStopOn = 1
        # No downsampling:
        downsampleRatio = 1
        self.bufferCompleteA = np.zeros(shape=self.totalSamples, dtype=np.int16)
        self.bufferCompleteB = np.zeros(shape=self.totalSamples, dtype=np.int16)
        self.bufferCompleteD = np.zeros(shape=self.totalSamples, dtype=np.int16)
        import time 
        loops = 0
        collection_start = time.time()
        nns = 0

        t_total = 0
        mon_total = 0
        rec_total = 0
        mon_dark = 0
        rec_dark = 0

        while True:
            # need to set a lot of this up between calls 
            start = time.time()
            self.status["runStreaming"] = ps.ps3000aRunStreaming(self.chandle,
                                                            ctypes.byref(self.sampleInterval),
                                                            sampleUnits,
                                                            maxPreTriggerSamples,
                                                            self.totalSamples,
                                                            autoStopOn,
                                                            downsampleRatio,
                                                            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'],
                                                            self.sizeOfOneBuffer)
            assert_pico_ok(self.status["runStreaming"])

            self.actualSampleInterval = self.sampleInterval.value
            self.actualSampleIntervalNs = self.actualSampleInterval *1


            self.nextSample = 0
            self.autoStopOuter = False
            self.wasCalledBack = False
            # We need a big buffer, not registered with the driver, to keep our complete capture in.
            def streaming_callback(handle, noOfSamples, startIndex, overflow, triggerAt, triggered, autoStop, param):
                self.wasCalledBack = True
                destEnd = self.nextSample + noOfSamples
                sourceEnd = startIndex + noOfSamples
                self.bufferCompleteA[self.nextSample:destEnd] = self.bufferAMax[startIndex:sourceEnd]
                self.bufferCompleteB[self.nextSample:destEnd] = self.bufferBMax[startIndex:sourceEnd]
                self.bufferCompleteD[self.nextSample:destEnd] = self.bufferDMax[startIndex:sourceEnd]
                self.nextSample += noOfSamples
                if autoStop:
                    self.autoStopOuter = True


            # Convert the python function into a C function pointer.
            cFuncPtr = ps.StreamingReadyType(streaming_callback)

            # Fetch data from the driver in a loop, copying it out of the registered buffers and into our complete one.
            while self.nextSample < self.totalSamples and not self.autoStopOuter:
                self.wasCalledBack = False
                self.status["getStreamingLastestValues"] = ps.ps3000aGetStreamingLatestValues(self.chandle, cFuncPtr, None)
                if not self.wasCalledBack:
                    # If we weren't called back by the driver, this means no data is ready. Sleep for a short while before trying
                    # again.
                    time.sleep(0.01)
            assert_pico_ok(self.status["getStreamingLastestValues"])

            # Find maximum ADC count value
            # handle = self.chandle
            # pointer to value = ctypes.byref(maxADC)
            maxADC = ctypes.c_int16()
            self.status["maximumValue"] = ps.ps3000aMaximumValue(self.chandle, ctypes.byref(maxADC))
            print("Max val", maxADC)
            assert_pico_ok(self.status["maximumValue"])

            # Convert ADC counts data to mV
            conv_t = time.time()
            if give_waves:
                if raw_data:
                    return self.bufferCompleteA, self.bufferCompleteB, self.bufferCompleteD
                adc2mVChAMax = adc2mV(self.bufferCompleteA, self.channel_range, maxADC)
                adc2mVChBMax = adc2mV(self.bufferCompleteB, self.ch_range_2, maxADC)
                adc2mVChDMax = adc2mV(self.bufferCompleteD, self.ch_range_3, maxADC)
                return adc2mVChAMax, adc2mVChBMax, adc2mVChDMax

            else:
                adc2mVChAMax = adc2mV(self.bufferCompleteA, self.channel_range, maxADC)
                adc2mVChBMax = adc2mV(self.bufferCompleteB, self.ch_range_2, maxADC) - self.bped
                adc2mVChDMax = adc2mV(self.bufferCompleteD, self.ch_range_3, maxADC) - self.dped



        #    adc2mVChAMax = self.bufferCompleteA
        #    adc2mVChBMax = self.bufferCompleteB
        #    adc2mVChDMax = self.bufferCompleteD
            conv_t_end = time.time()
            # Create time data
            time_sample = np.linspace(0, (self.totalSamples - 1) * self.actualSampleIntervalNs, self.totalSamples)

            ctime = get_cfd_time(time_sample, adc2mVChAMax, 1000,auto_adjust_ped=False, use_rise=True)[0]
            ntrig = len(ctime)

            montime = get_cfd_time(time_sample, -adc2mVChBMax, thresh,auto_adjust_ped= True, use_rise=False)[0]
            is_good, is_bad = get_valid(ctime, montime, False)
            nmon = np.sum(is_good)
            #mon_bad = np.sum(is_bad)*self.mon_lt_good/(1-self.mon_lt_good)
            mon_bad = np.sum(get_valid(ctime, montime,  False, True))
        
            rectime = get_cfd_time(time_sample, -adc2mVChDMax, thresh,auto_adjust_ped= True, use_rise=False)[0]
            is_good, is_bad = get_valid(ctime, rectime, True)
            nrec = np.sum(is_good)
            
            #rec_bad = np.sum(is_bad)*self.rec_lt_good/(1-self.rec_lt_good)
            rec_bad = np.sum(get_valid(ctime, rectime, True, True))

            t_total += ntrig
            mon_total +=nmon 
            rec_total +=nrec 
            mon_dark += mon_bad 
            rec_dark += rec_bad

            if False: #np.abs( 1- (nmon/nrec)/(np.array(mon_total)/np.array(rec_total)))>0.2:
                print("SPIKE")
                all_data = {
                    "time":time_sample,
                    "chana":adc2mVChAMax,
                    "chanb":adc2mVChBMax,
                    "chand":adc2mVChDMax
                }
                dfile = h5.File("waveforms.h5", 'w')
                for key in all_data:
                    dfile.create_dataset(key, data=all_data[key])
                dfile.close()

            end = time.time()

            # the number of those crossing times is the number of pulses! 
                        
            nns += len(adc2mVChAMax)*8
                
            loops +=1
            if (time.time() - collection_start)>self.collection_time:
                break
                
        return t_total, mon_total, rec_total, int(mon_dark), int(rec_dark)

