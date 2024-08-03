import sys
import socket
import time
import ssl
import traceback
import signal
import struct
import random
import math
import selectors

def process_client(process_queue,connected_socket,address,config):
    start_time = time.time()
    debug_name = f"{address[0]}:{str(address[1])}"

    def terminate(signum = None,stackframe = None):
        close_socket(connected_socket)
        sys.exit(0)

    def close_socket(unknown_socket):
        try:
            unknown_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            unknown_socket.close()
        except OSError:
            pass

    def get_socket():
        if (config["ssl_enabled"]):
            raise NotImplementedError("SSL not implemented yet.")
            return connected_ssl_socket
        else:
            return connected_socket
        
    def recv(recv_size): # TODO add default?
        get_socket().recv(recv_size)
    
    def recv_strict(recv_size):
        recv_data = b""
        while (len(recv_data) < recv_size):
            new_data = get_socket().recv(recv_size - len(recv_data))
            if (len(new_data) == 0):
                raise BrokenPipeError
            recv_data = (recv_data + new_data)
        return recv_data

    def send(data):
        send_size = config["send_size"]
        send_socket = get_socket()
        while (len(data) > 0):
            sent_bytes = send_socket.send(data[:send_size])
            data = data[sent_bytes:]

    def rtmp_timestamp():
        rollover_value = (2 ** 32)
        high_ms = math.floor(time.time() * 1000)
        high_div = (high_ms / rollover_value)
        return int((high_div - math.floor(high_div)) * rollover_value)
    
    def _read_int(data,big_endian = True):
        missing_bytes = (4 - len(data))
        if (missing_bytes < 0):
            raise ValueError
        
        if (big_endian):
            return struct.unpack("!I",((b"\x00" * missing_bytes) + data))[0]
        else:
            return struct.unpack("<I",(data + (b"\x00" * missing_bytes)))[0]
        
    def _read_chunk_timestamp():
        value = _read_int(recv_strict(3))
        if (value == 0xFFFFFF):
            value_bytes = (value_bytes + recv_strict(1))
            value = struct.unpack("!I",value_bytes)[0]
        return value

    signal.signal(signal.SIGINT,terminate)
    signal.signal(signal.SIGTERM,terminate)
    try:
        if (config["ssl_enabled"]):
            try:
                connected_ssl_socket = ssl.wrap_socket(
                    sock = connected_socket,
                    keyfile = config["ssl_keyfile"],
                    certfile = config["ssl_certfile"],
                    server_side = True
                )
            except ssl.SSLError as exception:
                if (exception.reason == "#"): # TODO this for silencing non-rtmps client errors
                    terminate()
                else:
                    raise
        
        # Stream Flow

        ## Handshake
        ### C0
        client_version = recv_strict(1)
        if (client_version != b"\x03"):
            print(f"[{debug_name} - WARN] Client is using non-standard version {str(client_version)}.")
        ### S0
        send(b"\x03")
        ### S1
        s1_time = rtmp_timestamp()
        s1_random = random.randbytes(1528)
        s1_packet = (
            struct.pack("!I",s1_time) +
            struct.pack("!I",0) +
            s1_random
        )
        send(s1_packet)
        ### C1
        c1_time = _read_int(recv_strict(4))
        if (_read_int(recv_strict(4)) != 0):
            print(f"[{debug_name} - WARN] C1 - Not zero.")
        c1_random = recv_strict(1528)
        c1_read = rtmp_timestamp()
        ### S2
        s2_packet = (
            struct.pack("!I",c1_time) +
            struct.pack("!I",c1_read) +
            c1_random
        )
        send(s2_packet)
        ### C2
        if (struct.unpack("!I",recv_strict(4))[0] != s1_time):
            print(f"[{debug_name} - ERROR] Failed C2 - Incorrect timestamp echo.")
            terminate()
        c2_time = _read_int(recv_strict(4))
        c2_random = recv_strict(1528)
        if (c2_random != s1_random):
            print(f"[{debug_name} - ERROR] Failed C2 - Incorrect random echo.")
            terminate()
        
        double_selector = selectors.DefaultSelector()
        double_selector.register(get_socket(),selectors.EVENT_READ,data = "socket")
        double_selector.register(process_queue._reader.fileno(),selectors.EVENT_READ,data = "queue")

        client_data = {
            "chunk_size": 4096
        }
        last_chunk = None
        while True:
            all_events = double_selector.select()
            for key,events in all_events:
                if (key.data == "socket"):
                    new_chunk = Chunk()

                    header_byte = recv_strict(1)[0]
                    new_chunk.format = ((header_byte & 0b11000000) >> 6)
                    new_chunk.chunk_stream_id = (header_byte & 0b00111111)

                    if (new_chunk.chunk_stream_id == 0):
                        second_byte = recv_strict(1)[0]
                        new_chunk.chunk_stream_id = (second_byte + 64)
                    elif (new_chunk.chunk_stream_id == 1):
                        second_byte = recv_strict(1)[0]
                        third_byte = recv_strict(1)[0]
                        new_chunk.chunk_stream_id = ((third_byte * 256) + second_byte + 64)
                    
                    if (new_chunk.format == 0):
                        new_chunk.timestamp = _read_chunk_timestamp()
                        new_chunk.message_length = _read_int(recv_strict(3))
                        new_chunk.message_type_id = _read_int(recv_strict(1))
                        new_chunk.message_stream_id = _read_int(recv_strict(4))
                        pass # TODO
                    else:
                        if (not last_chunk):
                            print(f"[{debug_name} - ERROR] Missing type 0 chunk.")
                            terminate()
                        if (new_chunk.format == 1):
                            new_chunk.timestamp = _read_chunk_timestamp()
                            new_chunk.message_length = _read_int(recv_strict(3))
                            new_chunk.message_type_id = _read_int(recv_strict(1))

                            new_chunk.message_stream_id = last_chunk.message_stream_id

                            pass # TODO
                        elif (new_chunk.format == 2):
                            new_chunk.timestamp = _read_chunk_timestamp()

                            new_chunk.message_length = last_chunk.message_length
                            new_chunk.message_type_id = last_chunk.message_type_id
                            new_chunk.message_stream_id = last_chunk.message_stream_id

                            pass # TODO
                        elif (new_chunk.format == 3):
                            new_chunk = last_chunk
                            new_chunk.message = None

                            pass # TODO
                    
                    if (new_chunk.message_length > 0):
                        new_chunk.message = recv_strict(new_chunk.message_length)

                    print(new_chunk.chunk_stream_id)
                    print(new_chunk.message_type_id)
                    if (new_chunk.chunk_stream_id == 2 or True):
                        if (new_chunk.message_stream_id == 0):
                            if (new_chunk.message_type_id == 1): # Set Chunk Size
                                new_chunk_size = _read_int(new_chunk.message)
                                if ((new_chunk_size > 0x7FFFFFFF) or (new_chunk_size < 1)):
                                    print(f"[{debug_name} - ERROR] Invalid Chunk Size is {str(new_chunk_size)}B.")
                                    terminate()
                                client_data["chunk_size"] = new_chunk_size
                                print(f"[{debug_name} - INFO] New Chunk Size is {str(new_chunk_size)}B.")
                            elif (new_chunk.message_type_id == 2): # Abort
                                pass # TODO
                            elif (new_chunk.message_type_id == 3): # Acknowledge
                                pass # TODO
                            elif (new_chunk.message_type_id == 5): # Window Acknowledgement Size
                                pass # TODO
                            elif (new_chunk.message_type_id == 6): # Set Peer Bandwidth
                                pass # TODO
                            elif (new_chunk.message_type_id == 4): # User Control Message
                                event_type = recv_strict(2)
                                print(event_type) # TODO
                            
                            elif ((new_chunk.message_type_id == 20) or (new_chunk.message_type_id == 17)): # Command Message AMF
                                pass # TODO
                            elif (new_chunk.message_type_id == 18): # Data Message AMF0
                                pass # TODO
                            elif (new_chunk.message_type_id == 15): # Data Message AMF3
                                pass # TODO
                            elif (new_chunk.message_type_id == 19): # Shared Object Message AMF0
                                pass # TODO
                            elif (new_chunk.message_type_id == 16): # Shared Object Message AMF3
                                pass # TODO
                            elif (new_chunk.message_type_id == 8): # Audio Message
                                pass # TODO
                            elif (new_chunk.message_type_id == 9): # Video Message
                                pass # TODO
                            elif (new_chunk.message_type_id == 22): # Aggregate Message
                                pass # TODO

                    last_chunk = new_chunk
                elif (key.data == "queue"):
                    pass # TODO pipe announcement
    
    except (BrokenPipeError,ConnectionResetError) as exception:
        print(f"[{debug_name} - ERROR] Connection interrupted.")

    except ssl.SSLError as exception:
        print(f"[{debug_name} - ERROR] SSL exception: {str(exception)}")

    except Exception as exception:
        print(f"[{debug_name} - ERROR] Unexpected exception:")
        traceback.print_exc()

    finally:
        close_socket(connected_socket)
        sys.exit(1)

class Chunk:
    def __init__(self):
        self.format = None
        self.chunk_stream_id = None
        self.timestamp = None
        self.message_type_id = None
        self.message_stream_id = None
        self.message_length = None
        self.message = None