import threading
import ipdb
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
		self.reload = False
		self.init()

	def do_reload(self):
		self.reload = False
		reload(powerpod)
		self.init()

	def init(self):
		self.profiles = powerpod.NewtonProfile.from_binary_get_profile_result(INITIAL_PROFILE)
		self.rides = [
			powerpod.messages.NewtonRide.make(
				[powerpod.messages.NewtonRideData(10, 0, 0, 100, 0, 0.0, 10.0, 620, 100, 0, 0, 1, 5) for x in range(1000)]
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
					log = LOGGER.debug
					last_identifier = identifier
				else:
					log = LOGGER.info
				log("<- %r", command)
				response = command.get_response(self)
				log("-> %r", str(response)[:200])
				self.protocol.write_message(response)

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
	sim.setDaemon(True)
	sim.start()
	ipdb.set_trace()

if __name__ == '__main__':
	main()
