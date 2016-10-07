import threading
import ipdb
import connection
import logging

LOGGER = logging.getLogger(__name__)



class NewtonSimulator(threading.Thread):
	firmware_version = 6.12
	serial_number = '-'.join(['00'] * 16)
	def __init__(self, serial_connection=None):
		super(NewtonSimulator, self).__init__()
		if serial_connection is None:
			serial_connection = connection.NewtonSerialConnection()
		self.serial_connection = serial_connection
		self.protocol = None
		self.profiles = None
		self.reload = False
		self.init()

	def do_reload(self):
		self.reload = False
		reload(connection)
		self.init()

	def init(self):
		self.profiles = connection.NewtonProfile.from_binary_get_profile_result(INITIAL_PROFILE)
		self.rides = [connection.NewtonRide.from_binary(INITIAL_RIDE)]
		self.protocol = connection.NewtonSerialProtocol(self.serial_connection)

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
				command = connection.NewtonCommand.MAP[identifier].parse(data)
				if (identifier, last_identifier) in [(0x09, 0x0e), (0x0e, 0x09)]:
					log = LOGGER.debug
					last_identifier = identifier
				else:
					log = LOGGER.info
				log("<- %r", command)
				response = command.get_response(self)
				log("-> %r", str(response)[:200])
				self.protocol.write_message(response)

if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	sim = NewtonSimulator()
	sim.setDaemon(True)
	sim.start()
	ipdb.set_trace()
