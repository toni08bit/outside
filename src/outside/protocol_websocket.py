import time
import random
import struct


def toggle_mask(payload_data,mask_key):
    toggled_data = bytearray()
    for byte in range(len(payload_data)):
        toggled_data.append(payload_data[byte] ^ mask_key[byte % 4])
    return toggled_data

class WebSocket:
    def __init__(self):
        self.connection_handler = None
        self.exit_handler = None

    def on_connection(self,connection_handler):
        self.connection_handler = connection_handler

    def on_exit(self,exit_handler):
        self.exit_handler = exit_handler

class WebSocketConnection:
    def __init__(self,request_class,http_socket,activity_queue,terminate_function):
        self.request = request_class
        self._socket = http_socket
        self._activity_queue = activity_queue
        self._terminate = terminate_function
        self._is_terminated = False

    def exit(self):
        if (self._is_terminated):
            return
        self._is_terminated = True
        self._activity_queue.put(time.time())
        self._terminate()
    
    def recv(self):
        msg_data = bytearray()
        fin_frame = False
        while (not fin_frame):
            received_header = self._socket.recv(2)
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
                header_data["payload_length"] = struct.unpack("!H",self._socket.recv(2))[0]
            elif (header_data["payload_length"] == 127):
                header_data["payload_length"] = struct.unpack("!Q",self._socket.recv(8))[0]

            if (header_data["mask"]):
                header_data["mask_key"] = self._socket.recv(4)

            payload_data = bytearray()
            payload_left = header_data["payload_length"]

            while (payload_left > 0):
                recv_size = min(payload_left,1)
                recv_data = self._socket.recv(recv_size)
                if (not recv_data):
                    self._terminate()
                payload_data.extend(recv_data)
                payload_left = (payload_left - len(recv_data))

            if (header_data["mask"]):
                payload_data = toggle_mask(payload_data,header_data["mask_key"])

            if ((header_data["opcode"] == 0) or (header_data["opcode"] == 1) or (header_data["opcode"] == 2)):
                msg_data.extend(payload_data)
            elif (header_data["opcode"] == 8):
                self.exit()
            elif (header_data["opcode"] == 9):
                self._send_frame(True,10,b"")
        
        return bytes(msg_data)
    
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

    def _send_frame(self,fin_frame,opcode,payload_data):
        self._activity_queue.put(time.time())
        header_data = bytearray()

        header_data.append((fin_frame << 7) | opcode)

        payload_length = len(payload_data)
        if (payload_length <= 125):
            header_data.append(payload_length | 0x80)
        elif (payload_length <= (2 ** 16 - 1)):
            header_data.append(126 | 0x80)
            header_data.extend(payload_length.to_bytes(2,"big"))
        else:
            header_data.append(127 | 0x80)
            header_data.extend(payload_length.to_bytes(8,"big"))

        mask_key = random.randint(0, 0xFFFFFFFF)

        mask_key_bytes = mask_key.to_bytes(4, 'big')
        masked_payload = toggle_mask(payload_data,mask_key_bytes)

        self._socket.sendall(bytes(header_data) + bytes(mask_key_bytes) + bytes(masked_payload))
        return