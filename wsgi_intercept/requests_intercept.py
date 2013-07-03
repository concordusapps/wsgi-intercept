from __future__ import print_function, unicode_literals, division


def install_opener():
    # httplib patch
    from wsgi_intercept.httplib2_intercept import install
    install()

    # requests' patch
    import wsgi_intercept
    from requests.packages.urllib3 import connectionpool

    connectionpool.old_http = connectionpool.HTTPConnection
    connectionpool.HTTPConnection = wsgi_intercept.WSGI_HTTPConnection

    connectionpool.old_https = connectionpool.HTTPSConnection
    connectionpool.HTTPSConnection = wsgi_intercept.WSGI_HTTPSConnection

    # we need settimeout()
    wsgi_intercept.wsgi_fake_socket.settimeout = lambda self, timeout: None

def uninstall_opener():
    # httplib unpatch
    from wsgi_intercept.httplib2_intercept import uninstall
    uninstall()

    # requests' unpatch
    import wsgi_intercept
    from requests.packages.urllib3 import connectionpool

    connectionpool.HTTPConnection = connectionpool.old_http
    connectionpool.HTTPSConnection = connectionpool.old_https
