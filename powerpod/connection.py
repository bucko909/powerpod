import logging
import operator
from socket import timeout

import serial

LOGGER = logging.getLogger(__name__)

class NewtonSerialConnection(serial.Serial):
	def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
		super(NewtonSerialConnection, self).__init__(port=port, baudrate=baudrate)

	def __enter__(self):
		try:
			self.open()
		except serial.serialutil.SerialException:
			self.close()
			self.open()
		return self

	def __exit__(self, *args):
		self.close()

class Packet(object):
	PACKET_TYPES = {}

def add_packet(cls):
	Packet.PACKET_TYPES[cls.INITIAL] = cls
	return cls

class BasicPacket(Packet):
	@classmethod
	def __repr__(cls):
		return '{}()'.format(cls.__name__)

	@property
	def wire_value(self):
		return self.INITIAL

	@staticmethod
	def read_length(data):
		return 0

	@classmethod
	def parse(cls, data):
		if data == cls.INITIAL:
			return cls()
		return None

@add_packet
class CommandAckPacket(BasicPacket):
	NAME = 'COMMAND_ACK'
	INITIAL = '\x00'

@add_packet
class AckPacket(BasicPacket):
	NAME = 'ACK'
	INITIAL = '\x90'

@add_packet
class ReadyPacket(BasicPacket):
	NAME = 'READY'
	INITIAL = '\x80'

@add_packet
class InterruptPacket(BasicPacket):
	NAME = 'INTERRUPT'
	INITIAL = '\xa0'

@add_packet
class MessagePacket(Packet):
	INITIAL = '\xf7'

	def __init__(self, data, length=None):
		assert len(data) < 128
		self._data = data

	def __repr__(self):
		return '{}({!r}, length={})'.format(self.__class__.__name__, self._data, len(self._data))

	@property
	def checksum(self):
		return chr(reduce(operator.xor, map(ord, self._data)) ^ 255 ^ len(self._data))

	@property
	def wire_value(self):
		return '\xf7\x7f{}{}{}'.format(chr(len(self._data)), self._data, self.checksum)

	@staticmethod
	def read_length(data):
		if len(data) < 3:
			return 4 - len(data)
		elif data[:2] != '\xf7\x7f':
			return None
		length = ord(data[2])
		return ord(data[2]) + 4 - len(data)

	@classmethod
	def parse(cls, data):
		if data[:2] != '\xf7\x7f':
			return None
		length = ord(data[3])
		if ord(data[2]) + 4 != len(data):
			return None
		checksum = data[-1]
		packet = cls(data[3:-1])
		if packet.checksum != checksum:
			LOGGER.warning("Invalid checksum on data packet %r; ignoring!", packet)
			return None
		return packet

	@property
	def terminal(self):
		return len(self._data) < 63

	@property
	def data(self):
		return self._data

class NewtonSerialProtocol(object):
	def __init__(self, connection, device_side=True):
		self.connection = connection
		self.device_side = device_side

	def read_packet(self):
		data = None
		while True:
			if data is not None:
				LOGGER.warning("invalid_packet %r", data)
				self.write_packet(InterruptPacket())
			self.connection.timeout = None
			data = self.connection.read(1)
			packet_type = Packet.PACKET_TYPES.get(data)
			if packet_type is None:
				continue
			self.connection.timeout = 0.1
			while True:
				remain = packet_type.read_length(data)
				if remain <= 0:
					break
				data += self.connection.read(remain)
			packet = packet_type.parse(data)
			if packet is None:
				continue
			LOGGER.debug("received_packet %r", packet)
			return packet

	def write_packet(self, packet):
		self.connection.timeout = 0.1
		wire_value = packet.wire_value
		bytes_written = self.connection.write(wire_value)
		if bytes_written == len(wire_value):
			LOGGER.debug("sent_packet %r", packet)
		else:
			LOGGER.warning("short_write %r", packet)

	def read_message(self):
		# read ReadyPacket
		# write AckPacket
		# read MessagePacket
		# write CommandAckPacket
		conversation = []
		message_parts = []
		while True:
			if conversation:
				LOGGER.warning("unexpected_read_conversation %r", conversation)
				self.write_packet(InterruptPacket())
				conversation = []
			conversation.append(self.read_packet())
			if not isinstance(conversation[-1], ReadyPacket):
				continue
			self.write_packet(AckPacket())
			conversation.append(self.read_packet())
			if not isinstance(conversation[-1], MessagePacket):
				continue
			message_parts.append(conversation[-1])
			if conversation[-1].terminal:
				self.write_packet(self.ack_to_send())
				message = ''.join(part.data for part in message_parts)
				LOGGER.debug("read_message %r", message)
				return message
			self.write_packet(AckPacket())
			LOGGER.debug("read_partial")
			conversation = []

	def write_message(self, message):
		# write ReadyPacket
		# read AckPacket
		# write MessagePacket
		# read AckPacket
		# OR
		# just do nothing (no reply, eg. set time)
		if message is None:
			self.write_packet(CommandAckPacket())
			return
		message_parts = [ message[63*i:63*(i+1)] for i in range(len(message)/63+1) ]
		for message_part in message_parts:
			if not self._write_message_part(message_part):
				return

	@property
	def ack_to_send(self):
		if self.device_side:
			return CommandAckPacket
		else:
			return AckPacket

	@property
	def expected_write_ack(self):
		if self.device_side:
			return AckPacket
		else:
			return CommandAckPacket

	def _write_message_part(self, message_part):
		self.write_packet(ReadyPacket())
		packet = self.read_packet()
		if not isinstance(packet, AckPacket):
			LOGGER.warning("unexpected_write_ready %r", packet)
			self.write_packet(InterruptPacket())
			return False
		self.write_packet(MessagePacket(message_part))
		packet = self.read_packet()
		if not isinstance(packet, self.expected_write_ack):
			LOGGER.warning("unexpected_write_ack %r", packet)
			self.write_packet(InterruptPacket())
			return False
		LOGGER.debug("wrote_message %r", message_part)
		return True

	def do_command(self, command):
		self.write_message(command.to_binary())
		if command.RESPONSE is None:
			return None
		response_raw = self.read_message()
		response = command.RESPONSE.from_binary(response_raw)
		assert response.to_binary() == response_raw
		return response
