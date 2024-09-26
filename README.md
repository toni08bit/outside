# `outside` Module

The `outside` module provides an HTTP and WebSocket server implementation with extensive customization options, error handling, and request/response management. It is designed to facilitate the creation of HTTP servers with dynamic routing, SSL support, and WebSocket functionality. It works similar to other projects (e.g. Flask), but does not require any other programs like nginx.

## Getting Started

There is a [Quick Start](QUICKSTART.md) available.

### Example Usage

```python
from outside import OutsideHTTP

# Create an HTTP server instance
server = OutsideHTTP(("127.0.0.1", 8080))

# Define a simple route handler
def hello_world(request):
    return Response(
        status_code = 200,
        headers = {"Content-Type": "text/plain"},
        content = "Hello, World!"
    )

# Add the route to the server
server.set_route("/hello", hello_world)

# Start the server
server.run()
```

## Contents
- [Classes](#classes)
  - [OutsideHTTP](#outsidehttp)
  - [OutsideHTTP_Redirect](#outsidehttp_redirect)
  - [WebSocket](#websocket)
  - [WebSocketConnection](#websocketconnection)
  - [Request](#request)
  - [Response](#response)
  - [ScheduledResponse](#scheduledresponse)
  - [FilePath](#filepath)
  - [ResponseCookie](#responsecookie)
- [Functions](#functions)
  - [get_insensitive_header](#get_insensitive_header)
  - [get_description](#get_description)

## Classes

DISCLAIMER: Classes/Functions/Methods marked with *(!)* are typically not required to be created by the user of the module.

### `OutsideHTTP`
```python
class OutsideHTTP(host: tuple[str, int])
```
A class that represents an HTTP server with configurable settings, dynamic routing, and error handling.

#### Parameters
- `host`: A tuple containing the IP address and port where the server will be hosted.

#### Methods

- `set_route(route: str, handler: Callable) -> None`
  - Adds a new route to the server.
  - **Parameters:**
    - `route`: A string representing the URL path for the route.
    - `handler`: A callable function that handles requests to the route.
  - **Example:**
    ```python
    server.set_route("/api/data", data_handler)
    ```

- `remove_route(route: str) -> None`
  - Removes an existing route from the server.
  - **Parameters:**
    - `route`: The route to remove.
  - **Example:**
    ```python
    server.remove_route("/api/data")
    ```

- `set_errorhandler(errorcode: int, handler: Callable) -> None`
  - Sets a custom error handler for a specific HTTP status code.
  - **Parameters:**
    - `errorcode`: HTTP status code for which the error handler is set.
    - `handler`: A callable function that handles errors for the specified code.
  - **Example:**
    ```python
    def not_found_handler(request, message=None):
        return Response(status_code=404, headers={}, content="Not Found")
    
    server.set_errorhandler(404, not_found_handler)
    ```

- `remove_errorhandler(errorcode: int) -> None`
  - Removes an existing error handler for a specific HTTP status code.
  - **Parameters:**
    - `errorcode`: The error code for which the handler will be removed.

- `terminate(signum: Optional[int] = None, stackframe: Optional = None) -> None`
  - Gracefully terminates the server and all active connections.

- `run() -> None`
  - Starts the HTTP server and begins listening for connections.
  - **Example:**
    ```python
    # Start the HTTP server
    server.run()
    ```

#### Attributes

- `config`: A dictionary containing various server configuration options such as `host`, `backlog_length`, `max_workers`, `process_timeout`, and others.
- `_terminate_process`: A boolean flag indicating whether the server should terminate.
- `_active_requests`: A list of active HTTP requests.
- `_routes`: A dictionary of routes and their corresponding handlers.
- `_error_routes`: A dictionary of error handlers for HTTP status codes.

### `OutsideHTTP_Redirect`
```python
class OutsideHTTP_Redirect(host: tuple[str, int], destination: str)
```
A class that represents an HTTP server that redirects all incoming requests to a specified destination.

#### Parameters
- `host`: A tuple containing the IP address and port where the server will be hosted.
- `destination`: The destination URL to which all incoming requests will be redirected.

#### Methods

- `run() -> None`
  - Starts the redirect server and begins listening for connections.

- `terminate() -> None`
  - Terminates the redirect server.

#### Example
```python
redirect_server = OutsideHTTP_Redirect(("127.0.0.1", 80), "https://example.com")
redirect_server.run()
```

### `WebSocket`
```python
class WebSocket
```
A class that facilitates WebSocket connections and message handling.

#### Methods

- `on_connection(handler: Callable) -> None`
  - Sets the handler function for incoming WebSocket connections.
  - **Parameters:**
    - `handler`: A callable function that handles WebSocket connections.
  - **Example:**
    ```python
    def websocket_handler(connection):
        while True:
            message = connection.recv()
            connection.send(message)  # Echo back the message
    
    websocket_server = WebSocket()
    websocket_server.on_connection(websocket_handler)
    ```

- `on_exit(handler: Callable) -> None`
  - Sets the handler function to be called when the WebSocket connection is closed.
  - **Parameters:**
    - `handler`: A callable function that handles WebSocket exit events.

### `WebSocketConnection` *(!)*
```python
class WebSocketConnection(request_class: Request, http_socket: socket.socket, activity_queue: multiprocessing.Queue, terminate_function: Callable)
```
A class that manages an individual WebSocket connection.

#### Methods

- `recv() -> bytes`
  - Receives data from the WebSocket connection.
  - **Returns:** The received data as bytes.

- `send(data: bytes) -> None`
  - Sends data to the WebSocket connection.
  - **Parameters:**
    - `data`: The data to send, as bytes.

- `exit() -> None`
  - Terminates the WebSocket connection.

### `Request` *(!)*
```python
class Request(method: str, headers: dict, content: bytes, version: str, url: str, address: tuple[str, int])
```
A class that represents an HTTP request.

#### Methods

- `json() -> Optional[dict]`
  - Parses the request content as JSON.
  - **Returns:** The parsed JSON data as a dictionary, or `None` if parsing fails.
  - **Example:**
    ```python
    request_data = request.json()
    if request_data:
        print(request_data)
    ```

#### Attributes

- `method`: The HTTP method of the request (e.g., 'GET', 'POST').
- `headers`: A dictionary of the request headers.
- `cookies`: A dictionary of cookies included in the request.
- `content`: The body content of the request.
- `version`: The HTTP version used in the request.
- `url`: The URL of the request.
- `params`: A dictionary of URL query parameters.
- `address`: A tuple containing the client's IP address and port.

### `Response` *(!)*
```python
class Response(status_code: int, headers: dict, content: Union[str, bytes, FilePath], cookies: dict = {})
```
A class that represents an HTTP response.

#### Attributes

- `status_code`: The HTTP status code of the response (e.g., 200, 404).
- `headers`: A dictionary of response headers.
- `content`: The response content, which can be a string, bytes, or a `FilePath` object.
- `cookies`: A dictionary of cookies to be included in the response.

### `ScheduledResponse` *(!)*
```python
class ScheduledResponse(request: Request, route_function: Callable, error_routes: dict)
```
A class that schedules the generation and handling of an HTTP response based on a request and a route function.

#### Methods

- `run() -> Optional[Response]`
  - Executes the route function and generates an HTTP response.
  - **Returns:** A `Response` object or `None` if an error occurs.

### `FilePath`
```python
class FilePath(path: str)
```
A class that represents a file to be sent as a response.

#### Methods

- `read(read_range: Optional[tuple[int, int]] = None, twice: bool = False) -> bytes`
  - Reads and returns the content of the file, or a specific range of bytes.
  - **Parameters:**
    - `read_range`: A tuple specifying the byte range to read (start, end).
    - `twice`: A boolean indicating whether the file should be read again.

#### Attributes

- `path`: The path to the file.
- `read_start`: The starting byte position for reading.
- `read_end`: The ending byte position for reading.

#### Example
```python
file_response = FilePath("/path/to/file.txt")
```

### `ResponseCookie`
```python
class ResponseCookie(value: str, max_age: int, domain: str, http_only: bool, secure: bool, path: str, same_site

: str)
```
A class that represents a cookie to be included in an HTTP response.

#### Attributes

- `value`: The value of the cookie.
- `max_age`: The maximum age of the cookie, in seconds.
- `domain`: The domain for which the cookie is valid.
- `http_only`: A boolean indicating whether the cookie is HTTP-only.
- `secure`: A boolean indicating whether the cookie is secure.
- `path`: The path for which the cookie is valid.
- `same_site`: The SameSite attribute of the cookie.

## Functions

### `get_insensitive_header` *(!)*
```python
def get_insensitive_header(headers: dict, header_name: str) -> Optional[str]
```
Fetches a header value from a dictionary, case-insensitively.

#### Parameters
- `headers`: A dictionary of headers.
- `header_name`: The name of the header to fetch.

#### Returns
- The value of the header if found, otherwise `None`.

#### Example
```python
headers = {"Content-Type": "application/json", "User-Agent": "my-app"}
content_type = get_insensitive_header(headers, "content-type")
print(content_type)  # Output: "application/json"
```

### `get_description`
```python
def get_description(code: int) -> str
```
Fetches the description of an HTTP status code.

#### Parameters
- `code`: The HTTP status code.

#### Returns
- A string description of the status code.

#### Example
```python
description = get_description(404)
print(description)  # Output: "Not Found"
```
