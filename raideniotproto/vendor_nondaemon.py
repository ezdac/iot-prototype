import sys, os, time, atexit
from signal import SIGTERM
import time
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.transports.http import HttpPostClientTransport
from tinyrpc import RPCClient
from tinyrpc.client import RPCProxy
from ethereum.utils import decode_hex
import RPi.GPIO as GPIO

import gevent
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

# from raiden.raiden-service import
#from raiden.tests.conftest import deployed_network

class ConsumerProxy(object):

    def __init__(self, host, port, protocol=JSONRPCProtocol, prefix=''):
        """
        a ConsumerProxy instance can call registered methods like that:
        ConsumerProxyInstance,rpc_proxy.<method>(*args)
        """

        rpc_client = RPCClient(
            protocol(),
            HttpPostClientTransport('http://{}:{}'.format(host, port))
        )
        self.rpc_proxy = RPCProxy(rpc_client, prefix=prefix, one_way=False)

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
#             time += 1
#             gevent.sleep(0.1)
#
#     def on_close(self, reason):
#         print "Connection Closed!!!", reason


class PowerMeterBase(object):
    """
    Count impulses from electricity meter
    """
    # GPIO.setmode(GPIO.BCM)
    # GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # GPIO.setup(17, GPIO.OUT)
    # log_fn = '/home/alarm/data/power.log'
    energy_per_impulse = 1/2000. #kwH

    def __init__(self, raiden,initial_price, asset_address, partner_address, ui_server):
        self.raiden = raiden
        self.api = raiden.api
        self.channel = None
        # give channel in constructor FIXME
        while not self.channel:
            try:
                asset_manager=raiden.get_manager_by_asset_address(decode_hex(asset_address))
                self.channel = asset_manager.get_channel_by_partner_address(decode_hex(vendor_address))
            except Exception as e:
                # pass silently FIXME
        self.relay_active = False
        self.consumed_impulses = 1 # overhead that has to be prepaid
        self.price_per_kwh = float(initial_price)
        self.asset_address = asset_address
        self.partner_addres = partner_address
        if ui_server:
            self.ui_server = ui_server
        # self.grant = granted_overhead # TODO: implement merciful overhead

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
        if self.ui_server:
            requests.post(self.ui_server + '/power_tick')
        self.consumed_impulses += 1

     # GPIO has fixed callback argument channel

    def event_callback(self, channel):
        """ Gets registered with GPIO, will get executed on every impulse.
        Requires, that raiden/rpc polling isn't blocking and doesn't take longer than the next impulse

        Maybe implement handling with queue..

        """
        print 'cb initialised! {} - count: {} credit - {} debit'.format(self.consumed_impulses, self.credit, self.debit)
        # ofh = open(self.log_fn, 'a')
        # ofh.write('{}, {}\n'.format(time.time(), GPIO.input(channel)))
        # ofh.flush()
        # check if the updated balance is sufficient and the last cycle was paid:
        if self.netted_balance < 0 and self.relay_active:
            self.deactivate_relay()
            # will stay in wait-loop until balance changes/is sufficient
            self.wait_and_activate()
        # increment counter for next started cycle
        self.add_impulse()


    def wait_and_activate(self):
        # exhaustive polling for now
        # activates relay if the debit is paid off
        while True:
            print 'waiting! {} - count: {} credit - {} debit'.format(self.consumed_impulses, self.credit, self.debit)
            if self.netted_balance >= 0 and not self.relay_active:
                print 'netted balance >=0'
                self.activate_relay()
                break
            time.sleep(1)

    def activate_relay(self):
        self.relay_active = True

    def deactivate_relay(self):
        self.relay_active = False

    def setup_event(self, callback=None):
        raise NotImplemented

    def cleanup(self):
        pass

    def run(self):
        # ofh = open(self.log_fn, 'a')
        self.setup_event(callback=self.event_callback)
        # blocks until first transfer is received
        self.wait_and_activate()
        while True:
            try:
                gevent.sleep(1)
                continue
            except KeyboardInterrupt:
                self.cleanup()
                sys.exit()


class PowerMeterRaspberry(PowerMeterBase):
    """
    Sets up the raspberry's GPIOs, registers callback with the impules event
    """
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(17, GPIO.OUT)

    def __init__(self, raiden, initial_price, asset_address, partner_address):
        import RPi.GPIO as GPIO
        super(PowerMeterRaspberry, self).__init__(raiden, initial_price,
              asset_address, partner_address)

     # GPIO has fixed callback argument channel

    def activate_relay(self):
        GPIO.output(17, True)
        self.relay_active = True

    def deactivate_relay(self):
        GPIO.output(17, False)
        self.relay_active = False

    def setup_event(self, callback=None):
        GPIO.add_event_detect(2, GPIO.RISING, callback=callback, bouncetime=100)

    def cleanup(self):
        GPIO.cleanup()

class PowerMeterDummy(PowerMeterBase):

    def __init__(self, raiden, consumer_proxy, initial_price, asset_address,
                 partner_address, granted_overhead=None):
        super(PowerMeterDummy, self).__init__(self, raiden, initial_price,
              asset_address, partner_address, granted_overhead=None)

        self.consumer_proxy = consumer_proxy

    def setup_event(self, callback=None):
        pass

    def mock_impulse_trigger(self, interval=4):
        # first mock impulse on vendor, checking if last cycle was paid, increment cycle counter
        self.event_callback()
        # trigger impulse callback on consumer via rpc, initialising transfer to prepay current cycle
        self.consumer_proxy.event_callback()
        # sleep to mock timespan of the cycle's electricity-consumption
        time.sleep(float(interval))

    def run(self):
        # ofh = open(self.log_fn, 'a')
        # trigger initial deposit on consumer
        self.consumer_proxy.event_callback()
        # wait until transfer received
        self.wait_and_activate()
        while True:
            try:
                # go into impulse mock loop:
                # will either deliver current when paid properly,
                # or deactivate the relay and wait in the wait_and_activate-loop
                # until paid properly
                self.mock_impulse_trigger()
                continue
            except KeyboardInterrupt:
                # stop with ctrl+c
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

# if __name__ == "__main__":
#     # server = WebSocketServer(('', 8000), resource, debug=True)
#     # server.serve_forever()
#     app1, app2 = deploy_default_config()
#
#     pm = PowerMeterDummy()
#     pm.run()
