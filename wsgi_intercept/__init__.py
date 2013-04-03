
"""installs a WSGI application in place of a real URI for testing.

Introduction
============

Testing a WSGI application normally involves starting a server at a
local host and port, then pointing your test code to that address.
Instead, this library lets you intercept calls to any specific host/port
combination and redirect them into a `WSGI application`_ importable by
your test program. Thus, you can avoid spawning multiple processes or
threads to test your Web app.

How Does It Work?
=================

``wsgi_intercept`` works by replacing ``httplib.HTTPConnection`` with a
subclass, ``wsgi_intercept.WSGI_HTTPConnection``. This class then
redirects specific server/port combinations into a WSGI application by
emulating a socket. If no intercept is registered for the host and port
requested, those requests are passed on to the standard handler.

The functions ``add_wsgi_intercept(host, port, app_create_fn,
script_name='')`` and ``remove_wsgi_intercept(host,port)`` specify
which URLs should be redirect into what applications. Note especially
that ``app_create_fn`` is a *function object* returning a WSGI
application; ``script_name`` becomes ``SCRIPT_NAME`` in the WSGI app's
environment, if set.

Install
=======

::

    pip install -U wsgi_intercept

Packages Intercepted
====================

Unfortunately each of the Web testing frameworks uses its own specific
mechanism for making HTTP call-outs, so individual implementations are
needed. Below are the packages supported and how to create an intercept.

urllib.request
-------

urllib.request is a standard Python module, and ``urllib.request.urlopen``
is a common way to open URLs.

The following code will install the WSGI intercept stuff as a default
urllib.request handler: ::

   >>> from wsgi_intercept.urllib_intercept import install_opener
   >>> install_opener() #doctest: +ELLIPSIS
   <urllib.request.OpenerDirector instance at ...>
   >>> import wsgi_intercept
   >>> from wsgi_intercept.test_wsgi_app import create_fn
   >>> wsgi_intercept.add_wsgi_intercept('some_host', 80, create_fn)
   >>> import urllib.request
   >>> urllib.request.urlopen('http://some_host:80/').read()
   'WSGI intercept successful!\\n'

httplib2
--------

httplib2_ is a 3rd party extension of the built-in ``httplib``.  To intercept
requests, it is similar to urllib::

    >>> from wsgi_intercept.httplib2_intercept import install
    >>> install()
    >>> import wsgi_intercept
    >>> from wsgi_intercept.test_wsgi_app import create_fn
    >>> wsgi_intercept.add_wsgi_intercept('some_host', 80, create_fn)
    >>> import httplib2
    >>> resp, content = httplib2.Http().request('http://some_host:80/', 'GET')
    >>> content
    'WSGI intercept successful!\\n'

(Contributed by `David "Whit" Morris`_.)

.. _httplib2: http://code.google.com/p/httplib2/
.. _David "Whit" Morris: http://public.xdi.org/=whit

History
=======

Pursuant to Ian Bicking's `"best Web testing framework"`_ post, Titus
Brown put together an `in-process HTTP-to-WSGI interception mechanism`_
for his own Web testing system, twill_. Because the mechanism is pretty
generic -- it works at the httplib level -- Titus decided to try adding
it into all of the *other* Python Web testing frameworks.

This is the result.

.. _twill: http://www.idyll.org/~t/www-tools/twill.html
.. _"best Web testing framework": http://blog.ianbicking.org/best-of-the-web-app-test-frameworks.html
.. _in-process HTTP-to-WSGI interception mechanism: http://www.advogato.org/person/titus/diary.html?start=119
.. _WSGI application: http://www.python.org/peps/pep-3333.html

Project Home
============

This project lives on `GitHub`_. Please submit all bugs, patches,
failing tests, et cetera using the Issue Tracker.

.. _GitHub: http://github.com/cdent/python3-wsgi-intercept

"""
from __future__ import print_function, unicode_literals, division
__version__ = '0.0.1'

import sys
import six
from six.moves import http_client
HTTPConnection = http_client.HTTPConnection
from io import BytesIO
import traceback

debuglevel = 0
# 1 basic
# 2 verbose

####

#
# Specify which hosts/ports to target for interception to a given WSGI app.
#
# For simplicity's sake, intercept ENTIRE host/port combinations;
# intercepting only specific URL subtrees gets complicated, because we don't
# have that information in the HTTPConnection.connect() function that does the
# redirection.
#
# format: key=(host, port), value=(create_app, top_url)
#
# (top_url becomes the SCRIPT_NAME)

_wsgi_intercept = {}


def add_wsgi_intercept(host, port, app_create_fn, script_name=''):
    """
    Add a WSGI intercept call for host:port, using the app returned
    by app_create_fn with a SCRIPT_NAME of 'script_name' (default '').
    """
    _wsgi_intercept[(host, port)] = (app_create_fn, script_name)


def remove_wsgi_intercept(*args):
    """
    Remove the WSGI intercept call for (host, port).  If no arguments are
    given, removes all intercepts
    """
    global _wsgi_intercept
    if len(args) == 0:
        _wsgi_intercept = {}
    else:
        key = (args[0], args[1])
        if key in _wsgi_intercept:
            del _wsgi_intercept[key]


#
# make_environ: behave like a Web server.  Take in 'input', and behave
# as if you're bound to 'host' and 'port'; build an environment dict
# for the WSGI app.
#
# This is where the magic happens, folks.
#
def make_environ(inp, host, port, script_name):
    """
    Take 'inp' as if it were HTTP-speak being received on host:port,
    and parse it into a WSGI-ok environment dictionary.  Return the
    dictionary.

    Set 'SCRIPT_NAME' from the 'script_name' input, and, if present,
    remove it from the beginning of the PATH_INFO variable.
    """
    #
    # parse the input up to the first blank line (or its end).
    #

    environ = {}

    method_line = inp.readline()
    method_line = method_line.decode('ISO-8859-1')

    content_type = None
    content_length = None
    cookies = []

    for line in inp:
        if not line.strip():
            break

        k, v = line.strip().split(b':', 1)
        v = v.lstrip()
        v = v.decode('ISO-8859-1')

        #
        # take care of special headers, and for the rest, put them
        # into the environ with HTTP_ in front.
        #

        if k.lower() == b'content-type':
            content_type = v
        elif k.lower() == b'content-length':
            content_length = v
        elif k.lower() == b'cookie' or k.lower() == b'cookie2':
            cookies.append(v)
        else:
            h = k.upper()
            h = h.replace(b'-', b'_')
            environ['HTTP_' + h.decode('ISO-8859-1')] = v

        if debuglevel >= 2:
            print('HEADER:', k, v)

    #
    # decode the method line
    #

    if debuglevel >= 2:
        print('METHOD LINE:', method_line)

    method, url, protocol = method_line.split(' ')

    # clean the script_name off of the url, if it's there.
    if not url.startswith(script_name):
        script_name = ''                # @CTB what to do -- bad URL.  scrap?
    else:
        url = url[len(script_name):]

    url = url.split('?', 1)
    path_info = url[0]
    query_string = ""
    if len(url) == 2:
        query_string = url[1]

    if debuglevel:
        print("method: %s; script_name: %s; path_info: %s; query_string: %s" %
                (method, script_name, path_info, query_string))

    r = inp.read()
    inp = BytesIO(r)

    #
    # fill out our dictionary.
    #

    environ.update({
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": inp,  # to read for POSTs
        "wsgi.errors": BytesIO(),
        "wsgi.multithread": 0,
        "wsgi.multiprocess": 0,
        "wsgi.run_once": 0,

        "PATH_INFO": path_info,
        "REMOTE_ADDR": '127.0.0.1',
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": script_name,
        "SERVER_NAME": host,
        "SERVER_PORT": port,
        "SERVER_PROTOCOL": protocol,
    })

    #
    # query_string, content_type & length are optional.
    #

    if query_string:
        environ['QUERY_STRING'] = query_string

    if content_type:
        environ['CONTENT_TYPE'] = content_type
        if debuglevel >= 2:
            print('CONTENT-TYPE:', content_type)
    if content_length:
        environ['CONTENT_LENGTH'] = content_length
        if debuglevel >= 2:
            print('CONTENT-LENGTH:', content_length)

    #
    # handle cookies.
    #
    if cookies:
        environ['HTTP_COOKIE'] = "; ".join(cookies)

    if debuglevel:
        print('WSGI environ dictionary:', environ)

    return environ


#
# fake socket for WSGI intercept stuff.
#
class wsgi_fake_socket:
    """
    Handle HTTP traffic and stuff into a WSGI application object instead.

    Note that this class assumes:

     1. 'makefile' is called (by the response class) only after all of the
        data has been sent to the socket by the request class;
     2. non-persistent (i.e. non-HTTP/1.1) connections.
    """
    def __init__(self, app, host, port, script_name):
        self.app = app                  # WSGI app object
        self.host = host
        self.port = port
        self.script_name = script_name  # SCRIPT_NAME (app mount point)

        self.inp = BytesIO()           # stuff written into this "socket"
        self.write_results = []          # results from the 'write_fn'
        self.results = None             # results from running the app
        self.output = BytesIO()        # all output from the app, incl headers

    def makefile(self, *args, **kwargs):
        """
        'makefile' is called by the HTTPResponse class once all of the
        data has been written.  So, in this interceptor class, we need to:

          1. build a start_response function that grabs all the headers
             returned by the WSGI app;
          2. create a wsgi.input file object 'inp', containing all of the
             traffic;
          3. build an environment dict out of the traffic in inp;
          4. run the WSGI app & grab the result object;
          5. concatenate & return the result(s) read from the result object.

        @CTB: 'start_response' should return a function that writes
        directly to self.result, too.
        """

        # dynamically construct the start_response function for no good reason.

        def start_response(status, headers, exc_info=None):
            # construct the HTTP request.
            self.output.write(b"HTTP/1.0 " + status.encode('utf-8') + b"\n")

            for k, v in headers:
                try:
                    k = k.encode('utf-8')
                except AttributeError:
                    pass
                try:
                    v = v.encode('utf-8')
                except AttributeError:
                    pass
                self.output.write(k + b':' + v + b"\n")
            self.output.write(b'\n')

            def write_fn(s):
                self.write_results.append(s)
            return write_fn

        # construct the wsgi.input file from everything that's been
        # written to this "socket".
        inp = BytesIO(self.inp.getvalue())

        # build the environ dictionary.
        environ = make_environ(inp, self.host, self.port, self.script_name)

        # run the application.
        app_result = self.app(environ, start_response)
        self.result = iter(app_result)

        ###

        # read all of the results.  the trick here is to get the *first*
        # bit of data from the app via the generator, *then* grab & return
        # the data passed back from the 'write' function, and then return
        # the generator data.  this is because the 'write' fn doesn't
        # necessarily get called until the first result is requested from
        # the app function.

        try:
            generator_data = None
            try:
                generator_data = next(self.result)

            finally:
                for data in self.write_results:
                    self.output.write(data)

            if generator_data:
                try:
                    self.output.write(generator_data)
                except TypeError as exc:
                    raise TypeError('bytes required in response: %s' % exc)

                while 1:
                    data = next(self.result)
                    self.output.write(data)

        except StopIteration:
            pass

        if hasattr(app_result, 'close'):
            app_result.close()

        if debuglevel >= 2:
            print("***", self.output.getvalue(), "***")

        # return the concatenated results.
        return BytesIO(self.output.getvalue())

    def sendall(self, text):
        """
        Save all the traffic to self.inp.
        """
        if debuglevel >= 2:
            print(">>>", text, ">>>")

        try:
            self.inp.write(text)
        except TypeError:
            self.inp.write(six.binary_type(text.decode('utf-8')))

    def close(self):
        "Do nothing, for now."
        pass


#
# WSGI_HTTPConnection
#
class WSGI_HTTPConnection(HTTPConnection):
    """
    Intercept all traffic to certain hosts & redirect into a WSGI
    application object.
    """
    def get_app(self, host, port):
        """
        Return the app object for the given (host, port).
        """
        key = (host, int(port))

        app, script_name = None, None

        if key in _wsgi_intercept:
            (app_fn, script_name) = _wsgi_intercept[key]
            app = app_fn()

        return app, script_name

    def connect(self):
        """
        Override the connect() function to intercept calls to certain
        host/ports.

        If no app at host/port has been registered for interception then
        a normal HTTPConnection is made.
        """
        if debuglevel:
            sys.stderr.write('connect: %s, %s\n' % (self.host, self.port,))

        try:
            (app, script_name) = self.get_app(self.host, self.port)
            if app:
                if debuglevel:
                    sys.stderr.write('INTERCEPTING call to %s:%s\n' %
                                     (self.host, self.port,))
                self.sock = wsgi_fake_socket(app, self.host, self.port,
                                             script_name)
            else:
                HTTPConnection.connect(self)

        except Exception as e:
            if debuglevel:              # intercept & print out tracebacks
                traceback.print_exc()
            raise

#
# WSGI_HTTPSConnection
#

try:
    from http.client import HTTPSConnection
except ImportError:
    pass
else:
    class WSGI_HTTPSConnection(HTTPSConnection, WSGI_HTTPConnection):
        """
        Intercept all traffic to certain hosts & redirect into a WSGI
        application object.
        """
        def get_app(self, host, port):
            """
            Return the app object for the given (host, port).
            """
            key = (host, int(port))

            app, script_name = None, None

            if key in _wsgi_intercept:
                (app_fn, script_name) = _wsgi_intercept[key]
                app = app_fn()

            return app, script_name

        def connect(self):
            """
            Override the connect() function to intercept calls to certain
            host/ports.

            If no app at host/port has been registered for interception then
            a normal HTTPSConnection is made.
            """
            if debuglevel:
                sys.stderr.write('connect: %s, %s\n' % (self.host, self.port,))

            try:
                (app, script_name) = self.get_app(self.host, self.port)
                if app:
                    if debuglevel:
                        sys.stderr.write('INTERCEPTING call to %s:%s\n' %
                                         (self.host, self.port,))
                    self.sock = wsgi_fake_socket(app, self.host, self.port,
                                                 script_name)
                else:
                    HTTPSConnection.connect(self)

            except Exception as e:
                if debuglevel:              # intercept & print out tracebacks
                    traceback.print_exc()
                raise
