from collections import namedtuple
import datetime
import calendar
import struct

class StructType(object):
	"""
	Automatically uses SHAPE to pack/unpack simple structs.
	"""
	@classmethod
	def from_binary(cls, data):
		return cls(*cls._decode(*struct.unpack(cls.SHAPE, data)))

	@staticmethod
	def _decode(*args):
		""" data from unpack -> data for __init__ """
		return args

	def to_binary(self):
		return struct.pack(self.SHAPE, *self._encode())

	def _encode(self):
		""" data from self -> data for pack """
		return self

	@property
	def size(self):
		return struct.Struct(self.SHAPE).size

class StructListType(object):
	"""
	Automatically uses SHAPE to pack/unpack simple structs which are followed by lists of RECORD_TYPE records.

	You must have 'size' in _fields, which must be the record count, and a 'records' field to hold the decoded records.

	RECORD_TYPE must have a 'size', and a 'from_binary' function.
	"""
	@classmethod
	def from_binary(cls, data):
		encode = struct.Struct(cls.SHAPE)
		header_size = encode.size
		header = encode.unpack(data[:header_size])
		size_offset = cls._fields.index('size')
		record_count = header[size_offset]
		record_size = struct.Struct(cls.RECORD_TYPE.SHAPE).size
		assert header_size + record_count * record_size == len(data)
		raw_records = [data[header_size + record_size * x:header_size + record_size * (x + 1)] for x in range(record_count)]
		return cls(*(cls._decode(*header) + (map(cls.RECORD_TYPE.from_binary, raw_records),)))

	@staticmethod
	def _decode(*args):
		""" data from unpack -> data for __init__ """
		return args

	def to_binary(self):
		assert self.size == len(self.records), (self.size, len(self.records))
		return struct.pack(self.SHAPE, *self._encode()) + ''.join(record.to_binary() for record in self.records)

	def _encode(self):
		""" data from self -> data for pack """
		record_offset = self._fields.index('records')
		return self[:record_offset] + self[record_offset+1:]

TIME_FIELDS = [
	('secs', 'b'),
	('mins', 'b'),
	('hours', 'b'),
	('day', 'b'),
	('month', 'b'),
	('month_length', 'b'),
	('year', 'h'),
]
class NewtonTime(StructType, namedtuple('NewtonTime', zip(*TIME_FIELDS)[0])):
	SHAPE = '<' + ''.join(zip(*TIME_FIELDS)[1])
	def as_datetime(self):
		return datetime.datetime(self.year, self.month, self.day, self.hours, self.mins, self.secs)

	@classmethod
	def from_datetime(cls, datetime):
		days_in_month = calendar.monthrange(datetime.year, datetime.month)[1]
		return cls(datetime.second, datetime.minute, datetime.hour, datetime.day, datetime.month, days_in_month, datetime.year)



PROFILE_FIELDS = [
	('unknown_0', 'h'),
	# Facts about sample_smoothing flags:
	# If I send (in GetProfileData) 0x0000, I get (in SetProfileData) 0x0800.
	# If I send                     0xffff, I get                     0xffdf.
	# If I send                     0x0539, I get                     0x0d19.
	# If I send                     0x2ef0, I get                     0x2ed0.
	# Both of these are preserved.
	# Conclusion: 0x0800 must be set, 0x0020 must be unset.
	# Switching from 5s sample smoothing to 1s sets 0x0008. Setting back unsets it.
	# Annoyingly, Isaac only resets to '1 sec' when you 'Get from iBike' -- it'll never reset to '5 sec', so I guess it just checks the flag.
	# Conclusion: 0x0008 is the "don't smooth for 5s" flag.
	# A reset profile gets 10251 (=0x280b)
	('sample_smoothing', 'H', {14554: 1, 14546: 5}),
	('unknown_1', 'h'),
	('null_1', 'i'),
	('null_2', 'h'),
	# If I send 0x0000, I get 0x8009.
	# If I send 0x8009, I get 0x8009.
	# If I send 0xffff, I get 0x8009.
	# If I then set the 'user-edited' flag by messing with stuff, I get 0x8005.
	# On a pristine profile, I see 0x800e or 0x800d and it's reset to 0x8009 with just a get/set. On an old recording, I saw it reset to 0x8005 on a user-edit.
	# Resetting the profile gets 0x800c.
	# Conclusion: Nothing to see here, but user edited-ness.
	('user_edited', 'H', {0x8009: False, 0x8005: True}),
	('total_mass_lb', 'h'),
	('wheel_circumference_mm', 'h'),
	('null_3', 'h'),
	('unknown_3', 'h'),
	('unknown_2', 'h'),
	('unknown_4', 'H'),
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
	('unknown_a', 'h'), # 0x0301 -> 0x0b01 (+0x0800) when sample rate changed to 1s. Never restored, though!
	('speed_id', 'H'),
	('cadence_id', 'H'),
	('hr_id', 'H'),
	('power_id', 'H'),
	('speed_type', 'B'),
	('cadence_type', 'B'),
	('hr_type', 'B'),
	('power_type', 'B'),
	('power_smoothing_seconds', 'H'),
	('unknown_c', 'h'), # 0x0032
]
class NewtonProfile(StructType, namedtuple('NewtonProfile', zip(*PROFILE_FIELDS)[0])):
	SHAPE = '<' + ''.join(zip(*PROFILE_FIELDS)[1])
	SIZE = struct.Struct(SHAPE).size

	@classmethod
	def _decode(cls, *args):
		# Alert when any of these are interesting.
		assert args[cls._fields.index('unknown_0')] == 0x5c16, args[cls._fields.index('unknown_0')]
		assert args[cls._fields.index('sample_smoothing')] in (0x38d2, 0x38da, 0x380b, 0x38fb, 0x382b, 0x38db, 0x280b), args[cls._fields.index('sample_smoothing')]
		assert args[cls._fields.index('unknown_1')] == 0x382b, args[cls._fields.index('unknown_1')]
		assert args[cls._fields.index('null_1')] == 0, args[cls._fields.index('null_1')]
		assert args[cls._fields.index('null_2')] == 0, args[cls._fields.index('null_2')]
		assert args[cls._fields.index('user_edited')] in (0x8009, 0x8005, 0x800d, 0x800c, 0x19, 0x8008), args[cls._fields.index('user_edited')]
		assert args[cls._fields.index('null_3')] == 0, args[cls._fields.index('null_3')]
		assert args[cls._fields.index('unknown_2')] in (0, 2), args[cls._fields.index('unknown_2')]
		assert args[cls._fields.index('unknown_3')] in (0, 0x1988, 0x5f5c), args[cls._fields.index('unknown_3')]
		assert args[cls._fields.index('unknown_4')] in (0xbc00, 0xe766, 0, 0x20ff), args[cls._fields.index('unknown_4')]
		assert args[cls._fields.index('unknown_5')] in (0, 1), args[cls._fields.index('unknown_5')]
		assert args[cls._fields.index('unknown_6')] in (-38.0, -10.0, 0.0), args[cls._fields.index('unknown_6')]
		assert args[cls._fields.index('unknown_7')] in (1.0, 0.0), args[cls._fields.index('unknown_7')]
		assert args[cls._fields.index('unknown_8')] == 1670644000, args[cls._fields.index('unknown_8')]
		assert args[cls._fields.index('unknown_9')] in (1850, 1803), args[cls._fields.index('unknown_9')]
		assert args[cls._fields.index('unknown_a')] in (0x0301, 0x0b01, 0x351), args[cls._fields.index('unknown_a')]
		assert args[cls._fields.index('unknown_c')] == 50, args[cls._fields.index('unknown_c')]
		return args

	@classmethod
	def default(cls):
		return cls(
				total_mass_lb=205,
				user_edited=32780,
				wheel_circumference_mm=2096,
				sample_smoothing=10251,
				aero=0.4889250099658966,
				fric=11.310999870300293,
				unknown_6=0.0,
				unknown_7=0.0,
				wind_scaling_sqrt=1.1510859727859497,
				speed_id=0,
				cadence_id=0,
				hr_id=0,
				power_id=0,
				speed_type=0,
				cadence_type=0,
				hr_type=0,
				power_type=0,
				tilt_mult_10=-7,
				cal_mass_lb=205,
				rider_mass_lb=180,
				unknown_9=1803,
				ftp_per_kilo_ish=1,
				ftp_over_095=85,
				unknown_a=769,
				# ^^ SetProfileData
				power_smoothing_seconds=1,
				unknown_c=50,
				# ^^ SetProfileData2
				unknown_0=0x5c16,
				unknown_1=0x382b,
				null_1=0,
				null_2=0,
				null_3=0,
				unknown_3=0,
				unknown_2=0,
				unknown_4=0,
				unknown_5=0,
				unknown_8=1670644000,
				# ^^^ Complete unknowns
		)


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

IDENTITY = lambda x: x
TO_TIMES_TEN_SIGNED = lambda base: lambda x: to_unsigned(int(x * 10), base)
FROM_TIMES_TEN_SIGNED = lambda base: lambda x: to_signed(x, base) * 0.1
FROM_TIMES_TEN = lambda x: x * 0.1
TO_TIMES_TEN = lambda x: int(x * 10)

RIDE_DATA_FIELDS = [
	('elevation_feet', 16, lambda x: to_signed(swap_endian(x), 16), lambda x: swap_endian(to_unsigned(x, 16))),
	('cadence', 8, IDENTITY, IDENTITY),
	('heart_rate', 8, IDENTITY, IDENTITY),
	('temperature_farenheit', 8, lambda x: x - 100, lambda x: x + 100),
	('unknown_0', 9, lambda x: to_signed(x, 9), lambda x: to_unsigned(x, 9)),
	('tilt', 10, FROM_TIMES_TEN_SIGNED(10), TO_TIMES_TEN_SIGNED(10)),
	('speed_mph', 10, FROM_TIMES_TEN, TO_TIMES_TEN),
	('wind_tube_pressure_difference', 10, IDENTITY, IDENTITY),
	('power_watts', 11, IDENTITY, IDENTITY),
	('dfpm_power_watts', 11, IDENTITY, IDENTITY),
	('acceleration_maybe', 10, lambda x: to_signed(x, 10), lambda x: to_unsigned(x, 10)),
	('stopped_flag_maybe', 1, IDENTITY, IDENTITY),
	('unknown_3', 8, IDENTITY, IDENTITY), # if this is large, "drafting" becomes true
]
# unknown_0 seems to be highly correlated to altitude. It might be average or integrated tilt. It seems to affect the /first record/ of the ride in Isaac but not much else (small = high power, big = low power -- which supports it being some sort of tilt offset).
# acceleration_maybe seems negative when stopping, positive in general. My feeling is that it's forward acceleration. I can't get this to affect anything.
# Using 'set profile after the ride' seems to ignore both unknown_0 and acceleration_maybe. I guess they are internal values, but I can only guess what they might do.
assert sum(x[1] for x in RIDE_DATA_FIELDS) == 15 * 8
DECODE_FIFTEEN_BYTES = '{:08b}' * 15
ENCODE_FIFTEEN_BYTES = ''.join('{:0%sb}' % (fielddef[1],) for fielddef in RIDE_DATA_FIELDS)
class NewtonRideData(object):
	SHAPE = '15s'
	__slots__ = zip(*RIDE_DATA_FIELDS)[0]
	def __init__(self, *args):
		for name, value in zip(self.__slots__, args):
			setattr(self, name, value)

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

	def to_binary(self):
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

	def pressure_Pa(self, reference_pressure_Pa=101325, reference_temperature_kelvin=288.15):
		return reference_pressure_Pa * (1 - (0.0065 * self.elevation_metres) / reference_temperature_kelvin) ** (9.80665 * 0.0289644 / 8.31447 / 0.0065)

	@property
	def temperature_kelvin(self):
		return (self.temperature_farenheit + 459.67) * 5 / 9

	def density(self, reference_pressure_Pa=101325, reference_temperature_kelvin=288.15):
		# I say 0.8773 at 22.7778C/2516.7336m; they say 0.8768. Good enough...
		# Constants from Wikipedia.
		return self.pressure_Pa(reference_pressure_Pa, reference_temperature_kelvin) * 0.0289644 / 8.31447 / self.temperature_kelvin

	def wind_speed_kph(self, offset=621, multiplier=13.6355, reference_pressure_Pa=101325, reference_temperature_kelvin=288.15, wind_scaling_sqrt=1.0):
		# multiplier based on solving from CSV file
		if self.wind_tube_pressure_difference < offset:
			return 0.0
		return ((self.wind_tube_pressure_difference - offset) / self.density(reference_pressure_Pa, reference_temperature_kelvin) * multiplier) ** 0.5 * wind_scaling_sqrt

	def __repr__(self):
		return '{}({})'.format(self.__class__.__name__, ', '.join(repr(getattr(self, name)) for name in self.__slots__))

class NewtonRideDataPaused(StructType, namedtuple('NewtonRideDataPaused', 'tag newton_time unknown_3')):
	SHAPE = '<6s8sb'

	@staticmethod
	def _decode(tag, newton_time_raw, unknown_3):
		return (tag, NewtonTime.from_binary(newton_time_raw), unknown_3)

	def _encode(self):
		return (self.tag, self.newton_time.to_binary(), self.unknown_3)

RIDE_FIELDS = [
	('unknown_0', 'h', IDENTITY, IDENTITY, 17), # byte 0 -- 0x1100 observed
	('size', 'i', IDENTITY, IDENTITY, 0), # byte 2
	('total_mass_lb', 'f', IDENTITY, IDENTITY, 235), # byte 6, always integer?!, could be total mass
	('energy_kJ', 'f', IDENTITY, IDENTITY, 0), # byte 10
	('aero', 'f', IDENTITY, IDENTITY, 0.384), # byte 14
	('fric', 'f', IDENTITY, IDENTITY, 12.0), # byte 18
	('initial_elevation_feet', 'f', IDENTITY, IDENTITY, 0), # byte 22, always integer?!
	('elevation_gain_feet', 'f', IDENTITY, IDENTITY, 0), # byte 26, always integer?!
	('wheel_circumference_mm', 'f', IDENTITY, IDENTITY, 2136.0), # byte 30, always integer?!
	('unknown_1', 'h', IDENTITY, IDENTITY, 15), # byte 34, 0x0f00 and 0x0e00 and 0x0e00 observed; multiplying by 10 does nothing observable. TODO is this ftp per kilo ish?
	('unknown_2', 'h', IDENTITY, IDENTITY, 1), # byte 36, =1?
	('start_time', '8s', NewtonTime.from_binary, NewtonTime.to_binary, NewtonTime(0, 0, 0, 1, 1, 31, 2000)), # byte 38
	('pressure_Pa', 'i', IDENTITY, IDENTITY, 101325), # byte 46, appears to be pressure in Pa (observed range 100121-103175) # (setting, reported) = [(113175, 1113), (103175, 1014), (93175, 915), (203175, 1996), (1e9, 9825490), (2e9, 19650979), (-2e9, -19650979)]. Reported value in Isaac (hPa) is this divided by ~101.7761 or multiplied by 0.00982549. This isn't affected by truncating the ride at all. It /is/ affected by unknown_3; if I make unknown_3 -73 from 73, I get (-2e9, -19521083).
	('Cm', 'f', IDENTITY, IDENTITY, 1.0204), # byte 50
	# average_temperature_farenheit = Average of temperature records. Does not affect displayed temperature in Isaac. It affects displayed pressure in Isaac (bigger temp = closer to pressure_Pa).
	# pressure_Pa = 103175
	# average_temperature_farenheit = 1, pressure = 1011mbar
	# average_temperature_farenheit = 100, pressure = 1015mbar
	# average_temperature_farenheit = 10000, pressure = 1031mbar
	# pressure_Pa = 1e9
	# average_temperature_farenheit = 1, pressure = 9798543mbar
	# average_temperature_farenheit = 100, pressure = 9833825mbar
	# average_temperature_farenheit = 10000, pressure = 9991024mbar
	('average_temperature_farenheit', 'h', IDENTITY, IDENTITY, 73), # byte 54.
	('wind_scaling_sqrt', 'f', IDENTITY, IDENTITY, 1.0), # byte 56
	('riding_tilt_times_10', 'h', IDENTITY, IDENTITY, 0.0), # byte 60
	('cal_mass_lb', 'h', IDENTITY, IDENTITY, 235), # byte 62
	('unknown_5', 'h', IDENTITY, IDENTITY, 88), # byte 64, 0x5800 and 0x6000 and 0x5c00 observed; multiplying by 10 doesn't affect: wind speed, pressure, temperature.
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
class NewtonRide(StructListType, namedtuple('NewtonRide', zip(*RIDE_FIELDS)[0] + ('records',))):
	SHAPE = '<' + ''.join(zip(*RIDE_FIELDS)[1])
	RECORD_TYPE = NewtonRideData

	@classmethod
	def make(cls, data, **kwargs):
		kwargs = {}
		assert 'size' not in kwargs
		assert 'records' not in kwargs
		for name in cls._fields[:-1]:
			kwargs[name] = RIDE_DEFAULTS[name]

		kwargs['records'] = data
		kwargs['size'] = len(data)
		if data:
			# TODO start_time, elevation gain
			kwargs['average_temperature_farenheit'] = int(round(sum(x.temperature_farenheit for x in data if hasattr(x, 'temperature_farenheit')) / len(data)))
			kwargs['initial_elevation_feet'] = [x.elevation_feet for x in data if hasattr(x, 'elevation_feet')][0]
			kwargs['data_records'] = len(data)
			kwargs['energy_kJ'] = int(round(sum(x.power_watts for x in data if hasattr(x, 'power_watts')) / 1000))

		args = []
		for name in cls._fields:
			args.append(kwargs[name])
		return cls(*args)

	def _encode(self):
		return tuple(encode(val) for val, encode in zip(self[:-1], RIDE_ENCODE))

	@staticmethod
	def _decode(*args):
		return tuple(decode(val) for val, decode in zip(args, RIDE_DECODE))

	def get_header(self):
		return NewtonRideHeader(self.unknown_0, self.start_time, sum(x.speed_mph * 1602 / 3600. for x in self.records if isinstance(x, NewtonRideData)))

	def fit_to(self, csv):
		pure_records = [x for x in self.records if not hasattr(x, 'newton_time')]
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
		pure_records = [x for x in self.records if not hasattr(x, 'newton_time')]
		csv_data = [float(x['Elevation (meters)']) / 0.3048 for x in csv.data]
		compare = [(x, y) for x, y in zip(pure_records, csv_data)]
		get_errors = lambda mul: [(pure_record.density(), pure_record.elevation_feet, csv_datum, pure_record.elevation_feet - csv_datum, (pure_record.wind_tube_pressure_difference - self.wind_tube_pressure_offset), pure_record.tilt, pure_record.unknown_0, pure_record) for pure_record, csv_datum in compare]
		return get_errors(0.1)

class NewtonRideHeader(StructType, namedtuple('NewtonRideHeader', 'unknown_0 start_time distance_metres')):
	# \x11\x00
	# newton time
	# float encoding of ride length in metres.
	SHAPE = '<h8sf'
	SIZE = 14

	def _encode(self):
		return (self.unknown_0, self.start_time.to_binary(), self.distance_metres)

	@classmethod
	def _decode(cls, unknown_0, start_time_raw, distance_metres):
		return (unknown_0, NewtonTime.from_binary(start_time_raw), distance_metres)
