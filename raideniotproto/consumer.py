import sys, os, time, atexit from signal import SIGTERM
import time
#import RPIO as GPIO # drop-in-replacement!

import gevent.wsgi
import gevent.queue

import gevent.wsgi
import gevent.queue

from tinyrpc.dispatch import public
from tinyrpc.server import RPCServer
from tinyrpc.dispatch import RPCDispatcher
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.transports.wsgi import WsgiServerTransport
from tinyrpc.server.gevent import RPCServerGreenlets


import gevent
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

from raiden.tests.network.utils import start_geth_node
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
        self.dispatcher.register_instance(self.app, 'consumer.')
        self.rpc_server = RPCServerGreenlets(
            self.transport,
            JSONRPCProtocol(),
            self.dispatcher
            )

    def start(self):
        gevent.spawn(self.wsgi_server.serve_forever)
        self.rpc_server.serve_forever()



class PlotApplication(WebSocketApplication):
    def __init__(self, app=None):
        super(PlotApplication, self).__init__()
        self.app = app

    def on_open(self):
        print 'ws opened'
        time = 0
        while True:
            self.ws.send("0 %s %s\n" % (time, self.app.))
            time++
            gevent.sleep(0.1)

    def on_close(self, reason):
        print "Connection Closed!!!", reason


class PowerConsumerBase(object):
    """
    Count impulses from electricity meter
    """
    log_fn = '/home/alarm/data/power.log'
    energy_per_impulse = 1/2000. #kW

    def __init__(self, raiden, price, asset_address, vendor_address):
        self.api = raiden.api
        self.consumed_impulses = 1 # overhead that has to be prepaid
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
        # TODO: timeout, or deactivate relay when funding is not accessible/takes too long
        funding = self.api.get_channel_detail(self.asset_address, self.partner_address)
        balance = funding['partner_balance']
        return balance
        # if timeout:
        #     return 0

    @property
    def netted_balance(self):
        return self.credit - self.debit

    def add_impulse(self):
        self.consumed_impulses += 1

    def settle_incremential(self):
        amount = self.price_per_kwh * self.energy_per_impulse
        self.raiden.api.transfer(
            self.asset_address,
            amount,
            self.partner_address,
        )

     # GPIO has fixed callback argument channel

    @public
    def remote_start_geth_node(private_keys, geth_private_key, p2p_base_port,
                    bootstrap_enode):
        base_datadir = os.path.join(os.pwd + 'tmpdir') # XXX check!
        geth_app = start_geth_node(private_keys, geth_private_key, p2p_base_port,
                        bootstrap_enode, base_datadir)
        if geth_app:
            self.geth_port = 4000 # XXX
            self.geth_private_key = geth_private_key
            self.raiden_private_key = private_keys[1] # XXX check
            self.raiden_port = INITIAL_PORT
            self.geth_started = True

        return 'success' # TODO implement properly, maybe return address etc

    @public
    def remote_start_raiden_app(self, registry_address, discovery_address):

        assert self.geth_started
        config = RaidenApp.default_config.copy()
        config['host'] = '0.0.0.0' # XXX NAT-external
        config['port'] = self.raiden_port
        config['privatekey_hex'] = self.raiden_private_key.encode('hex') #XXX encode?

        jsonrpc_client = JSONRPCClient(
            privkey=self.geth_private_key,
            host='127.0.0.1',
            port=self.geth_port,
            print_communication=False,
        )

        blockchain_service = BlockChainService(
            jsonrpc_client,
            registry_address.decode('hex'),
        )
        discovery = ContractDiscovery(jsonrpc_client, discovery_address.decode('hex'))  # FIXME: double encoding

        self.app = RaidenApp(config, blockchain_service, discovery)
        discovery.register(app.raiden.address, 0.0.0.0, self.raiden_port)

        self.app.raiden.register_registry(blockchain_service.default_registry)

        assert app

        return 'success'
        # XXX Discovery ????
        # self.app = App()
        # self.app.raiden = make_raiden_app(privatekey,
        #     eth_rpc_endpoint,
        #     registry_contract_address,
        #     discovery_contract_address=,
        #     listen_address,
        #     external_listen_address,
        #     logging
        # )

    @public
    def set_vendor_details(self, price_per_kwh, vendor_address, asset_address):
        self.price_per_kwh = price_per_kwh
        self.vendor_address = vendor_address
        self.asset_address = asset_address
        return 'success'

    @public # working?
    @property
    def consumer_ready(self):
        return all(
                self.price_per_kwh,
                self.vendor_address,
                self.asset_address,
                isinstance(self.app, RaidenApp),
                self.api,
                self.geth_started
        )

    @public
    def event_callback(self, channel):
        """ Gets registered with GPIO, will get executed on every impulse.
        Requires, that raiden/rpc polling isn't blocking and doesn't take longer than the next impulse

        Maybe implement handling with queue..

        """
        self.add_impulse()
        self.settle_incremential()

    # def wait_and_activate(self):
    #     # exhaustive polling for now
    #     # activates relay if the soll is paid off
    #     while True:
    #         if self.netted_balance >= 0 and not self.relay_active:
    #             self.activate_relay
    #             break
    #         time.sleep(1)

    def setup_event(self, callback=None):
        raise NotImplemented

    def cleanup(self):
        pass

    def run(self):
        assert self.consumer_ready
        # ofh = open(self.log_fn, 'a')
        self.setup_event(callback=self.event_callback)
        # blocks until first transfer is received
        self.wait_and_activate()
        while True:
            try:
                time.sleep(1)
                continue
            except KeyboardInterrupt:
                self.cleanup()
                sys.exit()


class PowerConsumerRaspberry(PowerConsumerBase):
    """
    Sets up the raspberry's GPIOs, registers callback with the impules event
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(17, GPIO.OUT)

    def __init__(self, raiden, initial_price, asset_address, partner_address, granted_overhead=None):
        import RPi.GPIO as GPIO
        super(PowerMeterRaspberry, self)

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


def static_wsgi_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/html")])
    return open("plot_graph.html").readlines()


resource = Resource([
    ('/', static_wsgi_app),
    ('/data', PlotApplication)
])

if __name__ == "__main__":
    # server = WebSocketServer(('', 8000), resource, debug=True)
    # server.serve_forever()
    pm = PowerMeter()
    pm.run()
