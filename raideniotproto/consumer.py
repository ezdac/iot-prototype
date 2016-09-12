import sys, os, time, atexit, math
from signal import SIGTERM
import time
import RPi.GPIO as GPIO
import inspect

import gevent
import gevent.wsgi
import gevent.queue

import gevent.wsgi
import gevent.queue

from tinyrpc.server import RPCServer
from tinyrpc.dispatch import RPCDispatcher, public
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.transports.wsgi import WsgiServerTransport
from tinyrpc.server.gevent import RPCServerGreenlets
from ethereum.utils import decode_hex

import gevent
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

#from raiden.tests.utils.network import start_geth_node
from raiden.app import App as RaidenApp
from raiden.app import INITIAL_PORT
from raiden.network.discovery import ContractDiscovery
from raiden.network.rpc.client import BlockChainService

class JSONRPCServer(object):

    dispatcher = RPCDispatcher()
    transport = WsgiServerTransport(queue_class=gevent.queue.Queue)

    def __init__(self, app, host, port):
        self.app = app
        self.wsgi_server = gevent.wsgi.WSGIServer((host, port), self.transport.handle)

        # call e.g. 'raiden.api.transfer' via JSON RPC
        self.dispatcher.register_instance(self.app)
        self.rpc_server = RPCServerGreenlets(
            self.transport,
            JSONRPCProtocol(),
            self.dispatcher
            )

    def start(self):
        method_names = [k[0] for k in inspect.getmembers(self.app, inspect.ismethod)]
	has_attribute = [k[1] for k in inspect.getmembers(self.app, inspect.ismethod) if '_rpc_public_name' in k[1].__dict__]
	print has_attribute
        registered = []
        for name in method_names:
            try:
                is_registered = self.dispatcher.get_method(name)
            except KeyError:
                is_registered = False
		pass
            finally:
		registered.append((name, is_registered))
        print 'Public methods: ', registered
        gevent.spawn(self.wsgi_server.serve_forever)
        self.rpc_server.serve_forever()



# class PlotApplication(WebSocketApplication):
#     def __init__(self, app=None):
#         super(PlotApplication, self).__init__()
#         self.app = app
#
#     def on_open(self):
#         print 'ws opened'
#         time = 0
#         while True:
#             self.ws.send("0 %s %s\n" % (time, self.app.))
#             time++
#             gevent.sleep(0.1)
#
#     def on_close(self, reason):
#         print "Connection Closed!!!", reason


class PowerConsumerBase(object):
    """
    Count impulses from electricity meter
    """
    log_fn = '/home/alarm/data/power.log'
    energy_per_impulse = 1/2000. #kW

    def __init__(self, raiden, price, asset_address, vendor_address):
        self.raiden = raiden
        self.api = raiden.api
        self.channel = None
        while not self.channel:
            try:
                asset_manager=raiden.get_manager_by_asset_address(decode_hex(asset_address))
                self.channel = asset_manager.get_channel_by_partner_address(decode_hex(vendor_address))
            except Exception as e:
                print e
        self.consumed_impulses = 0 # overhead that has to be prepaid
        self.price_per_kwh = float(price)
        self.asset_address = asset_address
        self.partner_address = vendor_address

    @property
    def electricity_consumed(self):
        return self.consumed_impulses * self.energy_per_impulse

    @property
    def debit(self):
        return self.electricity_consumed * self.price_per_kwh

    @property
    def credit(self):
        return self.channel.balance

    @property
    def netted_balance(self):
        return self.credit - self.debit

    def add_impulse(self):
        self.consumed_impulses += 1

    def settle_incremential(self):
        amount = self.price_per_kwh * self.energy_per_impulse
        transfer = self.raiden.api.transfer_async(
            self.asset_address,
            int(math.ceil(amount)),
            self.partner_address,
        )
        # try:
        #     return transfer.get()
        # except Exception:
        #     pass


     # GPIO has fixed callback argument channel



    @public
    def event_callback(self, channel):
        """ Gets registered with GPIO, will get executed on every impulse.
        Requires, that raiden/rpc polling isn't blocking and doesn't take longer than the next impulse

        Maybe implement handling with queue..

        """
        self.add_impulse()
        self.settle_incremential()

    def setup_event(self, callback=None):
        raise NotImplemented

    def cleanup(self):
        pass

    def initial_deposit(amount):
        self.raiden.api.transfer_async(
            self.asset_address,
            amount,
            self.partner_address,
        )


    def run(self):
        # ofh = open(self.log_fn, 'a')
        self.setup_event(callback=self.event_callback)
        # blocks until first transfer is received
        self.initial_deposit(1)
        # while True:
        #     try:
        #
        #         # FIXME switch to different thread?
        #         gevent.sleep(1)
        #         continue
        #     except KeyboardInterrupt:
        #         self.cleanup()
        #         sys.exit()
        evt = Event()
        gevent.signal(signal.SIGQUIT, evt.set)
        gevent.signal(signal.SIGTERM, evt.set)
        evt.wait()


class PowerConsumerRaspberry(PowerConsumerBase):
    """
    Sets up the raspberry's GPIOs, registers callback with the impules event
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(17, GPIO.OUT)

    def __init__(self, raiden, initial_price, asset_address, partner_address):
        import RPi.GPIO as GPIO
        super(PowerConsumerRaspberry, self).__init__(raiden, initial_price, asset_address, partner_address)

     # GPIO has fixed callback argument channel

    def setup_event(self, callback=None):
        GPIO.add_event_detect(2, GPIO.RISING, callback=callback, bouncetime=100)

    def cleanup(self):
        GPIO.cleanup()

class PowerConsumerDummy(PowerConsumerBase):

    def __init__(self):
        # # wait for rpc call with parameters that set fields, create raiden app and initialise superclass constructor
        # while not isinstance(RaidenApp, self.app):
        #     gevent.sleep(1)
        # self.api = self.raiden.api
        # while not self.asset_address:
        #     gevent.sleep(1)
        # # everything set from super class, don't call super constructor anymore
        # # super(PowerMeterDummy, self).__init__(raiden, self.price, self.asset_address, self.vendor_address):
        # # make accessible via rpc for mock impulse events
        # # self.event_callback = public(self.event_callback) # this shouldnt work like that!
        # assert self.consumer_ready
        # self.run()
        pass

    def setup_event(self, callback=None):
        pass

    @public
    def run(self):
        assert self.consumer_ready
        # ofh = open(self.log_fn, 'a')
        while True:
            try:
                time.sleep(1)
                continue
            # except RelayDeactivated:
            #     self.wait_and_activate()
            #     continue
            except KeyboardInterrupt:
                self.cleanup()
                sys.exit()


# def static_wsgi_app(environ, start_response):
#     start_response("200 OK", [("Content-Type", "text/html")])
#     return open("plot_graph.html").readlines()
#
#
# resource = Resource([
#     ('/', static_wsgi_app),
#     ('/data', PlotApplication)
# ])

if __name__ == "__main__":
    # server = WebSocketServer(('', 8000), resource, debug=True)
    # server.serve_forever()
    pm = PowerMeter()
    pm.run()
