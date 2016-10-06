from collections import namedtuple
import logging
import operator
from socket import timeout
import struct

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

	def __init__(self, data):
		assert len(data) < 128
		self._data = data

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, self._data)

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
			return None
		return packet

	@property
	def terminal(self):
		return len(self._data) < 127

	@property
	def data(self):
		return self._data

class NewtonCommand(object):
	MAP = {}

def add_command(cls):
	NewtonCommand.MAP[cls.IDENTIFIER] = cls
	return cls

class StructCommand(NewtonCommand):
	@classmethod
	def parse(cls, data):
		args = struct.unpack(cls.SHAPE, data)
		return cls(*args)

@add_command
class SetTimeCommand(StructCommand, namedtuple('SetTimeCommandBase', 'unknown1 secs mins hours day month unknown2 year')):
	# Is the unknown1 optional? I've seen this sent without it...
	IDENTIFIER = 0x04
	SHAPE = '<bbbbbbbh'

	def as_datetime(self):
		return datetime.datetime(self.year, self.month, self.day, self.hours, self.mins, self.secs)

	@staticmethod
	def get_response(_simulator):
		return None

@add_command
class GetFileCountCommand(StructCommand, namedtuple('GetFileCountCommandBase', '')):
	IDENTIFIER = 0x08
	SHAPE = ''

	@staticmethod
	def get_response(_simulator):
		return '\x00\x00'

@add_command
class GetSerialNumberCommand(StructCommand, namedtuple('GetSerialNumberCommandBase', '')):
	IDENTIFIER = 0x09
	SHAPE = ''

	@staticmethod
	def get_response(simulator):
		return ''.join([chr(int(x, 16)) for x in simulator.serial_number.split('-')])

@add_command
class GetFirmwareVersionCommand(StructCommand, namedtuple('GetFirmwareVersionCommandBase', '')):
	IDENTIFIER = 0x0e
	SHAPE = ''

	@staticmethod
	def get_response(simulator):
		# jamming data into Isaac:
		# 5800 == sadness
		# 5801 == 3.44
		# 5802 == 6.00
		# 5902 == 6.01
		# formula changes here (subtract 5.00 after this point!)
		# 6002 == 1.08
		# 7f02 == 1.39
		# ff02 == 2.67
		# 5803 == 3.56
		# 5804 == 6.12
		# 5805 == 8.68
		return struct.pack('<h', int(simulator.firmware_version * 100 + 500))

@add_command
class GetProfileNumberCommand(StructCommand, namedtuple('GetProfileNumberCommandBase', '')):
	IDENTIFIER = 0x1c
	SHAPE = ''

	@staticmethod
	def get_response(_simulator):
		return '\x00\x00'

@add_command
class GetProfileDataCommand(StructCommand, namedtuple('GetProfileDataCommandBase', '')):
	IDENTIFIER = 0x1f
	SHAPE = ''

	@staticmethod
	def get_response(simulator):
		data = ''.join(profile.get_binary() for profile in simulator.profiles)
		# TODO is this int32, or 2*int16 with unknown second value?
		return struct.pack('<i', len(data)) + data

PROFILE_FIELDS = [
	('unknown_0', 'h'),
	('sample_smooth', 'h', {14554: 1, 14546: 5}),
	('unknown_1', 'h'),
	('null_1', 'i'),
	('null_2', 'h'),
	('user_edited', 'b', {14: False, 5: True}),
	('unknown_2', 'b'), # 0x80
	('total_mass_lb', 'h'),
	('wheel_circumference_mm', 'h'),
	('null_3', 'h'),
	('unknown_3', 'h'),
	('null_4', 'h'),
	('unknown_4', 'h'),
	('unknown_5', 'h'),
	('aero', 'f'),
	('fric', 'f'),
	('unknown_6', 'f'),
	('unknown_7', 'f'),
	('unknown_8', 'i'),
	('wind_scaling_sqrt', 'f'),
	('tilt_mult_10', 'h'),
	('cal_mass_lb', 'h'),
	('rider_mass_lb', 'h'),
	('unknown_9', 'h'),
	('ftp_per_kilo_ish', 'h'),
	('ftp_over_095', 'h'),
	('unknown_a', 'h'),
	('speed_id', 'H'),
	('cadence_id', 'H'),
	('hr_id', 'H'),
	('power_id', 'H'),
	('speed_type', 'B'),
	('cadence_type', 'B'),
	('hr_type', 'B'),
	('power_type', 'B'),
	('power_smoothing_seconds', 'H'),
	('unknown_c', 'h'),
]
class NewtonProfile(object):
	__slots__ = zip(*PROFILE_FIELDS)[0]
	FORMAT = '<' + ''.join(zip(*PROFILE_FIELDS)[1])
	def __init__(self, *args):
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)

	def get_binary(self):
		return struct.pack(self.FORMAT, *[getattr(self, name) for name in self.__slots__])

	@classmethod
	def from_binary_get_profile_result(cls, data):
		length_part = data[:4]
		# TODO is this int32 or int16*2?
		length = struct.unpack('<i', length_part)[0]
		assert length == 328, (length, repr(data))
		return [cls.from_binary(data[4 + i * 82:86 + i * 82]) for i in range(4)]

	@classmethod
	def from_binary(cls, data):
		return cls(*struct.unpack(cls.FORMAT, data))

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

@add_command
class GetFileCommand(StructCommand, namedtuple('GetFileCommandBase', 'ride_number')):
	IDENTIFIER = 0x20
	SHAPE = '<h'

	def get_response(self, simulator):
		return simulator.rides[self.ride_number].get_binary()

RIDE_FIELDS = [
	('unknown_0', '14s'),
	('aero', 'f'),
	('fric', 'f'),
	('unknown_1', '28s'),
	('Cm', 'f'),
	('unknown_2', '2s'),
	('wind_scaling_sqrt', 'f'),
	('unknown_3', '22s')
]
class NewtonRide(object):
	__slots__ = zip(*RIDE_FIELDS)[0] + ('data',)
	FORMAT = '<' + ''.join(zip(*RIDE_FIELDS)[1])
	def __init__(self, *args):
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)

	@classmethod
	def from_binary(cls, data):
		fixed_part = data[:82]
		data_part = data[82:]
		data = map(NewtonRideData.from_binary, (data_part[x:x+15] for x in range(0, len(data_part), 15)))
		return cls(*(struct.unpack(cls.FORMAT, fixed_part) + (data,)))

	def get_binary(self):
		fixed_part = struct.pack(self.FORMAT, *[getattr(self, name) for name in self.__slots__[:-1]])
		data_part = ''.join(map(NewtonRideData.get_binary, self.data))
		return fixed_part + data_part

	def get_header(self):
		return '\x11\x00\x06\x12\x03\x18\x09\x1e\xe0\x07\x27\xde\x77\x47'

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

RIDE_DATA_FIELDS = [
	('elevation_feet', 16),
	('cadence', 8),
	('heart_rate', 8),
	('temperature_farenheit_plus_132', 8),
	('unknown_0', 9),
	('tilt_times_10', 10),
	('speed_mph_times_10', 10),
	('unknown_1', 2),
	('wind_speed_mph_times_10_maybe', 8),
	('power_watts', 11),
	('unknown_2', 11),
	('acceleration_maybe', 10),
	('unknwon_3', 9),
]
assert sum(x[1] for x in RIDE_DATA_FIELDS) == 15 * 8
DECODE_FIFTEEN_BYTES = '{:08b}' * 15
ENCODE_FIFTEEN_BYTES = ''.join('{:0%sb}' % (size,) for _name, size in RIDE_DATA_FIELDS)
class NewtonRideData(object):
	__slots__ = zip(*RIDE_DATA_FIELDS)[0]
	def __init__(self, *args):
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)

	@classmethod
	def from_binary(cls, data):
		binary = DECODE_FIFTEEN_BYTES.format(*struct.unpack('15B', data))
		vals = []
		start = 0
		for _name, size in RIDE_DATA_FIELDS:
			value = int(binary[start:start+size], 2)
			start += size
			if value & (1 << (size - 1)):
				value -= 1 << size
			vals.append(value)
		return cls(*vals)

	def get_binary(self):
		vals = []
		for name, size in RIDE_DATA_FIELDS:
			value = getattr(self, name)
			if value < 0:
				value += 2 << size
			vals.append(value)
		binary = ENCODE_FIFTEEN_BYTES.format(*vals)
		chopped = [int(binary[x:x+8], 2) for x in range(0, 15*8, 8)]
		return struct.pack('15B', *chopped)

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

@add_command
class GetFileListCommand(StructCommand, namedtuple('GetFileListCommandBase', '')):
	IDENTIFIER = 0x21
	SHAPE = ''

	@staticmethod
	def get_response(simulator):
		return struct.pack('<h', len(simulator.rides)) + ''.join(ride.get_header() for ride in simulator.rides)

@add_command
class UnknownCommand(StructCommand, namedtuple('UnknownCommandBase', '')):
	""" This is sent before GetFileListCommand... """
	IDENTIFIER = 0x22
	SHAPE = ''

	@staticmethod
	def get_response(_simulator):
		return '\x00\x02\x00\x00'

class NewtonSerialProtocol(object):
	def __init__(self, connection):
		self.connection = connection

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
				self.write_packet(CommandAckPacket())
				message = ''.join(part.data for part in message_parts)
				LOGGER.info("read_message %r", message)
				return message
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
		message_parts = [ message[127*i:127*(i+1)] for i in range(len(message)/127+1) ]
		for message_part in message_parts:
			if not self._write_message_part(message_part):
				return

	def _write_message_part(self, message_part):
		self.write_packet(ReadyPacket())
		packet = self.read_packet()
		if not isinstance(packet, AckPacket):
			LOGGER.warning("unexpected_write_ready %r", packet)
			self.write_packet(InterruptPacket())
			return False
		self.write_packet(MessagePacket(message_part))
		packet = self.read_packet()
		if not isinstance(packet, AckPacket):
			LOGGER.warning("unexpected_write_ack %r", packet)
			self.write_packet(InterruptPacket())
			return False
		LOGGER.info("wrote_message %r", message_part)
		return True
