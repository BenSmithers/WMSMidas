import hid 
VEND_ID = 2478
PROD_ID = 12310 
SNO = "3533CV4SM89AA00500"
ENCODING = 'latin-1'
PATH = "/dev/hidraw0"


# these were observed to change from the plugged-state to the unplugged-state 
important = [
    24,25,27,28,32,34, 35, 49, 50, 
]

def decoder(bytes):
    return ''.join([str(byte) for byte in bytes])

class UPS:
    def __init__(self):
        self.handle = hid.Device(vid=VEND_ID, pid=PROD_ID, path=PATH.encode())
        
    def read_status(self):
        n_bytes = 64
        rval = decoder(self.handle.get_feature_report(34, n_bytes))
    
        data = {
            "on_ac": not (rval=="34330")
        }
        return data 
