from collections import namedtuple
import datetime
import struct

class NewtonCommand(object):
	MAP = {}

	def get_response(self, simulator):
		return self.RESPONSE.from_simulator(self, simulator).get_binary()

def add_command(cls):
	NewtonCommand.MAP[cls.IDENTIFIER] = cls
	return cls

class StructType(object):
	@classmethod
	def from_binary(cls, data):
		return cls(*cls._decode(*struct.unpack(cls.SHAPE, data)))

	@staticmethod
	def _decode(*args):
		""" data from unpack -> data for __init__ """
		return args

	def get_binary(self):
		return struct.pack(self.SHAPE, *self._encode())

	def _encode(self):
		""" data from self -> data for pack """
		return self

class StructCommand(NewtonCommand, StructType):
	@classmethod
	def from_binary(cls, data):
		assert struct.unpack('b', data[0])[0] == self.IDENTIFIER
		return super(StructCommand, self).from_binary(data[1:])

	@classmethod
	def parse(cls, data):
		# TODO sort out this mess
		return super(StructCommand, cls).from_binary(data)

	def get_binary(self):
		return struct.pack('b', self.IDENTIFIER) + super(StructCommand, self).get_binary()

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
		# This command just sends a second ack packet when it's done?
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

class GetFileCountResponse(StructType, namedtuple('GetFileCountResponse', 'count')):
	SHAPE = '<h'

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls(len(simulator.rides))

@add_command
class GetFileCountCommand(StructCommand, namedtuple('GetFileCountCommandBase', '')):
	IDENTIFIER = 0x08
	SHAPE = ''
	RESPONSE = GetFileCountResponse

	@staticmethod
	def get_response(simulator):
		return ''.join([chr(int(x, 16)) for x in simulator.serial_number.split('-')])

class GetSerialNumberResponse(StructType, namedtuple('GetSerialNumberResponse', 'serial_number')):
	SHAPE = '16s'

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls(''.join(chr(int(x, 16)) for x in simulator.serial_number.split('-')))

@add_command
class GetSerialNumberCommand(StructCommand, namedtuple('GetSerialNumberCommandBase', '')):
	IDENTIFIER = 0x09
	SHAPE = ''
	RESPONSE = GetSerialNumberResponse

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

class GetFileResponse(namedtuple('GetFileResponse', 'ride_data')):
	@classmethod
	def parse(cls, data):
		return cls(NewtonRide.from_binary(data))

	def get_binary(self):
		return self.ride_data.get_binary()

	@classmethod
	def from_simulator(cls, command, simulator):
		return cls(simulator.rides[command.ride_number])

@add_command
class GetFileCommand(StructCommand, namedtuple('GetFileCommandBase', 'ride_number')):
	IDENTIFIER = 0x20
	SHAPE = '<h'
	RESPONSE = GetFileResponse

IDENTITY = lambda x: x
RIDE_FIELDS = [
	('unknown_0', 'h', IDENTITY, IDENTITY, 17), # byte 0 -- 0x1100 observed
	('data_records', 'i', IDENTITY, IDENTITY, 0), # byte 2
	('total_mass_lb', 'f', IDENTITY, IDENTITY, 235), # byte 6, always integer?!, could be total mass
	('energy_kJ', 'f', IDENTITY, IDENTITY, 0), # byte 10
	('aero', 'f', IDENTITY, IDENTITY, 0.384), # byte 14
	('fric', 'f', IDENTITY, IDENTITY, 12.0), # byte 18
	('initial_elevation_feet', 'f', IDENTITY, IDENTITY, 0), # byte 22, always integer?!
	('elevation_gain_feet', 'f', IDENTITY, IDENTITY, 0), # byte 26, always integer?!
	('wheel_circumference_mm', 'f', IDENTITY, IDENTITY, 2136.0), # byte 30, always integer?!
	('unknown_1', 'h', IDENTITY, IDENTITY, 15), # byte 34, 0x0f00 and 0x0e00 and 0x0e00 observed; multiplying by 10 does nothing observable.
	('unknown_2', 'h', IDENTITY, IDENTITY, 1), # byte 36, =1?
	('start_time', '8s', NewtonTime.from_binary, NewtonTime.get_binary, NewtonTime(0, 0, 0, 1, 1, 31, 2000)), # byte 38
	('pressure_Pa', 'i', IDENTITY, IDENTITY, 101325), # byte 46, appears to be pressure in Pa (observed range 100121-103175) # (setting, reported) = [(113175, 1113), (103175, 1014), (93175, 915), (203175, 1996), (1e9, 9825490), (2e9, 19650979), (-2e9, -19650979)]. Reported value in Isaac (hPa) is this divided by ~101.7761 or multiplied by 0.00982549. This isn't affected by truncating the ride at all. It /is/ affected by unknown_3; if I make unknown_3 -73 from 73, I get (-2e9, -19521083).
	('Cm', 'f', IDENTITY, IDENTITY, 1.0204), # byte 50
	('average_temperature_farenheit', 'h', IDENTITY, IDENTITY, 73), # byte 54. Average of temperature records. Does not affect displayed temperature in Isaac. It affects displayed pressure in Isaac (bigger temp = closer to pressure_Pa).
	('wind_scaling_sqrt', 'f', IDENTITY, IDENTITY, 1.0), # byte 56
	('riding_tilt_times_10', 'h', IDENTITY, IDENTITY, 0.0), # byte 60
	('cal_mass_lb', 'h', IDENTITY, IDENTITY, 235), # byte 62
	('unknown_5', 'h', IDENTITY, IDENTITY, 88), # byte 64, 0x5800 and 0x6000 and 0x5c00 observed; multiplying by 10 doesn't affect: wind speed, pressure, temperature, 
	('wind_tube_pressure_offset', 'h', lambda x: x - 1024, lambda x: x + 1024, 620), # byte 66, this is a 10-bit signed negative number cast to unsigned and stored in a 16 bit int...
	('unknown_7', 'i', IDENTITY, IDENTITY, 0), # byte 68, 0x00000000 observed
	('reference_temperature_kelvin', 'h', IDENTITY, IDENTITY, 288), # byte 72, normally 288 (14.85C)
	('reference_pressure_Pa', 'i', IDENTITY, IDENTITY, 101325), # byte 74
	('unknown_9', 'h', IDENTITY, IDENTITY, 1), # byte 78 -- 0x0100 observed
	('unknown_a', 'h', IDENTITY, IDENTITY, 50), # byte 80 -- 0x3200 observed
	# byte 82
]
RIDE_DECODE = zip(*RIDE_FIELDS)[2]
RIDE_ENCODE = zip(*RIDE_FIELDS)[3]
RIDE_DEFAULTS = {key: value for key, _, _, _, value in RIDE_FIELDS}
class NewtonRide(object):
	__slots__ = zip(*RIDE_FIELDS)[0] + ('data',)
	FORMAT = '<' + ''.join(zip(*RIDE_FIELDS)[1])
	def __init__(self, *args):
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)
		return
		self.wind_scaling_sqrt = 1.4
		data = [x for x in self.data if hasattr(x, 'temperature_farenheit')]
		#self.data_records = min(self.data_records, 100)
		#self.data = self.data[:100]
		#self.pressure_Pa = 2000000000
		print "pressure: %s" % self.pressure_Pa
		#self.unknown_3 = self.unknown_3
		# pressure_Pa = 103175
		# unknown_3 = 1, pressure = 1011mbar
		# unknown_3 = 100, pressure = 1015mbar
		# unknown_3 = 10000, pressure = 1031mbar
		self.pressure_Pa = int(1e9)
		# pressure_Pa = 1e9
		# unknown_3 = 1, pressure = 9798543mbar
		# unknown_3 = 100, pressure = 9833825mbar
		# unknown_3 = 10000, pressure = 9991024mbar
		#self.wind_scaling_sqrt = 2.0
		#self.unknown_5 *= 10

	@classmethod
	def make(cls, data, **kwargs):
		kwargs = {}
		for name in cls.__slots__[:-1]:
			kwargs[name] = RIDE_DEFAULTS[name]

		kwargs['data'] = data
		if data:
			# TODO start_time, elevation gain
			kwargs['average_temperature_farenheit'] = int(round(sum(x.temperature_farenheit for x in data if hasattr(x, 'temperature_farenheit')) / len(data)))
			kwargs['initial_elevation_feet'] = [x.elevation_feet for x in data if hasattr(x, 'elevation_feet')][0]
			kwargs['data_records'] = len(data)
			kwargs['energy_kJ'] = int(round(sum(x.power_watts for x in data if hasattr(x, 'power_watts')) / 1000))

		args = []
		for name in cls.__slots__:
			args.append(kwargs[name])
		return cls(*args)

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
		return NewtonRideHeader(self.unknown_0, self.start_time, sum(x.speed_mph * 1602 / 3600. for x in self.data if isinstance(x, NewtonRideData)))

	def fit_to(self, csv):
		pure_records = [x for x in self.data if not hasattr(x, 'newton_time')]
		csv_data = [float(x['Wind Speed (km/hr)']) for x in csv.data]
		compare = [(x, y) for x, y in zip(pure_records, csv_data) if y > 0]
		reference_pressure_kPa = self.reference_pressure_Pa / 1000.0
		get_errors = lambda offset, multiplier: [pure_record.wind_speed_kph(offset, multiplier, reference_pressure_kPa, self.reference_temperature_kelvin, self.wind_scaling_sqrt) - csv_datum for pure_record, csv_datum in compare]
		dirs = [(x, y) for x in range(-1, 2) for y in range(-1, 2) if x != 0 or y != 0]
		print dirs
		skip = 500
		best = current = (500, 10)
		best_error = float('inf')
		while skip > 0.000001:
			new_best = False
			for x, y in dirs:
				test = (current[0] + x * skip, current[1] + y * skip * 0.02)
				if test[1] < 0:
					continue
				error = sum(map(abs, get_errors(*test)))
				#print test, error
				if error < best_error:
					best = test
					best_error = error
					new_best = True
			if new_best:
				current = best
			else:
				skip *= 0.5
			#print best, skip, best_error
		errors = get_errors(*best)
		return best, best_error, max(map(abs, errors)), ["%0.4f" % (x,) for x in errors]

	def fit_elevation(self, csv):
		pure_records = [x for x in self.data if not hasattr(x, 'newton_time')]
		csv_data = [float(x['Elevation (meters)']) / 0.3048 for x in csv.data]
		compare = [(x, y) for x, y in zip(pure_records, csv_data)]
		get_errors = lambda mul: [(pure_record.density(), pure_record.elevation_feet, csv_datum, pure_record.elevation_feet - csv_datum, (pure_record.wind_tube_pressure_difference - self.wind_tube_pressure_offset), pure_record.tilt, pure_record.unknown_0, pure_record) for pure_record, csv_datum in compare]
		return get_errors(0.1)

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

class NewtonRideHeader(namedtuple('NewtonRideHeader', 'unknown_0 start_time distance_metres')):
	# \x11\x00
	# newton time
	# float encoding of ride length in metres.
	SHAPE = '<h8sf'
	SIZE = 14

	def get_binary(self):
		return struct.pack(self.SHAPE, self.unknown_0, self.start_time.get_binary(), self.distance_metres)

	@classmethod
	def parse(cls, data):
		unknown_0, start_time_raw, distance_metres = struct.unpack(cls.SHAPE, data)
		return cls(unknown_0, NewtonTime.from_binary(start_time_raw), distance_metres)

	@classmethod
	def parse_list(cls, data):
		length, = struct.unpack('<h', data[:2])
		assert len(data) == length * cls.SIZE + 2, (len(data), length, repr(data))
		return [cls.parse(data[2 + x * cls.SIZE:2 + (x + 1) * cls.SIZE]) for x in range(length)]

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
	('unknown_0', 9, lambda x: to_signed(x, 9), lambda x: to_unsigned(x, 9)), # Don't know what this is. Seems to be a signed 9 bit number, but even making drastic changes to it doesn't really bother Isaac.
	('tilt', 10, FROM_TIMES_TEN_SIGNED(10), TO_TIMES_TEN_SIGNED(10)),
	('speed_mph', 10, FROM_TIMES_TEN, TO_TIMES_TEN),
	('wind_tube_pressure_difference', 10, IDENTITY, IDENTITY),
	('power_watts', 11, IDENTITY, IDENTITY),
	('unknown_2', 11, IDENTITY, IDENTITY), # My guess is DFPM power.
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

	def pressure_kPa(self, reference_pressure_Pa=101.325, reference_temperature_kelvin=288.15):
		# Pascals
		return reference_pressure_Pa * (1 - (0.0065 * self.elevation_metres) / reference_temperature_kelvin) ** (9.80665 * 0.0289644 / 8.31447 / 0.0065)

	@property
	def temperature_kelvin(self):
		return (self.temperature_farenheit + 459.67) * 5 / 9

	def density(self, reference_pressure_Pa=101.325, reference_temperature_kelvin=288.15):
		# I say 0.8773 at 22.7778C/2516.7336m; they say 0.8768. Good enough...
		return self.pressure_kPa(reference_pressure_Pa, reference_temperature_kelvin) * 1000 * 0.0289644 / 8.31447 / self.temperature_kelvin

	def wind_speed_kph(self, offset=621, multiplier=13.6355, reference_pressure_Pa=101.325, reference_temperature_kelvin=288.15, wind_scaling_sqrt=1.0):
		# Based on solving from CSV file
		if self.wind_tube_pressure_difference < offset:
			return 0.0
		return ((self.wind_tube_pressure_difference - offset) / self.density(reference_pressure_Pa, reference_temperature_kelvin) * multiplier) ** 0.5 * wind_scaling_sqrt

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

class NewtonRideDataPaused(namedtuple('NewtonRideDataPaused', 'tag newton_time unknown_3')):
	@classmethod
	def from_binary(cls, data):
		tag, time_bin, unknown_3 = struct.unpack('<6s8sb', data)
		return cls(tag, NewtonTime.from_binary(time_bin), unknown_3)

	def get_binary(self):
		return struct.pack('<6s8sb', self.tag, self.newton_time.get_binary(), self.unknown_3)

class GetFileListResponse(namedtuple('GetFileListResponse', 'headers')):
	@classmethod
	def parse(cls, data):
		return cls(NewtonRideHeader.parse_list(data))

	def get_binary(self):
		return struct.pack('<h', len(self.headers)) + ''.join(header.get_binary() for header in self.headers)

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls([ride.get_header() for ride in simulator.rides])

@add_command
class GetFileListCommand(StructCommand, namedtuple('GetFileListCommandBase', '')):
	IDENTIFIER = 0x21
	SHAPE = ''
	RESPONSE = GetFileListResponse

@add_command
class UnknownCommand(StructCommand, namedtuple('UnknownCommandBase', '')):
	""" This is sent before GetFileListCommand... """
	IDENTIFIER = 0x22
	SHAPE = ''

	@staticmethod
	def get_response(_simulator):
		return '\x00\x02\x00\x00'

