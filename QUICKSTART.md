# `outside` Module Quickstart Guide

This quickstart guide will help you get started with the `outside` module, providing step-by-step instructions to set up a basic HTTP server and WebSocket server. It covers the installation, configuration, and basic usage of the module. This documentation was partly AI-generated as this project wasn't meant for other people to use.

## 1. Installation

Requirement: python>=3.8

The module is available on PyPi under the name `outside-framework` (**NOT "outside"**).
You can retrieve the PyPi package using the *pip* command:
   ```bash
   pip install outside-framework
   ```

DISCLAIMER: The project was built for Linux Servers, expect bugs on other systems.

## 2. Creating a Simple HTTP Server

This section will guide you through creating a basic HTTP server that responds with a simple message.

### 2.1. Setting Up the Server

1. **Import Required Classes**
   ```python
   from outside import OutsideHTTP, Response
   ```

2. **Create the Server Instance**
   ```python
   server = OutsideHTTP(("127.0.0.1", 8080))  # Host on localhost, port 8080
   ```

3. **Define a Route Handler**
   ```python
   def hello_world(request):
       return Response(
           status_code = 200,
           headers = {"Content-Type": "text/plain"},
           content = "Hello, World!"
       )
   ```

4. **Add the Route to the Server**
   ```python
   server.set_route("/hello", hello_world)
   ```

5. **Start the Server**
   ```python
   server.run()
   ```

6. **Access the Server**
   Open your browser and navigate to `http://127.0.0.1:8080/hello` to see the "Hello, World!" message.

### 2.2. Handling Different HTTP Methods

You can handle different HTTP methods such as `POST`, `PUT`, `DELETE`, etc., by checking the `request.method` attribute in your route handler.

```python
def data_handler(request):
    if request.method == 'POST':
        return Response(
            status_code=201,
            headers={"Content-Type": "application/json"},
            content='{"message": "Data received successfully!"}'
        )
    elif request.method == 'GET':
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            content='{"message": "This is a GET request!"}'
        )
    else:
        return Response(
            status_code=405,
            headers={},
            content="Method Not Allowed"
        )

server.set_route("/data", data_handler)
```

### 2.3. Adding Custom Error Handlers

You can add custom error handlers for specific HTTP status codes.

```python
def not_found_handler(request, message=None):
    return Response(
        status_code = 404,
        headers = {},
        content = "The page you are looking for was not found."
    )

server.set_errorhandler(404, not_found_handler)
```

## 3. Creating a WebSocket Server

The `outside` module also supports WebSocket connections, making it easy to build real-time applications.

### 3.1. Setting Up a WebSocket Server

1. **Import Required Classes**
   ```python
   from outside import OutsideHTTP, WebSocket
   ```

2. **Create the WebSocket Server Instance**
   ```python
   websocket_server = OutsideHTTP(("127.0.0.1", 8081))  # Host on localhost, port 8081
   ```

3. **Define the WebSocket Handler**
   ```python
   def websocket_handler(connection):
       while True:
           message = connection.recv()
           connection.send(message)  # Echo back the message
   ```

4. **Set Up the WebSocket Route**
   ```python
   ws = WebSocket()
   ws.on_connection(websocket_handler)
   websocket_server.set_route("/ws", ws)
   ```

5. **Start the WebSocket Server**
   ```python
   websocket_server.run()
   ```

6. **Test the WebSocket Server**
   Use a WebSocket client (like `wscat` or an online tool) to connect to `ws://127.0.0.1:8081/ws` and send messages.

### 3.2. Handling WebSocket Events

You can define handlers for WebSocket connection events:

```python
def on_exit():
    print("WebSocket connection closed.")

ws.on_exit(on_exit)
```

## 4. Redirecting Traffic with `OutsideHTTP_Redirect`

If you need to redirect traffic to another URL, use the `OutsideHTTP_Redirect` class.

### 4.1. Setting Up the Redirect Server

1. **Import Required Class**
   ```python
   from outside import OutsideHTTP_Redirect
   ```

2. **Create the Redirect Server Instance**
   ```python
   redirect_server = OutsideHTTP_Redirect(("127.0.0.1", 80), "https://www.example.com")
   ```

3. **Start the Redirect Server**
   ```python
   redirect_server.run()
   ```

4. **Test the Redirect**
   Navigate to `http://127.0.0.1` in your browser, and you should be redirected to `https://www.example.com`.

## 5. SSL Configuration

To enable SSL, you need to set the `ssl_enabled`, `ssl_keyfile`, and `ssl_certfile` attributes in the server configuration.

### 5.1. Enabling SSL for the Server

DISCLAIMER: It is usually a challenge to obtain trusted SSL certificates for only an IP address. This is meant for use in combination with a domain.

1. **Configure SSL Settings**
   ```python
   server.config["ssl_enabled"] = True
   server.config["ssl_keyfile"] = "/path/to/privkey.pem"
   server.config["ssl_certfile"] = "/path/to/cert.pem"
   ```

2. **Start the Server**
   ```python
   server.run()  # Now the server will run with SSL enabled
   ```

3. **Access the Secure Server**
   Open your browser and navigate to `https://127.0.0.1:8080/hello`.

## 6. Handling File Uploads

The `outside` module supports handling file uploads with custom logic.

### 6.1. Handling File Uploads

1. **Define a File Upload Handler**
   ```python
   def file_upload_handler(request):
       if request.method == 'POST':
           uploaded_file = request.content  # Get the uploaded file content
           with open("uploaded_file.dat", "ab") as f:
               f.write(uploaded_file)
           return Response(
               status_code = 201,
               headers = {},
               content = "File uploaded successfully!"
           )
       else:
           return Response(
               status_code = 405,
               headers = {},
               content = "Method Not Allowed"
           )
   ```

2. **Add the Route**
   ```python
   server.set_route("/upload", file_upload_handler)
   ```

3. **Test the File Upload**
   Use a tool like `curl` to upload a file:
   ```bash
   curl -X POST -F "file=@/path/to/your/file" http://127.0.0.1:8080/upload
   ```

## 7. Customizing Server Configuration

You can customize various aspects of the server, such as the maximum number of concurrent workers, request timeouts, and more.

### 7.1. Modifying Configuration

```python
server.config["max_workers"] = 200  # Increase the number of concurrent workers
server.config["process_timeout"] = 120  # Set request timeout to 120 seconds
```

## 8. Summary

With this guide, you should be able to quickly set up and configure an HTTP or WebSocket server using the `outside` module. Explore the various classes and methods available to extend and customize the server to meet your specific needs.

For more detailed information, refer to the [full documentation](README.md).
