import matplotlib.pyplot as plt 
import numpy as np

from utils import load_file, average, fold
from datetime import datetime
import os 

def get_color(n, colormax=3.0, cmap="viridis"):
    """
        Discretize a colormap. Great getting nice colors for a series of trends on a single plot! 
    """
    this_cmap = plt.get_cmap(cmap)
    return this_cmap(n/colormax)



wavelens = [450, 410, 365, 295, 278, 255, 235]

rno = 190
fname = os.path.join(
    "/home", "watermon","online","data","run00{}.mid.lz4".format(rno) 
)

data = load_file(fname)

NFOLD = 10



unique_waves = np.unique(data["waves"])

to_plot = data["rec"] / data["mon"]

triggers = data["triggers"]
monitor = data["mon"]
rec = data["rec"]


metric = np.log((triggers - rec)/(triggers))/np.log((triggers-monitor)/(triggers))
#log_metric = np.log(metric)

start  =datetime(2026, 5, 2, 12, 0, 0)
end  =datetime(2027, 5, 2, 0, 0, 0)

for i, wv in enumerate(unique_waves):
    # this is the darkrate measurement
    if wv == -1 or wv ==8 :
        continue
    mask = data["waves"]==wv 

    times = average(data["times"][mask], NFOLD)
    times = np.array([datetime.fromtimestamp(entry) for entry in times])

    this_metric = fold(metric[mask], NFOLD)

    tmask = np.logical_and(times>start, times<end)

    plt.plot(times[tmask], 100*(this_metric[tmask] - np.mean(this_metric[tmask])) / np.mean(this_metric[tmask]), 'o-', label= "{}nm".format(wavelens[wv-1]), markersize=2, color=get_color(i+1, 9, 'nipy_spectral_r'))  # with markers


plt.xlabel("Timestamp")
plt.ylabel("% Change")
plt.gcf().autofmt_xdate()
#plt.ylim([-1,1])
#plt.yscale('log')
#plt.xlim([datetime(2026, 4, 30, 15, 30, 0), datetime(2026, 4, 30, 18, 30, 0)])
plt.legend(ncol=2)
plt.tight_layout()
plt.savefig(
    os.path.join(os.path.dirname(__file__), "plots", "result_{}.png".format(rno)), dpi=400
)

