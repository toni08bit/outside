def get_insensitive_header(headers,header_name):
    for current_name in headers.keys():
        if (current_name.lower() == header_name.lower()):
            return headers[header_name]
    return None
