from wms_midas.utilities import ELLxConnection, LEDBoard, PicoMeasure 

import numpy as np
from math import sqrt 
import time 

scope = PicoMeasure(True) 
scope.collection_time = 10

TARGET = 0.2
WINDOW = 0.01

stage = ELLxConnection("/dev/ttyUSB0")
led = LEDBoard("/dev/ttyUSB1")
led.disable()
led.enable()

led.set_fast_rate()
led.set_int_trigger()

leds = [1,2,3,4,5,6,7]
positions = [5.5 + i*(14-5.5) for i in range(len(leds))]

adc_success = []

for i in range(len(leds)):
    if i < 4:
        continue
    if leds[i]==7:
        min_adc = 200
    else:
        min_adc = 600
    max_adc = 1000
    next_adc = 810

    led.set_adc(1023)
    msg = led.activate_led(leds[i])
    print(msg)
    msg = stage.move_absolute(positions[i])
    print(msg)
    
    step_count = 0
    while True:
        step_count += 1
        led.set_adc(next_adc)
        print("waiting before msmt")
        time.sleep(10)
        print("ready")

        trig, mon, rec, mond, recd = scope.measure()
        ratio = mon/trig 
        error = sqrt(mon)/trig 
        trig, mon, rec, mond, recd = scope.measure()
        new_ratio = mon/trig 
        if abs(new_ratio - ratio)>5*error:
            print("Too much varation - remeasure")
            trig, mon, rec, mond, recd = scope.measure()
            ratio = mon/trig 

        
    
        if step_count> 10:
            print("ratio was {} and {}, target is {}".format(ratio, new_ratio, TARGET))
            print("Failed to find a good adc for LED {}, last tried {}".format(leds[i], next_adc))
            adc_success.append(-1)
            break 

        if abs(ratio - TARGET) < WINDOW:
            print("Found new ADC {} --> {}".format(next_adc, ratio))
            adc_success.append(next_adc)
            break
        else:
            
            # make it dimmer, set ADC higher
            if ratio>TARGET:
                min_adc = next_adc
                next_adc = int(0.5*(next_adc + max_adc))
            else: # make it brighter, set ADC lower 
                max_adc = next_adc
                next_adc = int(0.5*(next_adc + min_adc))
            print("Observed {} vs {} target; Setting ADC to {}".format(ratio, TARGET, next_adc))
                
    print(adc_success)