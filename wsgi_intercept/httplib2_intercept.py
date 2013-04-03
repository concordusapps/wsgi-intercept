
"""intercept HTTP connections that use httplib2

(see wsgi_intercept/__init__.py for examples)

"""
from __future__ import print_function, unicode_literals, division

import httplib2
from . import WSGI_HTTPConnection, debuglevel, wsgi_fake_socket
from httplib2 import (SCHEME_TO_CONNECTION, HTTPConnectionWithTimeout,
        HTTPSConnectionWithTimeout)
import sys

InterceptorMixin = WSGI_HTTPConnection

# might make more sense as a decorator


def connect(self):
    """
    Override the connect() function to intercept calls to certain
    host/ports.
    """
    if debuglevel:
        sys.stderr.write('connect: %s, %s\n' % (self.host, self.port,))

    (app, script_name) = self.get_app(self.host, self.port)
    if app:
        if debuglevel:
            sys.stderr.write('INTERCEPTING call to %s:%s\n' %
                             (self.host, self.port,))
        self.sock = wsgi_fake_socket(app,
                                                    self.host, self.port,
                                                    script_name)
    else:
        self._connect()


class HTTP_WSGIInterceptorWithTimeout(HTTPConnectionWithTimeout,
        InterceptorMixin):
    _connect = httplib2.HTTPConnectionWithTimeout.connect
    connect = connect


class HTTPS_WSGIInterceptorWithTimeout(HTTPSConnectionWithTimeout,
        InterceptorMixin):
    _connect = httplib2.HTTPSConnectionWithTimeout.connect
    connect = connect


def install():
    SCHEME_TO_CONNECTION['http'] = HTTP_WSGIInterceptorWithTimeout
    SCHEME_TO_CONNECTION['https'] = HTTPS_WSGIInterceptorWithTimeout


def uninstall():
    SCHEME_TO_CONNECTION['http'] = HTTPConnectionWithTimeout
    SCHEME_TO_CONNECTION['https'] = HTTPSConnectionWithTimeout
