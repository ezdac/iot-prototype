import sys, os, time, atexit
from signal import SIGTERM
import time
import RPi.GPIO as GPIO
from tinyrpc.transports.http import HttpWebSocketClientTransport
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.client import RPCClient

#import RPIO as GPIO # drop-in-replacement!
import gevent
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

# #  monkey patch: gevent-websocket to support 'extra' argument
# class _Resource(Resource):
#     def __init__(self, apps=None, extra=None):
#         super(_Resource, self).__init__(apps)
#         assert type(extra) is dict or None
#         if extra is not None:
#             self.extra = extra
#
#     def __call__(self, environ, start_response):
#         environ = environ
#         is_websocket_call = 'wsgi.websocket' in environ
#         current_app = self._app_by_path(environ['PATH_INFO'], is_websocket_call)
#
#         if current_app is None:
#             raise Exception("No apps defined")
#
#         if is_websocket_call:
#             ws = environ['wsgi.websocket']
#             extra = self.extra
#             # here the WebSocketApplication objects get constructed
#             current_app = current_app(ws, extra)
#             current_app.ws = ws  # TODO: needed?
#             current_app.handle()
#             # Always return something, calling WSGI middleware may rely on it
#             return []
#         else:
#             return current_app(environ, start_response)


class PlotApplication(WebSocketApplication):
    def __init__(self, ws, extra=None):
        super(PlotApplication, self).__init__(ws)
        self.app = extra['app']

    def on_open(self):
        print 'ws opened'
        time = 0
        while True:
            self.ws.send("0 %s %s\n" % (time, self.app.electricity_consumed))
            time += 1
            gevent.sleep(1)

    def on_close(self, reason):
        print "Connection Closed!!!", reason


class PowerMeter(object):
    """
    Count impulses from electricity meter
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    log_fn = '/home/alarm/data/power.log'
    energyPerImpulse = 1/2000. # in kWh per Impulse
    pricePerKwh = 100 # TODO: get price per kWh per livefeed from somewhere...

    def __init__(self, rpc_client):
        self.count = 0
        self.electricity_consumed = 0
        self.rpc_client = rpc_client

     # GPIO has fixed callback argument channel
    def event_callback(self, channel):
        self.count += 1
        self.electricity_consumed += self.energyPerImpulse
        print 'count: {}'.format(self.count)
        # XXX: amount determination in buyer script??
        self.rpc_client.call(transfer_partner, amount=100)
        # TODO: check for sufficient balance first or catch error
        # TODO: proper success confirmation required?

    def start(self):
        # ofh = open(self.log_fn, 'a')
        GPIO.add_event_detect(2, GPIO.RISING, callback=self.event_callback, bouncetime=100)
        while True:
            try:
                gevent.sleep(1)
                continue
            except KeyboardInterrupt: # except exiting
                self.stop()
                #exit greenlet

    def stop(self):
        GPIO.cleanup()


# def static_wsgi_app(environ, start_response):
#     start_response("200 OK", [("Content-Type", "text/html")])
#     return open("assets/plot_graph.html").readlines()
#
# routes = [
#     ('/', static_wsgi_app),
#     ('/data', PlotApplication)
# ]

if __name__ == "__main__":
    while not rpc_client:
        try:
            rpc_client = RPCClient(
                HttpWebSocketClientTransport('192.168.0.118:8000/buyer'),
                JSONRPCProtocol()
                )
        # TODO: check for reasonable exceptions
        except Exception, e:
            print e
            continue
    pm = PowerMeter(rpc_client)
    data = {'app': pm}
    pm_thread = gevent.spawn(pm.start)
    # resource = _Resource(routes, extra=data)
    # server = WebSocketServer(('', 8000), resource, debug=True)
    try:
        server.serve_forever()
    finally:
        pm.rpc_client.stop()
        GPIO.cleanup()
