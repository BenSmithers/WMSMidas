# data are in ascii format and in hexadecimal notation 


from enum import Enum 


"""
    Each call has, in the documentation for the ELLx board, a set of expected Responses. 

    Each of those responses has been implemented below with the associated "key" that will be present in the response header. 
    Here, we present the code to tabulate all known response keys. 
    Then, when a response is received, the second two bytes are compared against the known keys.
    The proper Response decoder is called, and the decoded quantities are returned. 

    If the key matches no known decoder, a KeyError is thrown.
"""
def _all_subclasses(cls:'Response'):
    """
        Returns either a list of the names of all subclasses of `cls`, or a list of the classes themselves
    """

    return list(set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in _all_subclasses(c)]))
def _get_message_map()->'dict[str,Response]':
    all_responses = _all_subclasses(Response)
    return {
        entry.key:entry for entry in all_responses
    }
def response_handler(full_response:bytes):
    """
        First, build a map of the known responses 
        Check this response type against the map
        And call the relevant Response decoder
    """
    message_map = _get_message_map()
    this_key = full_response[1:3].decode()

    if this_key not in message_map.keys():
        raise KeyError("Unsure how to handle key {}".format(this_key))
    else:
        return message_map[this_key].decode(full_response)



class DecoderType(Enum):
    Word=0
    SignedLong=1
    UnsignedLong=2 

def _decode_word(reply:bytes)->str:
    return reply.decode()
def _encode_word(reply:str)->bytes:
    return reply.encode()

def _decode_signed_long(reply:bytes)->int:
    """
        Assumes any headers or end of line characters are already removed! 
    """
    decoded = reply.decode()
    # reply will be a signed bit

    flip = decoded[0]!='0'
    package_len = len(decoded)    

    if flip:
        count_from = int("F"*package_len, 16)*-1 -1
    else:
        count_from = 0

    return count_from + int(decoded[:],16)

def _encode_signed_long(value, nbytes)->str:
    if value <0:
        adjusted = value - int("F"*nbytes, 16)*-1 +1
        return hex(adjusted)[2:].upper().encode()
    else:
        raw_hex = hex(value)[2:].upper()
        return ("0"*(nbytes-len(raw_hex)) + raw_hex).upper().encode()



def _encode_unsigned_long(value:int, nbytes:int)->str:
    """
        value should already be in pulses. No conversion takes place here! 
    """

    return hex(value)[2:].zfill(nbytes).upper().encode()

def _decode_unsigned_long(reply:bytes):
    return int(reply.decode(), 16)

def decode(sub_val:bytes, dt:DecoderType):
    if dt.value == DecoderType.Word.value:
        return _decode_word(sub_val)
    elif dt.value == DecoderType.UnsignedLong.value:
        return _decode_unsigned_long(sub_val) 
    elif dt.value == DecoderType.SignedLong.value:
        return _decode_signed_long(sub_val) 
    else:
        raise NotImplementedError("Unknown decoder type: {}".format(dt))

def encode(sub_val, dt:DecoderType, nbytes=-1)->str:
    """
        Encode data according to a schema identified by DecoderType. 
        Functions as the inverse of the `decode` method
    """
    if dt.value == DecoderType.Word.value:
        return _encode_word(sub_val)
    elif dt.value == DecoderType.UnsignedLong.value:
        return _encode_unsigned_long(sub_val, nbytes) 
    elif dt.value == DecoderType.SignedLong.value:
        return _encode_signed_long(sub_val, nbytes) 
    else:
        raise NotImplementedError("Unknown decoder type: {}".format(dt))  

class Message:
    """
        This is the fundamental class for all of the messages sent to or received from the board. 

        There is a symmetry presented where each message to the ELLx board is a Call
        Then, it responds, and the Response decoders parse the messages.
    """
    key="XX"
    def __init__(self, *args):
        self._args = args

class Call(Message):
    """
        The `Call` class represents a call _to_ the ELLx board. 
        This is a request for information, or an instruction to move. 

        All Calls follow the same encoding procedure. 
        The encoding method expets a number of arguments consistent with the class. 

        The `key` now represents the key the board expects for this specific call. IE `sv` for Set Velocity. 
    """
    args = [] 

    @classmethod 
    def encode(cls, *args):
        assert len(cls.args)==len(args)
        bytes_msg= ("0"+cls.key).encode()
        for i, entry in enumerate(args):
            bytes_msg += encode(entry, cls.args[i][1], cls.args[i][0])
        bytes_msg+="\n".encode()
        return bytes_msg

class Response(Message):
    """
        This class represents the decoder. 
        the `key` now represents the response key that this corresponds to. 

        A `reply` attribute is included as a list of length-2 lists specifiying how the data are formatted in the response. 
        The pre-provided ones here represents the 
                1 - byte representing the associated board.
                2 - two bytes representing the response key

        Subclasses of Response increase the number of entries for each separate quantity provided in the response data packet. 
        The most extreme example is the InfoDump, with 33 bytes of data
    """
    # This should be a series of length-2 lists for [byte number - decoder type]
    reply=[
        [1, DecoderType.Word],
        [2, DecoderType.Word]
    ]
    @classmethod
    def decode(cls, retval:bytes):
        """
            For each expected entry in the return bytes, decode it and add it to a response list
            Then, return the responses
        """
        response = []
        bit_counter = 0
        for entry in cls.reply:
            these = retval[bit_counter:(bit_counter+entry[0])]
            bit_counter += entry[0]
            response.append(decode(these, entry[1])) 
        return response

# ======================== RESPONSES ===================
class GetStatus(Response):
    key = "GS"
    reply = Response.reply + [
        [2, DecoderType.Word]
    ]

class InfoDump(Response):
    key="IN"
    reply = Response.reply + [
        [2, DecoderType.Word], # bi positional slider
        [8, DecoderType.Word], # serial no 
        [4, DecoderType.Word], # year of manufacture
        [2, DecoderType.Word], # firmware ver
        [2, DecoderType.Word], # most significant bit signifies thread type? 
        [4, DecoderType.Word], # 31 mm travel
        [8, DecoderType.SignedLong], # 1 pulse per position?
    ]

class GetPosition(Response):
    key = "AP"
    reply = Response.reply +[
        [8, DecoderType.SignedLong]
    ]
class Position(Response):
    key="PO"
    reply=Response.reply+[ 
        [8, DecoderType.SignedLong]
    ]
class HomeOffset(Response):
    key="HO"
    reply=Response.reply + [
        [8, DecoderType.SignedLong]
    ]


class JogResponse(Response):
    key="GJ"
    reply= Response.reply+[
        [8, DecoderType.SignedLong]
    ]
class VelocityResponse(Response):
    key="GV"
    reply = Response.reply+[ 
        [2, DecoderType.UnsignedLong]
    ]

# ======================== CALLS ===================
class RequestStatus(Call):
    key="gs"
class RequestInfo(Call):
    key="in"
class RequestJog(Call):
    key="gj"
class Isolate(Call):
    key="is"
    args=[
        [2, DecoderType.UnsignedLong]
    ]
class SetHome(Call):
    key="so"
    args=[
        [8, DecoderType.SignedLong]
    ]
class GoHome(Call):
    key = "go"
class RequestPosition(Call):
    key="gp"
class SetJog(Call):
    key="sj"
    args=[
        [8, DecoderType.SignedLong]
    ]
class StepForward(Call):
    key="fw"
class StepBackward(Call):
    key="bw"
class Stop(Call):
    key="st"
class MoveAbsolute(Call):
    key="ma"
    args=[
        [8, DecoderType.SignedLong]
    ]
class MoveRelative(Call):
    key="mr"
    args=[
        [8, DecoderType.SignedLong]
    ]
class GetVeolicty(Call):
    key="gv"
class SetVelocity(Call):
    key="sv"
    args=[
        [2, DecoderType.UnsignedLong]
    ]
class Stop(Call):
    key="st"