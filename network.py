from urllib.parse import urlparse
import socket


def get_host_and_ips(url):
    try:
        host = urlparse(url).hostname or url
        infos = socket.getaddrinfo(host, None)
        ips = sorted(set(info[4][0] for info in infos))
        return host, ", ".join(ips)

    except Exception:
        return "", ""