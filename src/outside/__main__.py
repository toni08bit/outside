import os
import outside

if (__name__ == "__main__"):
    http_server = outside.OutsideHTTP(("0.0.0.0",8000))

    def main_route(request):
        requested_path = os.path.abspath(os.getcwd() + request.url)
        if (not requested_path.startswith(os.getcwd())):
            return 403,"Invalid parent folder."
        if (os.path.isdir(requested_path)):
            if (os.path.exists(requested_path + "/index.html")):
                return outside.protocol_http.Response(
                    status_code = 200,
                    headers = {},
                    content = outside.protocol_http.FilePath(requested_path + "/index.html")
                )
            else:
                return 404,"No index.html file."
        elif (os.path.isfile(requested_path)):
            return outside.protocol_http.Response(
                status_code = 200,
                headers = {},
                content = outside.protocol_http.FilePath(requested_path)
            )
        else:
            return 404,"URL not found or unavailable."
    http_server.set_route("/",main_route)

    http_server.run()
