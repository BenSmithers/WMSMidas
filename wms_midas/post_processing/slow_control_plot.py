#plot all: 
import matplotlib.pyplot as plt 
import numpy as np

from utils import load_file
from datetime import datetime
import os 

place_temp = ['Sterilizer', 'Tube Lower', 'Tube Upper']
place_pres = ['Input', 'Post-Filter', 'Update', 'Osmosis']
place_flow = ['FLOW[0]', 'FLOW[1]', 'FLOW[2]', 'FLOW[3]', 'FLOW[4]']
place_light = ['Monitor', 'Receiver']
place_volt = ['PMT0', 'PMT1']
place_ADC = ['ADC']

fname = os.path.join(
    "/home", "watermon","online","data","run00164.mid.lz4" 
)

data = load_file(fname)

# read all data and time from slow control 
# Extract values and times
def plot_slow_control(data, bank_name, place, sensor_no, ylabel, ylim, save_plot):   
    bank_data = data["slow_control"][bank_name]["values"]
    bank_times = np.array([datetime.fromtimestamp(entry) for entry in data["slow_control"][bank_name]["times"]])
    
    plt.figure()

    for i in sensor_no:
        sensor_data = [value[i] for value in bank_data if value]
        if max(sensor_data)==0 and min(sensor_data)==0 :
            continue
        plt.plot(bank_times, sensor_data, label=place[i])
    plt.xlabel("Timestamp")
    plt.ylabel(ylabel)
    plt.gcf().autofmt_xdate()
    plt.ylim(ylim)
    #plt.xlim(datetime(2026, 3, 23, 17, 40, 0), None)
    plt.legend(place)
    plt.savefig(
        os.path.join(os.path.dirname(__file__), "plots", save_plot), dpi=400
    )
    plt.clf()

# Plot Temperature
plot_slow_control(data, "TEMP", place_temp, [0,1,2], "Temperature", [8, 21], "temp_result.png")
# Plot Pressure
plot_slow_control(data, "PRES", place_pres, [0,1,2,3], "Pressure", [0, 25], "pres_result.png")
# Plot Flow
plot_slow_control(data, "FLOW", place_flow, [0,1,2,3,4], "Flow Rate", [0, 1.2], "flow_result.png")
# Plot Light
plot_slow_control(data, "LIGH", place_light, [0,1], "Light Level", [0, 0.11], "light_result.png")
# Plot HV
#plot_slow_control(data, "VOLT", place_volt, [0,1], "Voltage Level", [0, 1000], "voltage_result.png")
# Plot ADC
plot_slow_control(data, "ADC0", place_ADC, [0], "ADC Level", [0, 1000], "adc_result.png")