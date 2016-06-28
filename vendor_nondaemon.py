import sys, os, time, atexit
from signal import SIGTERM

class Daemon(object):
	"""
	A generic daemon class.

	Usage: subclass the Daemon class and override the run() method
	"""
	def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
		self.stdin = stdin
		self.stdout = stdout
		self.stderr = stderr
		self.pidfile = pidfile

	def daemonize(self):
		"""
		do the UNIX double-fork magic, see Stevens' "Advanced
		Programming in the UNIX Environment" for details (ISBN 0201563177)
		http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
		"""
		try:
			pid = os.fork()
			if pid > 0:
				# exit first parent
				sys.exit(0)
		except OSError, e:
			sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
			sys.exit(1)

		# decouple from parent environment
		os.chdir("/")
		os.setsid()
		os.umask(0)

		# do second fork
		try:
			pid = os.fork()
			if pid > 0:
				# exit from second parent
				sys.exit(0)
		except OSError, e:
			sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
			sys.exit(1)

		# redirect standard file descriptors
		sys.stdout.flush()
		sys.stderr.flush()
		si = file(self.stdin, 'r')
		so = file(self.stdout, 'a+')
		se = file(self.stderr, 'a+', 0)
		os.dup2(si.fileno(), sys.stdin.fileno())
		os.dup2(so.fileno(), sys.stdout.fileno())
		os.dup2(se.fileno(), sys.stderr.fileno())

		# write pidfile
		atexit.register(self.delpid)
		pid = str(os.getpid())
		file(self.pidfile,'w+').write("%s\n" % pid)

	def delpid(self):
		os.remove(self.pidfile)

	def start(self):
		"""
		Start the daemon
		"""
		# Check for a pidfile to see if the daemon already runs
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			pid = None

		if pid:
			message = "pidfile %s already exist. Daemon already running?\n"
			sys.stderr.write(message % self.pidfile)
			sys.exit(1)

		# Start the daemon
		self.daemonize()
		self.run()

	def stop(self):
		"""
		Stop the daemon
		"""
		# Get the pid from the pidfile
		try:
			pf = file(self.pidfile,'r')
			pid = int(pf.read().strip())
			pf.close()
		except IOError:
			pid = None

		if not pid:
			message = "pidfile %s does not exist. Daemon not running?\n"
			sys.stderr.write(message % self.pidfile)
			return # not an error in a restart

		# Try killing the daemon process
		try:
			while 1:
				os.kill(pid, SIGTERM)
				time.sleep(0.1)
		except OSError, err:
			err = str(err)
			if err.find("No such process") > 0:
				if os.path.exists(self.pidfile):
					os.remove(self.pidfile)
			else:
				print str(err)
				sys.exit(1)

	def restart(self):
		"""
		Restart the daemon
		"""
		self.stop()
		self.start()

	def run(self):
		"""
		You should override this method when you subclass Daemon. It will be called after the process has been
		daemonized by start() or restart().
		"""

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
	pricePerKwh

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
		if self.count >= 10 and not self.relay_active:
			self.count = 0
			self.activate_relay()
			# FIXME: race condition with next callback ?
			time.sleep(20)
			self.deactivate_relay()

	def activate_relay(self):
		GPIO.outpu(17, True)
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

		while True:
			try:
				time.sleep(1)
				continue
			except KeyboardInterrupt:
				self.cleanup()
				sys.exit()

	def cleanup(self):
		GPIO.cleanup()
		self.stop()

if __name__ == "__main__":
	pm = PowerMeter()
	pm.run()
