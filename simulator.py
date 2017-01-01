import threading
import logging
import argparse

import powerpod

LOGGER = logging.getLogger(__name__)

class NewtonSimulator(threading.Thread):
	firmware_version = 6.12
	serial_number = '-'.join(['00'] * 16)
	def __init__(self, serial_connection=None):
		super(NewtonSimulator, self).__init__()
		if serial_connection is None:
			serial_connection = powerpod.NewtonSerialConnection()
		self.serial_connection = serial_connection
		self.protocol = None
		self.profiles = None
		self.current_profile = 0
		self.odometer_distance = 0.0
		self.reload = False
		self.screens = [powerpod.NewtonProfileScreens.default() for _ in range(4)]
		self.init()

	def do_reload(self):
		self.reload = False
		reload(powerpod)
		self.init()

	def init(self):
		self.profiles = [powerpod.types.NewtonProfile.default() for _ in range(4)]
		self.rides = [
			powerpod.types.NewtonRide.make(
				[powerpod.types.NewtonRideData(10, 0, 100, 100, 0, 0.0, 10.0, 620, 100, 200, x - 100 if x >= 100 and x < 200 else 0, 1, 5) for x in range(1000)]
			)
		]
		self.protocol = powerpod.NewtonSerialProtocol(self.serial_connection)

	def run(self):
		last_identifier = 0x09 # skip first firmware
		with self.serial_connection:
			while True:
				if self.reload:
					self.do_reload()
					break
				message = self.protocol.read_message()
				identifier = ord(message[0])
				data = message[1:]
				command = powerpod.NewtonCommand.MAP[identifier].parse(data)
				if (identifier, last_identifier) in [(0x09, 0x0e), (0x0e, 0x09)]:
					# Newton sends get firmware/get serial every second or so
					# Log these as debug messages.
					log = LOGGER.debug
					last_identifier = identifier
				else:
					log = LOGGER.info
				log("<- %r", command)
				response = command.get_response(self)
				log("-> %s", repr(response)[:200])
				response_bin = None if response is None else response.to_binary()
				self.protocol.write_message(response_bin)

def arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--port')
	return parser

def main():
	logging.basicConfig(level=logging.INFO)
	args = arg_parser().parse_args()
	kwargs = {}
	if args.port is not None:
		kwargs['serial_connection'] = powerpod.NewtonSerialConnection(port=args.port)
	sim = NewtonSimulator(**kwargs)
	sim.run()

if __name__ == '__main__':
	main()
