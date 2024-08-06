import time
import sys
import socket
import signal
import multiprocessing
import queue

from . import protocol_http
from . import code_description


class OutsideHTTP:
    def __init__(self,host):
        self.config = {
            "host": ("0.0.0.0",80), # The Host (IP,Port)
            "backlog_length": 50, # Amount of waiting clients allowed
            "max_workers": 150, # Max. amount of ongoing requests (running subprocesses) allowed (includes websockets)
            "process_timeout": 60, # Time until a process with no send/recv activity gets terminated
            "termination_timeout": 5, # Time until a process which is being terminated is getting killed
            "recv_size": 1024, # Receiving packet size
            "send_size": 1024, # Sending packet size
            "keep_alive": True, # Allow more requests after one request is finished over the same socket
            "ssl_enabled": False, # Enable/Disable SSL
            "ssl_keyfile": "", # SSL Private Key File, e.g.: "/etc/letsencrypt/live/billplayz.de/privkey.pem"
            "ssl_certfile": "", # SSL Public Certificate, e.g.: "/etc/letsencrypt/live/billplayz.de/cert.pem"
            "accept_timeout": 1, # Interval between checking running processes for activity
            "max_body_size_mb": 250, # Max. upload (from client) body size
            "allow_range_from_mb": 50, # Request browser to split the request into multiple from x+ MB response size ("FilePath" response only)
            "big_definition_mb": 50, # x MB is considered as "big" and response gets sent with higher transmission speed (increses latency)
            "big_send_limit_mb": 100, # x MB is the max. packet send size for "big" responses
            "post_callback": None, # Call this function with the request and response data for e.g. statistics
            "pre_send": None, # Modify the final response before sending
            "server_cleanup": None # Call this function after the webserver has terminated
        }
        self.config["host"] = host

        self._terminate_process = False
        self._active_requests = []
        self._routes = {}
        self._route_names = []
        self._error_routes = {}
        self._is_halting = False

        def _create_errorhandler(error_code,error_description):
            def _errorhandler(request,message = None):
                if (message == None):
                    message = "No further information."
                return protocol_http.Response(
                    status_code = error_code,
                    headers = {},
                    content = f"{str(error_code)} {error_description} ({message})"
                )
            return _errorhandler
        for error_code,error_description in code_description.code_info.items():
            self.set_errorhandler(error_code,_create_errorhandler(error_code,error_description))

    def set_route(self,route,handler):
        self._routes[route] = handler
        self._route_names.append(route)
        self._route_names.sort(
            key = len,
            reverse = True
        )

    def remove_route(self,route):
        del self._routes[route]

    def set_errorhandler(self,errorcode,handler):
        self._error_routes[errorcode] = handler

    def remove_errorhandler(self,errorcode):
        del self._error_routes[errorcode]

    def terminate(self,signum = None,stackframe = None):
        if (self._is_halting):
            print(f"[MAIN/HTTP - WARN] Multiple signals received.")
            return
        if (signum):
            print(f"[MAIN/HTTP - INFO] Signal {signum} received.")
        else:
            print("[MAIN/HTTP - INFO] No signal received.")
        print(f"[MAIN/HTTP - INFO] Terminating, closing sockets.")
        self._is_halting = True

        self._main_socket.shutdown(socket.SHUT_RDWR)
        self._main_socket.close()
        self._terminate_process = True

        for running_process,activity_queue,process_data in self._active_requests:
            if (self._check_process(running_process)):
                running_process.terminate()
                print(f"[MAIN/HTTP - INFO] Waiting on {process_data['address'][0]} to terminate in final steps.")
                running_process.join(timeout = self.config["termination_timeout"])
                if (self._check_process(running_process)):
                    print(f"[MAIN/HTTP - ERROR] Killing {process_data['address'][0]} in final steps. (Did not terminate!)")
                    running_process.kill()
                else:
                    print(f"[MAIN/HTTP - INFO] {process_data['address'][0]} exited in final steps.")
            else:
                print(f"[MAIN/HTTP - WARN] {process_data['address'][0]} is already terminated in final steps. (Low rate!)")

        self._active_requests = []
        print("[MAIN/HTTP - INFO] All processes have exited.")
        if (self.config["server_cleanup"]):
            print("[MAIN/HTTP - INFO] Running server cleanup.")
            self.config["server_cleanup"]()
        print("[MAIN/HTTP - INFO] Terminated.")
        sys.exit(0)

    def run(self):
        signal.signal(signal.SIGINT,self.terminate)
        signal.signal(signal.SIGTERM,self.terminate)

        self._main_socket = socket.socket(
            family = socket.AF_INET,
            type = socket.SOCK_STREAM
        )
        self._main_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self._main_socket.bind(self.config["host"])
        self._main_socket.settimeout(self.config["accept_timeout"])
        self._main_socket.listen(self.config["backlog_length"])

        print(f"[MAIN/HTTP - INFO] Listening on {str(self.config['host'][1])}.")
        while (not self._terminate_process):
            try:
                if (len(self._active_requests) >= self.config["max_workers"]):
                    time.sleep(self.config["accept_timeout"])
                    raise socket.timeout
                
                accepted_socket,address = self._main_socket.accept()
                print(f"[MAIN/HTTP - INFO] Connected to {address[0]}")
            except socket.timeout:
                current_time = time.time()
                for running_process,activity_queue,process_data in self._active_requests:
                    if (not self._check_process(running_process)):
                        print(f"[MAIN/HTTP - INFO] Removing {process_data['address'][0]}. (Process exited)")
                        self._active_requests.remove((running_process,activity_queue,process_data))
                        continue
                    self._check_process_activity(activity_queue,process_data)
                    if ((current_time - process_data["last_activity"]) >= self.config["process_timeout"]):
                        if (process_data.get("terminating_at")):
                            if ((current_time - process_data["terminating_at"]) >= self.config["termination_timeout"]):
                                print(f"[MAIN/HTTP - ERROR] Killing {process_data['address'][0]}. (Did not terminate!)")
                                running_process.kill()
                                self._active_requests.remove((running_process,activity_queue,process_data))
                        else:
                            print(f"[MAIN/HTTP - INFO] Terminating {address[0]}. (No further activity!)")
                            running_process.terminate()
                            process_data["terminating_at"] = current_time
            except OSError:
                continue
            else:
                new_queue = multiprocessing.Queue()
                new_process = multiprocessing.Process(
                    target = protocol_http.process_request,
                    name = f"[outside] HTTP for {address[0]}:{address[1]}",
                    daemon = False,
                    args = [new_queue,accepted_socket,address,self.config,self._route_names,self._routes,self._error_routes]
                )
                new_process.start()
                self._active_requests.append(
                    (
                        new_process,
                        new_queue,
                        {
                            "last_activity": time.time(),
                            "address": address
                        }
                    )
                )

    def _check_process(self,process):
        return (process.exitcode == None)
    
    def _check_process_activity(self,activity_queue,process_data):
        while True:
            try:
                queue_item = activity_queue.get(block = False)
            except queue.Empty:
                return
            if (process_data["last_activity"] < queue_item):
                process_data["last_activity"] = queue_item

class OutsideHTTP_Redirect:
    def __init__(self,host,destination):
        self.host = host
        self.destination_host = destination
        self._is_started = False

        self.http_server = OutsideHTTP(host)
        self.http_server.config["backlog_length"] = 1
        self.http_server.config["process_timeout"] = 10
        self.http_server.config["termination_timeout"] = 2
        self.http_server.config["keep_alive"] = False
        self.http_server.config["max_body_size_mb"] = 0

        def main_route(request):
            return protocol_http.Response(
                status_code = 301,
                headers = {
                    "Location": f"{self.destination_host}{request.url[1:]}"
                },
                content = ""
            )
        self.http_server.set_route("/",main_route)

    def run(self):
        self.http_server.run()

    def terminate(self):
        self.http_server.terminate()
