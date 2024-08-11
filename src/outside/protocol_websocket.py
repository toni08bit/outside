import os
import time
import struct
import threading
import traceback
import signal


def toggle_mask(payload_data,mask_key):
    toggled_data = bytearray()
    for byte in range(len(payload_data)):
        toggled_data.append(payload_data[byte] ^ mask_key[byte % 4])
    return toggled_data

class WebSocket:
    def __init__(self):
        self.connection_handler = None

class WebSocketConnection:
    def __init__(self,request_class,http_socket,activity_queue,terminate_function):
        self.request = request_class
        self.on_exit = None
        self._socket = http_socket
        self._activity_queue = activity_queue
        self._terminate = terminate_function
        self._is_terminated = False

        signal.signal(signal.SIGINT,self.exit)
        signal.signal(signal.SIGTERM,self.exit)
        
        pipe_tuple = os.pipe()
        self._recv_thread = threading.Thread(
            target = self._recv_thread_function,
            args = [pipe_tuple[1],self._socket]
        )
        self._recv_thread.start()
        self.pipe = os.fdopen(pipe_tuple[0],"rb")

    def exit(self):
        if (self._is_terminated):
            return
        if (self.on_exit):
            try:
                self.on_exit()
            except Exception:
                print(f"[{self.request.address[0]}:{str(self.request.address[1])} - Error] on_exit has failed:")
                traceback.print_exc()
        try:
            self._send_frame(True,8,b"")
        except Exception:
            pass
        self._is_terminated = True
        self._activity_queue.put(time.time())
        self._terminate()
    
    def recv(self):
        msg_length = struct.unpack("!L",self.pipe.read(4))[0]
        thread_status = struct.unpack("!B",self.pipe.read(1))[0]
        if (thread_status == 0):
            self.exit()
        msg_data = self.pipe.read(msg_length)
        return msg_data
    
    def send(self,data):
        data_length = len(data)
        data_cursor = 0
        while (data_cursor < data_length):
            next_frame = (data_cursor + (8 * 1024 * 1024))
            cursor_limiter = min(next_frame,data_length)
            frame_data = data[data_cursor:cursor_limiter]
            if (data_cursor == 0):
                frame_opcode = 2
            else:
                frame_opcode = 0
            fin_frame = (cursor_limiter == data_length)
            self._send_frame(fin_frame,frame_opcode,frame_data)
            data_cursor = next_frame

    def _recv_thread_function(self,write_pipe,http_socket):
        try:
            while True:
                msg_data = bytearray()
                fin_frame = False
                while (not fin_frame):
                    received_header = http_socket.recv(2)
                    self._activity_queue.put(time.time())

                    header_data = {}

                    header_raw = struct.unpack("!BB",received_header)
                    fin_frame = ((header_raw[0] & 0x80) != 0)
                    header_data["rsv1"] = ((header_raw[0] & 0x80) != 0)
                    header_data["rsv2"] = ((header_raw[0] & 0x80) != 0)
                    header_data["rsv3"] = ((header_raw[0] & 0x80) != 0)
                    header_data["opcode"] = (header_raw[0] & 0x0F)
                    header_data["mask"] = ((header_raw[1] & 0x80) != 0)
                    header_data["mask_key"] = None
                    header_data["payload_length"] = (header_raw[1] & 0x7F)

                    if (header_data["payload_length"] == 126):
                        header_data["payload_length"] = struct.unpack("!H",http_socket.recv(2))[0]
                    elif (header_data["payload_length"] == 127):
                        header_data["payload_length"] = struct.unpack("!Q",http_socket.recv(8))[0]

                    if (header_data["mask"]):
                        header_data["mask_key"] = http_socket.recv(4)

                    payload_data = bytearray()
                    payload_left = header_data["payload_length"]

                    while (payload_left > 0):
                        recv_size = min(payload_left,1)
                        recv_data = http_socket.recv(recv_size)
                        if (not recv_data):
                            self._terminate()
                        payload_data.extend(recv_data)
                        payload_left = (payload_left - len(recv_data))

                    if (header_data["mask"]):
                        payload_data = toggle_mask(payload_data,header_data["mask_key"])

                    if ((header_data["opcode"] == 0) or (header_data["opcode"] == 1) or (header_data["opcode"] == 2)):
                        msg_data.extend(payload_data)
                    elif (header_data["opcode"] == 8):
                        try:
                            self._send_frame(True,8,b"")
                        except Exception:
                            pass
                        raise BrokenPipeError
                    elif (header_data["opcode"] == 9):
                        self._send_frame(True,10,b"")
                
                os.write(write_pipe,struct.pack("!L",len(msg_data)))
                os.write(write_pipe,struct.pack("!B",1))
                os.write(write_pipe,msg_data)
        except Exception:
            os.write(write_pipe,struct.pack("!L",0))
            os.write(write_pipe,struct.pack("!B",1))
            self.exit()

    def _send_frame(self,fin_frame,opcode,payload_data):
        self._activity_queue.put(time.time())
        header_data = bytearray()

        header_data.append((fin_frame << 7) | opcode)

        payload_length = len(payload_data)
        if (payload_length <= 125):
            header_data.append(payload_length | 0x00)
        elif (payload_length <= (2 ** 16 - 1)):
            header_data.append(126 | 0x00)
            header_data.extend(payload_length.to_bytes(2,"big"))
        else:
            header_data.append(127 | 0x00)
            header_data.extend(payload_length.to_bytes(8,"big"))

        self._socket.sendall(bytes(header_data) + bytes(payload_data))
        return