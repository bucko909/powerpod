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
class SetTimeCommand(NewtonCommand, namedtuple('SetTimeCommandBase', 'unknown newton_time')):
	# Is the unknown1 optional? I've seen this sent without it...
	IDENTIFIER = 0x04
	SHAPE = '<b8s'

	@classmethod
	def parse(cls, data):
		unknown, time_bin = struct.unpack(cls.SHAPE, data)
		return cls(unknown, NewtonTime.from_binary(time_bin))

	@staticmethod
	def get_response(_simulator):
		return None

TIME_FIELDS = [
	('secs', 'b'),
	('mins', 'b'),
	('hours', 'b'),
	('day', 'b'),
	('month', 'b'),
	('unknown', 'b'),
	('year', 'h'),
]
TIME_SHAPE = '<' + ''.join(zip(*TIME_FIELDS)[1])
class NewtonTime(namedtuple('NewtonTime', zip(*TIME_FIELDS)[0])):
	def as_datetime(self):
		return datetime.datetime(self.year, self.month, self.day, self.hours, self.mins, self.secs)

	@classmethod
	def from_binary(cls, data):
		return cls(*struct.unpack(TIME_SHAPE, data))

	def get_binary(self):
		return struct.pack(TIME_SHAPE, *self)

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

IDENTITY = lambda x: x
RIDE_FIELDS = [
	('unknown_0', 'h', IDENTITY, IDENTITY), # byte 0
	('data_records', 'i', IDENTITY, IDENTITY), # byte 2
	('total_mass_lb', 'f', IDENTITY, IDENTITY), # byte 6, always integer?!, could be total mass
	('energy_kJ', 'f', IDENTITY, IDENTITY), # byte 10
	('aero', 'f', IDENTITY, IDENTITY), # byte 14
	('fric', 'f', IDENTITY, IDENTITY), # byte 18
	('initial_elevation_feet', 'f', IDENTITY, IDENTITY), # byte 22, always integer?!
	('elevation_gain_feet', 'f', IDENTITY, IDENTITY), # byte 26, always integer?!
	('wheel_circumference_mm', 'f', IDENTITY, IDENTITY), # byte 30, always integer?!
	('unknown_1', 'h', IDENTITY, IDENTITY), # byte 34, 0x0f00 and 0x0e00 and 0x0e00 observed; multiplying by 10 does nothing observable.
	('unknown_2', 'h', IDENTITY, IDENTITY), # byte 36, =1?
	('start_time', '8s', NewtonTime.from_binary, NewtonTime.get_binary), # byte 38
	('pressure_Pa', 'i', IDENTITY, IDENTITY), # byte 46, appears to be pressure in Pa (observed range 100121-103175) # (setting, reported) = [(113175, 1113), (103175, 1014), (93175, 915), (203175, 1996), (1e9, 9825490), (2e9, 19650979), (-2e9, -19650979)]. Reported value in Isaac (hPa) is this divided by ~101.7761 or multiplied by 0.00982549. This isn't affected by truncating the ride at all. It /is/ affected by unknown_3; if I make unknown_3 -73 from 73, I get (-2e9, -19521083).
	('Cm', 'f', IDENTITY, IDENTITY), # byte 50
	('unknown_3', 'h', IDENTITY, IDENTITY), # byte 54, 0x4900 and 0x4800 and 0x4500 observed # temperature? It's not the /ride/ temperature at least. It affects pressure_Pa. Humidity?
	('wind_scaling_sqrt', 'f', IDENTITY, IDENTITY), # byte 56
	('riding_tilt_times_10', 'h', IDENTITY, IDENTITY), # byte 60
	('cal_mass_lb', 'h', IDENTITY, IDENTITY), # byte 62
	('unknown_5', 'h', IDENTITY, IDENTITY), # byte 64, 0x5800 and 0x6000 and 0x5c00 observed; multiplying by 10 doesn't do much...
	('unknown_6', 'h', IDENTITY, IDENTITY), # byte 66, ?? 0x6d06 == 1645 observed # kinda close to ratio pressure_Pa to pressure offset?; multiply by 10 = no wind; divide by 10 = no wind. Add 10 = slightly weaker wind; subtract 10 = slightly stronger wind. So closer to just the pressure offset. TODO
	('unknown_7', 'i', IDENTITY, IDENTITY), # byte 68, 0x00000000 observed
	('unknown_8', 'h', IDENTITY, IDENTITY), # byte 72, 0x2001 == 288 observed; doesn't seem to affect anything when multiplied by 2/4.
	('ref_pressure_Pa', 'i', IDENTITY, IDENTITY), # byte 74
	('unknown_9', 'h', IDENTITY, IDENTITY), # byte 78 -- 0x0100 observed
	('unknown_a', 'h', IDENTITY, IDENTITY), # byte 80 -- 0x3200 observed
	# byte 82
]
RIDE_DECODE = zip(*RIDE_FIELDS)[2]
RIDE_ENCODE = zip(*RIDE_FIELDS)[3]
class NewtonRide(object):
	__slots__ = zip(*RIDE_FIELDS)[0] + ('data',)
	FORMAT = '<' + ''.join(zip(*RIDE_FIELDS)[1])
	def __init__(self, *args):
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)
		self.data_records = min(self.data_records, 100)
		self.data = self.data[:100]
		#self.pressure_Pa = 2000000000
		print "pressure: %s" % self.pressure_Pa
		#self.unknown_3 = self.unknown_3
		print "unknown_3: %s" % self.unknown_3

	@classmethod
	def from_binary(cls, data):
		fixed_part = data[:82]
		data_part = data[82:]
		data = map(NewtonRideData.from_binary, (data_part[x:x+15] for x in range(0, len(data_part), 15)))
		return cls(*([decode(val) for val, decode in zip(struct.unpack(cls.FORMAT, fixed_part), RIDE_DECODE)] + [data]))

	def get_binary(self):
		fixed_part = struct.pack(self.FORMAT, *[encode(getattr(self, name)) for name, encode in zip(self.__slots__[:-1], RIDE_ENCODE)])
		data_part = ''.join(x.get_binary() for x in self.data)
		return fixed_part + data_part

	def get_header(self):
		# \x11\x00
		# newton time
		# float encoding of ride length in metres.
		return struct.pack('<h8sf', self.unknown_0, self.start_time.get_binary(), sum(x.speed_mph * 1602 / 3600. for x in self.data if isinstance(x, NewtonRideData)))
		#return '\x11\x00\x06\x12\x03\x18\x09\x1e\xe0\x07\x27\xde\x77\x47'

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

def swap_endian(x):
	return (x >> 8) + ((x & ((1 << 8) - 1)) << 8)

def to_signed(x, bits):
	if x & 1 << (bits - 1):
		return x - (1 << bits)
	else:
		return x

def to_unsigned(x, bits):
	if x < 0:
		return x + (1 << bits)
	else:
		return x

TO_TIMES_TEN_SIGNED = lambda base: lambda x: to_unsigned(int(x * 10), base)
FROM_TIMES_TEN_SIGNED = lambda base: lambda x: to_signed(x, base) * 0.1
FROM_TIMES_TEN = lambda x: x * 0.1
TO_TIMES_TEN = lambda x: int(x * 10)

RIDE_DATA_FIELDS = [
	('elevation_feet', 16, lambda x: to_signed(swap_endian(x), 16), lambda x: swap_endian(to_unsigned(x, 16))),
	('cadence', 8, IDENTITY, IDENTITY),
	('heart_rate', 8, IDENTITY, IDENTITY),
	('temperature_farenheit', 8, lambda x: x - 100, lambda x: x + 100),
	('unknown_0', 9, IDENTITY, IDENTITY), # Don't know what this is. Seems to be a signed 9 bit number, but even making drastic changes to it doesn't really bother Isaac.
	('tilt_times_10', 10, FROM_TIMES_TEN_SIGNED(10), TO_TIMES_TEN_SIGNED(10)),
	('speed_mph', 10, FROM_TIMES_TEN, TO_TIMES_TEN),
	#('unknown_1', 2, IDENTITY, IDENTITY),
	#('wind_speed_mph_maybe', 8, FROM_TIMES_TEN, TO_TIMES_TEN),
	('wind_tube_pressure_difference', 10, IDENTITY, IDENTITY),
	('power_watts', 11, IDENTITY, IDENTITY),
	('unknown_2', 11, IDENTITY, IDENTITY),
	('acceleration_maybe', 10, lambda x: to_signed(x, 10), lambda x: to_unsigned(x, 10)),
	('stopped_flag_maybe', 1, IDENTITY, IDENTITY),
	('unknown_3', 8, IDENTITY, IDENTITY), # if this is large, "drafting" becomes true
]
assert sum(x[1] for x in RIDE_DATA_FIELDS) == 15 * 8
DECODE_FIFTEEN_BYTES = '{:08b}' * 15
ENCODE_FIFTEEN_BYTES = ''.join('{:0%sb}' % (fielddef[1],) for fielddef in RIDE_DATA_FIELDS)
STROBE = 0
class NewtonRideData(object):
	__slots__ = zip(*RIDE_DATA_FIELDS)[0]
	def __init__(self, *args):
		global STROBE
		STROBE += 1
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)
		return
		# speed=20.0, u_1=0,1,2,3 ws=16.0 => ws=0,0,15,36.9
		# speed=10.0, u_1=0,1,2,3 ws=16.0 => ws=0,0,15,36.9
		# speed=20.0, u_1=0,1,2,3 ws=10.0 => ws=0,0,0,33.0
		# speed=20.0, u_1=0,1,2,3 ws=20.0 => ws=0,0,20.1,39.2
		# speed=20.0, u_1=0,1,2,3 ws=21.0 => ws=0,0,21.1,39.7
		# speed=20.0, u_1=0,1,2,3 ws=22.0 => ws=0,0,22.1,40.2
		# speed=20.0, u_1=0,1,2,3 ws=23.0 => ws=0,0,23.1,40.8
		# speed=20.0, u_1=0,1,2,3 ws=24.0 => ws=0,0,24.0,41.3
		# speed=20.0, u_1=0,1,2,3 ws=25.0 => ws=0,0,24.9,41.9
		#self.unknown_1 = (STROBE // 100) % 4
		self.elevation_feet = 0 # (STROBE // 200) * 100
		self.cadence = 0 #100 + STROBE % 100
		self.heart_rate = 100 + STROBE // 100
		self.temperature_farenheit = 73 # -100 + (STROBE) % 200
		self.unknown_0 = (STROBE // 10) % 512
		self.tilt_times_10 = -1.0 #+ (STROBE // 50) % 10
		self.speed_mph = 20.0 - abs(STROBE % 100 - 50) * ((STROBE // 200) % 4) * 0.1
		self.wind_tube_pressure_difference = 700 # + (STROBE // 400) * 10 # + (STROBE // 400)
		self.power_watts = 100 #+ (STROBE // 110) % 100
		self.unknown_2 = 0 #+ (STROBE // 130) % 100
		self.acceleration_maybe = 50 if (STROBE // 100) % 2 == 0 else -50
		self.stopped_flag_maybe = 1 if (STROBE % 71) == 0 else 0
		self.unknown_3 = 4 # (STROBE // 10) % 255
		# elevation_feet = 0, temperature_farenheit = 73, unknown_0 = 0, speed_mph = 20, power_watts = 100, unknown_2 = 0, acceleration_maybe = 0, unknown_3 = 0
		# 0 -> 42.2
		# TEMPERATURE has an effect. Increasing temperature increases wind speed!
		# unknown_0, speed_mph, power_watts, unknown_2, acceleration_maybe seem to do nothing.
		# messing with the last 9 bits seems to allow me to turn on 'drafting'


	@classmethod
	def from_binary(cls, data):
		if data.startswith('\xff\xff\xff\xff\xff\xff'):
			return NewtonRideDataPaused.from_binary(data)
		binary = DECODE_FIFTEEN_BYTES.format(*struct.unpack('15B', data))
		vals = []
		start = 0
		for _name, size, decode, _encode in RIDE_DATA_FIELDS:
			value = int(binary[start:start+size], 2)
			start += size
			vals.append(decode(value))
		return cls(*vals)

	def get_binary(self):
		vals = []
		for name, size, _decode, encode in RIDE_DATA_FIELDS:
			value = getattr(self, name)
			vals.append(encode(value))
		binary = ENCODE_FIFTEEN_BYTES.format(*vals)
		assert len(binary) == 15 * 8
		chopped = [int(binary[x:x+8], 2) for x in range(0, 15*8, 8)]
		return struct.pack('15B', *chopped)

	@property
	def elevation_metres(self):
		return self.elevation_feet * 0.3048

	@property
	def pressure_kPa(self):
		# Pascals
		return 101.325 * (1 - (0.0065 * self.elevation_metres) / 288.15) ** (9.80665 * 0.0289644 / 8.31447 / 0.0065)

	@property
	def temperature_kelvin(self):
		return (self.temperature_farenheit + 459.67) * 5 / 9

	@property
	def density(self):
		# I say 0.8773 at 22.7778C/2516.7336m; they say 0.8768. Good enough...
		return self.pressure_kPa * 1000 * 0.0289644 / 8.31447 / self.temperature_kelvin

	@property
	def wind_speed(self):
		# Based on solving from CSV file
		return ((self.wind_tube_pressure_difference - 621) / self.density * 13.6355) ** 0.5

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

class NewtonRideDataPaused(namedtuple('NewtonRideDataPaused', 'tag newton_time unknown_3')):
	@classmethod
	def from_binary(cls, data):
		tag, time_bin, unknown_3 = struct.unpack('<6s8sb', data)
		return cls(tag, NewtonTime.from_binary(time_bin), unknown_3)

	def get_binary(self):
		return struct.pack('<6s8sb', self.tag, self.newton_time.get_binary(), self.unknown_3)

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
				LOGGER.debug("read_message %r", message)
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
		LOGGER.debug("wrote_message %r", message_part)
		return True
