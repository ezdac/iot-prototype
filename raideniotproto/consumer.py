
from gevent import monkey
monkey.patch_all()

import sys, os, time, atexit, math
from signal import SIGTERM
import time
import RPi.GPIO as GPIO
import inspect
import requests

import gevent
import gevent.wsgi
import gevent.queue

from tinyrpc.server import RPCServer
from tinyrpc.dispatch import RPCDispatcher, public
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.transports.wsgi import WsgiServerTransport
from tinyrpc.server.gevent import RPCServerGreenlets
from ethereum.utils import decode_hex

from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

#from raiden.tests.utils.network import start_geth_node
from raiden.app import App as RaidenApp
from raiden.app import INITIAL_PORT
from raiden.network.discovery import ContractDiscovery
from raiden.network.rpc.client import BlockChainService


class PowerConsumerBase(object):
    """
    Count impulses from electricity meter
    """
    energy_per_impulse = 1/2000. #kW

    def __init__(self, raiden, price, asset_address, vendor_address, ui_server=None):
        self.raiden = raiden
        self.api = raiden.api
        self.channel = None
        while not self.channel:
            try:
                asset_manager=raiden.get_manager_by_asset_address(decode_hex(asset_address))
                self.channel = asset_manager.get_channel_by_partner_address(decode_hex(vendor_address))
            except Exception as e:
                raise e
        self.consumed_impulses = 0 # overhead that has to be prepaid
        self.price_per_kwh = float(price)
        self.asset_address = asset_address
        self.partner_address = vendor_address
        if ui_server:
            self.ui_server = ui_server

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
        amount = int(math.ceil(amount))
        self.transfer(amount)

    def event_callback(self):
        """ Gets registered with GPIO, will get executed on every impulse.
        Requires, that raiden/rpc polling isn't blocking and doesn't take longer than the next impulse

        Maybe implement handling with queue..

        """
        print self.consumed_impulses
        print self.channel.balance
        self.add_impulse()
        self.settle_incremential()

    def cleanup(self):
        pass

    def transfer(self,amount):
        # amount should be int
        try:
            transfer = self.raiden.api.transfer_async(
                    self.asset_address,
                    amount,
                    self.partner_address,
                )
            if self.ui_server:
                requests.get(self.ui_server + '/pay/'+str(amount))
        except ValueError:
            print 'Insufficient Funds in channel'
            transfer = None # FIXME
    	try:
    	    return transfer.get()
    	except Exception as e:
    	    raise e


    def event_watcher(self,channel, callback=None):
        while True:
            gevent.sleep(0.001)
            if GPIO.event_detected(2):
                callback()

    def run(self):
        import signal
        from gevent.event import Event
        GPIO.add_event_detect(2, GPIO.RISING, bouncetime=100)
        # transfer initial deposit to get the light going
        initial_amount = self.channel.balance 
        prepaid_amount = 4
        if self.ui_server:
            requests.get(self.ui_server + '/init/'+str(initial_amount))
            requests.get(self.ui_server + '/pay/' + str(prepaid_amount))
	gevent.spawn(self.transfer, prepaid_amount)
        # event polling for impulse, execute callback on event
        gevent.spawn(self.event_watcher,2,self.event_callback)
        evt = Event()
        gevent.signal(signal.SIGQUIT, evt.set)
        gevent.signal(signal.SIGTERM, evt.set)
        evt.wait()
        self.cleanup()


class PowerConsumerRaspberry(PowerConsumerBase):
    """
    Sets up the raspberry's GPIOs, registers callback with the impules event
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(17, GPIO.OUT)

    def __init__(self, raiden, initial_price, asset_address, partner_address, ui_server=None):
        import RPi.GPIO as GPIO
        super(PowerConsumerRaspberry, self).__init__(raiden, initial_price, asset_address, partner_address, ui_server)

     # GPIO has fixed callback argument channel

    def setup_event(self, callback=None):
        GPIO.add_event_detect(2, GPIO.RISING, callback=callback, bouncetime=100)

    def cleanup(self):
        GPIO.cleanup()
