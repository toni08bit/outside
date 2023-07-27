import json
import traceback
import sys
import mimetypes
import time
import http.cookies
import socket
import signal
import ssl

import outside.code_description

def process_request(connected_socket,address,config,route_names,routes,error_routes,is_reused = False):
    start_time = time.time()

    def close_socket(unknown_socket):
        try:
            unknown_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            unknown_socket.close()
        except OSError:
            pass

    def terminate(signum = None,stackframe = None):
        close_socket(connected_socket)
        sys.exit(0)

    def recv(recv_size = config["recv_size"]):
        if (config["ssl_enabled"]):
            return connected_ssl_socket.recv(recv_size)
        else:
            return connected_socket.recv(recv_size)
        
    def send(data):
        send_socket = connected_socket
        if (config["ssl_enabled"]):
            send_socket = connected_ssl_socket

        while (len(data) > 0):
            send_socket.send(data[:config["send_size"]])
            data = data[config["send_size"]:]

    try:
        signal.signal(signal.SIGINT,terminate)
        signal.signal(signal.SIGTERM,terminate)

        if (config["ssl_enabled"]):
            if (is_reused):
                connected_ssl_socket = connected_socket
            else:
                try:
                    connected_ssl_socket = ssl.wrap_socket(
                        sock = connected_socket,
                        keyfile = config["ssl_keyfile"],
                        certfile = config["ssl_certfile"],
                        server_side = True
                    )
                except ssl.SSLError as exception:
                    if (exception.reason == "HTTP_REQUEST"):
                        terminate()
                    else:
                        raise

        # Begin Request Flow
        request_class = Request("NONE",{},b"","HTTP/-1","/",address)
        # Receive Request Info + Headers
        print(f"[{address[0]} - INFO] Waiting for request info.")
        header_lines = [b""]
        while True:
            try:
                recv_data = recv()
                if (len(recv_data) == 0):
                    raise BrokenPipeError
                recv_data = recv_data.replace(b"\r",b"")
                header_split = recv_data.split(b"\n\n")
                if (len(header_split) > 1):
                    request_class.content = recv_data[(len(header_split[0]) + 2):]
                    recv_data = header_split[0]
                recv_data = recv_data.split(b"\n")
                header_lines[len(header_lines) - 1] = (header_lines[len(header_lines) - 1] + recv_data[0])
                header_lines = (header_lines + recv_data[1:])
                if (header_lines[len(header_lines) - 1] == b""):
                    header_lines = header_lines[:-2]
                    break
                if (len(header_split) > 1):
                    break
            except BrokenPipeError:
                print(f"[{address[0]} - WARN] Pipe broken, releasing process.")
                terminate()

        split_preline = header_lines[0].decode("utf-8").split(" ")
        request_class.method = split_preline[0]
        request_class.url = split_preline[1]
        request_class.version = split_preline[2]

        for header_line in header_lines[1:]:
            split_line = header_line.decode("utf-8").split(": ")
            request_class.headers[split_line[0]] = split_line[1]

        # Receive Body
        if (request_class.headers.get("Content-Length")):
            request_class.headers["Content-Length"] = int(request_class.headers["Content-Length"])
            if (not request_class.content):
                request_class.content = b""
            print(f"[{address[0]} - INFO] Receiving content.")
            if (request_class.headers["Content-Length"] > (config["max_body_size_mb"] * 1024 * 1024)):
                print(f"[{address[0]} - WARN] Content-Length is too high, releasing process.")
                terminate()
            while (len(request_class.content) < request_class.headers["Content-Length"]):
                recv_data = recv(min((request_class.headers["Content-Length"] - len(request_class.content)),config["recv_size"]))
                request_class.content = (request_class.content + recv_data)
            print(f"[{address[0]} - INFO] Received {str(len(request_class.content))}B content.")

        # Check Route
        responding_route = None
        for route_name in route_names:
            if (request_class.url.startswith(route_name)):
                responding_route = routes[route_name]
                break
        if (not responding_route):
            responding_route = error_routes[404]

        # Respond
        request_class._extract_cookies()
        scheduled_response_class = ScheduledResponse(request_class,responding_route,error_routes)
        response_class = scheduled_response_class.run()
        if (not response_class):
            print(f"[{address[0]} - WARN] ScheduledResponse did not return Response, releasing process.")
            terminate()
        
        socket_keep_alive = False
        if ((config["keep_alive"]) and (request_class.headers.get("Connection") == "keep-alive")):
            response_class.headers["Connection"] = "keep-alive"
            socket_keep_alive = True
        else:
            response_class.headers["Connection"] = "close"

        response_data = (b"HTTP/1.1 " + str(response_class.status_code).encode("utf-8") + b" " + outside.code_description.get_description(response_class.status_code).encode("utf-8") + b"\n")

        for header_name in response_class.headers:
            header_value = response_class.headers[header_name]
            if (isinstance(header_value,int)):
                header_value = str(header_value)
            response_data = (response_data + header_name.encode("utf-8") + b": " + header_value.encode("utf-8") + b"\n")

        if (response_class.headers.get("Set-Cookie")):
            print(f"[{address[0]} - ERROR] Set-Cookie header was returned by ScheduledResponse, use add_cookie instead.")
            terminate()
        for cookie_name,cookie_value in response_class.cookies.items():
            response_data = (response_data + b"Set-Cookie: " + cookie_name.encode("utf-8") + b"=" + cookie_value.value.encode("utf-8"))
            if (cookie_value.max_age):
                response_data = (response_data + f"; Max-Age={str(cookie_value.max_age)}".encode("utf-8"))
            if (cookie_value.domain):
                response_data = (response_data + f"; Domain={cookie_value.domain}".encode("utf-8"))
            if (cookie_value.http_only):
                response_data = (response_data + f"; HttpOnly".encode("utf-8"))
            if (cookie_value.secure):
                response_data = (response_data + f"; Secure".encode("utf-8"))
            if (cookie_value.path):
                response_data = (response_data + f"; Path={cookie_value.path}".encode("utf-8"))
            if (cookie_value.same_site):
                response_data = (response_data + f"; SameSite={cookie_value.same_site}".encode("utf-8"))
            response_data = (response_data + b"\n")

        response_data = (response_data + b"\n" + response_class.content)

        print(f"[{address[0]} - INFO] Sending response.")
        send(response_data)
        print(f"[{address[0]} - INFO] Code {str(response_class.status_code)} in {str((time.time() - start_time) / 1000)}ms.")
        if (socket_keep_alive):
            print(f"[{address[0]} - INFO] Waiting for further requests.")
            reuse_socket = connected_socket
            if (config["ssl_enabled"]):
                reuse_socket = connected_ssl_socket
            process_request(reuse_socket,address,config,route_names,routes,error_routes,True)
        terminate()

    except Exception as exception:
        print(f"[{address[0]} - ERROR] Unexpected exception:")
        traceback.print_exc()
        close_socket(connected_socket)
        sys.exit(1)

class Request:
    def __init__(self,method,headers,content,version,url,address):
        self.method = method
        self.headers = headers
        self.cookies = None
        self.content = content
        self.version = version
        self.url = url
        self.params = {}
        self.address = address

    def _extract_cookies(self):
        if (self.headers.get("Cookie")):
            self.cookies = http.cookies.SimpleCookie()
            self.cookies.load(self.headers["Cookie"])
            cookie_items = self.cookies.items()
            self.cookies = {}
            for cookie_name,cookie_value in cookie_items:
                self.cookies[cookie_name] = cookie_value.value
        else:
            self.cookies = {}

    def json(self):
        try:
            return json.loads(self.content.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        except UnicodeDecodeError:
            return None

class Response:
    def __init__(self,request,status_code,headers,content,cookies = {}):
        self.request = request
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.cookies = cookies

class ScheduledResponse:
    def __init__(self,request,route_function,error_routes):
        self.request = request
        self.route_function = route_function
        self.error_routes = error_routes

    def run(self):
        generated_response = None
        try:
            generated_response = self.route_function(self.request)
            if (type(generated_response) != Response):
                generated_response = self.error_routes[generated_response[0]](self.request,generated_response[1])
        except Exception as exception:
            print(f"[{self.request.address[0]} - ERROR] Unexpected server error:")
            traceback.print_exc()
            try:
                generated_response = self.error_routes[500](self.request,f"Unexpected Exception: {exception.__class__.__name__}")
            except Exception:
                print(f"[{self.request.address[0]} - ERROR] Unexpected error-route error: (releasing process)")
                traceback.print_exc()

        if (not generated_response):
            return None

        if (not generated_response.headers.get("Content-Type")):
            if (isinstance(generated_response.content,str)):
                generated_response.headers["Content-Type"] = "text/plain"
                generated_response.content = generated_response.content.encode("utf-8")
            elif (isinstance(generated_response.content,FilePath)):
                generated_response.headers["Content-Type"] = mimetypes.guess_type(generated_response.content.path)
                generated_response.content = generated_response.content.read()
            elif (isinstance(generated_response.content,dict)):
                generated_response.headers["Content-Type"] = "application/json"
                generated_response.content = json.dumps(generated_response.content).encode("utf-8")
            elif (isinstance(generated_response.content,bytes)):
                generated_response.headers["Content-Type"] = "text/plain"
            else:
                print(f"[{self.request.address[0]} - ERROR] Return type invalid.")
                return None
        else:
            print(f"[{self.request.address[0]} - ERROR] Response content type is not supported.")
            raise NotImplementedError

        generated_response.headers["Content-Length"] = len(generated_response.content)
                    
        return generated_response

class Websocket:
    def __init__(self):
        pass # TODO

class FilePath:
    def __init__(self,path):
        self.path = path
        self._content = None

    def read(self,twice = False):
        if (twice or (not self._content)):
            open_file = open(self.path,"rb")
            self._content = open_file.read()
            open_file.close()
        return self._content
    
class ResponseCookie:
    def __init__(self,value,max_age,domain,http_only,secure,path,same_site):
        self.value = value
        self.max_age = max_age
        self.domain = domain
        self.http_only = bool(http_only)
        self.secure = bool(secure)
        self.path = path
        self.same_site = same_site
