import sys, os, time, atexit
from signal import SIGTERM


import time
import RPi.GPIO as GPIO
#import RPIO as GPIO # drop-in-replacement!

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

 	# GPIO has fixed callback argument channel
	def event_callback(self, channel):
		self.count += 1
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



	def run(self):
		# ofh = open(self.log_fn, 'a')
		GPIO.add_event_detect(2, GPIO.RISING, callback=self.event_callback, bouncetime=100)
		self.activate_relay()
		while True:
			try:
				time.sleep(1)
				continue
			except KeyboardInterrupt:
				self.cleanup()
				sys.exit()

	def cleanup(self):
		GPIO.cleanup()

if __name__ == "__main__":
	pm = PowerMeter()
	pm.run()
