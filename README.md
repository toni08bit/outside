
# outside
## What's this?
An easy-to-use python web framework. Inspired by Flask.

## Install
This project is available on pip via the **outside-framework** name.

    pip install outside-framework

## Demo
The software is actively being used at [billplayz.de](https://billplayz.de/)

## Quickstart
This simple script responds with "Hello World!" to every request.

    import outside
    http_server = outside.OutsideHTTP(("127.0.0.1",80))
    
    def test(request):
        return outside.protocol_http.Response(
            request = request,
            status_code = 200,
            headers = {},
            content = "Hello World!"
        )
    http_server.set_route("/",test)
    
    if (__name__ == "__main__"):
        http_server.run()

## Reference
### outside.OutsideHTTP.config
**host**: (address: *string* ["0.0.0.0"], port: *int* [80])
**backlog_length**: length: *int* [25]
**process_timeout**: seconds: *int* [60]
**termination_timeout**: seconds: *int* [5]
**recv_size**: bytes: *int* [1024]
**send_size**: bytes: *int* [1024]
**accept_timeout**: seconds: *int* [0.02]
**ssl_enabled**: enabled: *bool* [False]
**ssl_keyfile**: path: *string* [""]
**ssl_certfile**: path: *string* [""]
**max_body_size_mb**: megabytes: *int* [250]
**keep_alive**: enabled: *bool* [True]
**post_callback**: callback: *function* or *None* [None]
**pre_send**: callback: *function* or *None* [None]

### outside.OutsideHTTP.set_route()

    Syntax: outside.OutsideHTTP.set_route(startswith: string,callback: function)
    Example: http_server.set_route("/testroute/",my_function)

### outside.OutsideHTTP.remove_route()

    Syntax: outside.OutsideHTTP.remove_route(startswith: string)
    Example: http_server.remove_route("/testroute/")

### outside.OutsideHTTP.set_errorhandler()

    Syntax: outside.OutsideHTTP.set_errorhandler(errorcode: int, handler: function)
    Example: http_server.set_errorhandler(404,my_function)

### outside.OutsideHTTP.remove_errorhandler()

    Syntax: outside.OutsideHTTP.remove_errorhandler(errorcode: int)
    Example: http_server.remove_errorhandler(404)

### outside.OutsideHTTP.terminate()

    Syntax: outside.OutsideHTTP.terminate()
    Example: http_server.terminate()

### outside.OutsideHTTP.run()

    Syntax: outside.OutsideHTTP.run()
    Example: http_server.run()

