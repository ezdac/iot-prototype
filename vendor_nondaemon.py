import sys, os, time, atexit
from signal import SIGTERM
import time
import RPi.GPIO as GPIO

import raiden
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

    TODO: apart from impulse-callback, register transaction received callback
        That way the relay can be turned on again when a transaction is balancing
        a debit that is too high

        receive_callback:
            -) check debit/credit
            -) require prepay to activate the relay
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(17, GPIO.OUT)
    log_fn = '/home/alarm/data/power.log'
    energyPerImpulse = 1/2000. # in kWh per Impulse
    pricePerKwh = 10000 # TODO: get price per kWh per livefeed from somewhere...

    def __init__(self, buyer, vendor):
        self.buyer = buyer
        self.vendor = vendor
        self.count = 0
        self.relay_active = False
        self.electricity_consumed = 0
        # TODO: global credit pool, summation over different payment channels?
        self.credit = 0
        self.tolerance = 100


     # GPIO has fixed callback argument channel
    def event_callback(self, channel):
        self.count += 1
        self.electricity_consumed += self.energyPerImpulse
        print 'count: {}'.format(self.count)
        # ofh = open(self.log_fn, 'a')
        # ofh.write('{}, {}\n'.format(time.time(), GPIO.input(channel)))
        # ofh.flush()
        debit = self.electricity_consumed * self.pricePerKwh
        credit = self.vendor.get_balance() # XXX checkme
        if credit - debit >= tolerance:
            self.deactivate_relay()

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


class RaidenNode(object):
	from raiden.app import App

	def __init__(self, app):
		assert isinstance(app, App)
		self.app = app
		self.assetmanager = app.raiden.assetmanagers.values()[0]
        self.address = pex(app.raiden.address)

    @export_rpc
    def set_partner(self, address):
        self.partner = address # pexed address, TODO: accept both

    @export_rpc
	def get_channel(self, address):
		return self.assetmanager[address]

    @export_rpc
	def get_balance(self, address):
		chan = self.get_channel(address)
		return chan.balance

	# cb(id, success) ?
	@export_rpc
	def transfer(self, asset_address, amount, target, cb=None):
	    self.app.raiden.api.transfer(
            asset_address,
        	amount,
        	target=target,
			callback=cb
    	)

    @export_rpc
    def transfer_partner(self, amount):
        assert hasattr(self, partner)
        target = self.partner
        asset = self.get_channel(target) #XXX checkme
        self.transfer(self, asset, amount, target)



class RaidenBuyer(RaidenNode):
	pass
class RaidenVendor(RaidenNode):
	pass


    # def __init__(self):

    #     self.buyer, self.vendor = create_network(num_nodes=2, num_assets=1, channels_per_node=1)
    #     messages = setup_messages_cb()
    #     mlogger = MessageLogger()
    #     self.vendor_address = pex(app1.raiden.address)
	#
    # buyer_am = self.buyer.raiden.assetmanagers.values()[0]
    # vendor_am = self.vendor.raiden.assetmanagers.values()[0]
	#
    # channel0 = buyer_am.channels[app1.raiden.address]
    # channel1 = vendor_am.channels[app0.raiden.address]
	#
    # buyer_balance = channel0.balance
    #  = channel1.balance
	#
    # assert asset_manager0.asset_address == asset_manager1.asset_address
    # assert app1.raiden.address in asset_manager0.channels
	#
    # amount = 10
    # app0.raiden.api.transfer(
    #     asset_manager0.asset_address,
    #     amount,
    #     target=app1.raiden.address,
    # )
    # gevent.sleep(1)


if __name__ == "__main__":
    apps = create_network(num_nodes=2, num_assets=1, channels_per_node=1)
	buyer, vendor = [RaidenNode(app) for app in apps]
    buyer.set_partner(vendor.address)
    vendor.set_partner(buyer.address)
    pm = PowerMeter()
    data = {'app': pm,
            # 'vendor': vendor,
            'buyer': buyer
            }
    pm_thread = gevent.spawn(pm.start)
    routes = [
        ('/', static_wsgi_app),
        ('/data', PlotApplication),
        ('/buyer', buyer)
    ]
    resource = _Resource(routes, extra=data)
    server = WebSocketServer(('', 8000), resource, debug=True)

    try:
        server.serve_forever()
    finally:
        GPIO.cleanup()
