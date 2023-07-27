import time
import socket
import signal
import multiprocessing

import outside.protocol_http as protocol_http
import outside.code_description as code_description


class OutsideHTTP:
    def __init__(self,host):
        self.config = {
            "host": ("0.0.0.0",80),
            "backlog_length": 25,
            "process_timeout": 60,
            "termination_timeout": 5,
            "recv_size": 1024,
            "send_size": 1024,
            "accept_timeout": 0.02,
            "ssl_enabled": False,
            "ssl_keyfile": "",
            "ssl_certfile": "",
            "max_body_size_mb": 250,
            "keep_alive": True
        }
        self.config["host"] = host

        self._terminate_process = False
        self._active_requests = []
        self._routes = {}
        self._route_names = []
        self._error_routes = {}

        def _create_errorhandler(error_code,error_description):
            def _errorhandler(request,message = None):
                if (message == None):
                    message = "No further information."
                return protocol_http.Response(
                    request = request,
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
        if (signum):
            print(f"[MAIN - INFO] Signal {signum} received.")
        else:
            print("[MAIN - INFO] No signal received.")
        print(f"[MAIN - INFO] Terminating, closing sockets.")

        self._main_socket.shutdown(socket.SHUT_RDWR)
        self._main_socket.close()
        self._terminate_process = True

        for running_process in self._active_requests:
            if (self._check_process(running_process)):
                running_process.terminate()
                print(f"[MAIN - INFO] Waiting on {running_process._socket_address[0]} to terminate in final steps.")
                running_process.join(timeout = self.config["termination_timeout"])
                if (self._check_process(running_process)):
                    print(f"[MAIN - ERROR] Killing {running_process._socket_address[0]} in final steps. (Did not terminate!)")
                    running_process.kill()
                else:
                    print(f"[MAIN - INFO] {running_process._socket_address[0]} exited in final steps.")
            else:
                print(f"[MAIN - WARN] {running_process._socket_address[0]} is already terminated in final steps.")

        self._active_requests = []
        print(f"[MAIN - INFO] All processes have exited. Done!")

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

        print("[MAIN - INFO] Listening.")
        while (not self._terminate_process):
            try:
                accepted_socket,address = self._main_socket.accept()
                print(f"[MAIN - INFO] Connected to {address[0]}")
            except socket.timeout:
                current_time = time.time()
                for running_process in self._active_requests:
                    if (not self._check_process(running_process)):
                        print(f"[MAIN - INFO] Removing {running_process._socket_address[0]}. (Process exited)")
                        self._active_requests.remove(running_process)
                        continue
                    if ((current_time - running_process._started_at) >= self.config["process_timeout"]):
                        if (hasattr(running_process,"_terminating_at")):
                            if ((current_time - running_process._terminating_at) >= self.config["termination_timeout"]):
                                print(f"[MAIN - ERROR] Killing {running_process._socket_address[0]}. (Did not terminate!)")
                                running_process.kill()
                                self._active_requests.remove(running_process)
                        else:
                            print(f"[MAIN - WARN] Terminating {address[0]}.")
                            running_process.terminate()
                            running_process._terminating_at = current_time
            except OSError:
                continue
            else:
                new_process = multiprocessing.Process(
                    target = protocol_http.process_request,
                    name = f"(outside subprocess) HTTP Request from {address[0]}:{address[1]}",
                    daemon = True,
                    args = [accepted_socket,address,self.config,self._route_names,self._routes,self._error_routes]
                )
                new_process.start()
                new_process._started_at = time.time()
                new_process._socket_address = address
                self._active_requests.append(new_process)

    def _check_process(self,process):
        return (process.exitcode == None)
