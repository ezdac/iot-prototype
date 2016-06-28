import sys, os, time, atexit
from signal import SIGTERM
import time
import RPi.GPIO as GPIO
#import RPIO as GPIO # drop-in-replacement!
import gevent
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource



#  monkey patch: gevent-websocket to support 'extra' argument
class _Resource(Resource):
    def __init__(self, apps=None, extra=None):
        super(_Resource, self).__init__(apps)
        assert type(extra) is dict or None
        if extra is not None:
            self.extra = extra

    def __call__(self, environ, start_response):
        environ = environ
        is_websocket_call = 'wsgi.websocket' in environ
        current_app = self._app_by_path(environ['PATH_INFO'], is_websocket_call)

        if current_app is None:
            raise Exception("No apps defined")

        if is_websocket_call:
            ws = environ['wsgi.websocket']
            extra = self.extra
            # here the WebSocketApplication objects get constructed
            current_app = current_app(ws, extra)
            current_app.ws = ws  # TODO: needed?
            current_app.handle()
            # Always return something, calling WSGI middleware may rely on it
            return []
        else:
            return current_app(environ, start_response)


class PlotApplication(WebSocketApplication):
    def __init__(self, extra=None):
        super(PlotApplication, self).__init__()
        self.app = extra['app']

    def on_open(self):
        print 'ws opened'
        time = 0
        while True:
            self.ws.send("0 %s %s\n" % (time, self.app.electricity_consumed))
            time += 1
            gevent.sleep(0.1)

    def on_close(self, reason):
        print "Connection Closed!!!", reason


class PowerMeter(object):
    """
    Count impulses from electricity meter
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(17, GPIO.OUT)
    log_fn = '/home/alarm/data/power.log'
    delay = 90/2000. # impulse length is 90ms
    energyPerImpulse = 1/800. #kW
#	pricePerKwh

    def __init__(self):
        self.count = 0
        self.relay_active = False
        self.electricity_consumed = 0

     # GPIO has fixed callback argument channel
    def event_callback(self, channel):
        self.count += 1
        self.electricity_consumed += energyPerImpulse
        print 'count: {}'.format(self.count)
        # ofh = open(self.log_fn, 'a')
        # ofh.write('{}, {}\n'.format(time.time(), GPIO.input(channel)))
        # ofh.flush()
        if self.count >= 10 and self.relay_active:
            self.count = 0
            self.deactivate_relay()
            # FIXME: race condition with next callback ?
            time.sleep(20)
            self.activate_relay()

    def activate_relay(self):
        GPIO.output(17, True)
        self.relay_active = True

    def deactivate_relay(self):
        GPIO.output(17, False)
        self.relay_active = False

    def toggle_relay(self):
        if self.relay_active:
            self.deactivate_relay()
        else:
            self.activate_relay()



    def start(self):
        # ofh = open(self.log_fn, 'a')
        GPIO.add_event_detect(2, GPIO.RISING, callback=self.event_callback, bouncetime=100)
        self.activate_relay()
        while True:
            try:
                gevent.sleep(1)
                continue
            except KeyboardInterrupt: # except exiting
                self.stop()
                #exit greenlet

    def stop(self):
        GPIO.cleanup()


def static_wsgi_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/html")])
    return open("assets/plot_graph.html").readlines()

routes = [
    ('/', static_wsgi_app),
    ('/data', PlotApplication)
]

if __name__ == "__main__":
    pm = PowerMeter()
    data = {'app': pm}
    pm_thread = gevent.spawn(pm.start)
    resource = _Resource(routes, extra=data)
    server = WebSocketServer(('', 8000), resource, debug=True)

    server.start()
    gevent.joinall([pm_thread, server])

    # server.serve_forever()
