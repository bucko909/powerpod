from collections import namedtuple
import struct

from .types import StructType, StructListType, NewtonTime, NewtonRideHeader, NewtonRide, NewtonProfile

class NewtonCommand(object):
	MAP = {}

	def get_response(self, simulator):
		if self.RESPONSE is None:
			return None
		return self.RESPONSE.from_simulator(self, simulator)

def add_command(cls):
	NewtonCommand.MAP[cls.IDENTIFIER] = cls
	return cls

class StructCommandMixIn(object):
	@classmethod
	def from_binary(cls, data):
		assert struct.unpack('b', data[0])[0] == cls.IDENTIFIER
		return super(StructCommandMixIn, cls).from_binary(data[1:])

	@classmethod
	def parse(cls, data):
		# TODO sort out this mess
		return super(StructCommandMixIn, cls).from_binary(data)

	def to_binary(self):
		return struct.pack('b', self.IDENTIFIER) + super(StructCommandMixIn, self).to_binary()

class StructCommand(StructCommandMixIn, NewtonCommand, StructType):
	pass

class StructListCommand(StructCommandMixIn, NewtonCommand, StructListType):
	pass


@add_command
class SetTimeCommand(StructCommand, namedtuple('SetTimeCommand', 'unknown newton_time')):
	# Is the unknown1 optional? I've seen this sent without it...
	IDENTIFIER = 0x04
	SHAPE = '<b8s'
	RESPONSE = None

	@classmethod
	def _decode(cls, unknown, newton_time):
		return (unknown, NewtonTime.from_binary(newton_time))

	def _encode(self):
		return (self.unknown, self.newton_time.to_binary())



class GetSpaceUsageResponse(StructType, namedtuple('GetSpaceUsageResponse', 'used_percentage')):
	SHAPE = '<h'

	@classmethod
	def from_simulator(cls, _command, simulator):
		# Hope you like having no free space!
		return cls(199)

@add_command
class GetSpaceUsageCommand(StructCommand, namedtuple('GetSpaceUsageCommand', '')):
	IDENTIFIER = 0x08
	SHAPE = ''
	RESPONSE = GetSpaceUsageResponse



class GetSerialNumberResponse(StructType, namedtuple('GetSerialNumberResponse', 'serial_number')):
	SHAPE = '16s'

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls(''.join(chr(int(x, 16)) for x in simulator.serial_number.split('-')))

	@property
	def as_hex(self):
		return '-'.join('{:02X}'.format(ord(x)) for x in self.serial_number)

@add_command
class GetSerialNumberCommand(StructCommand, namedtuple('GetSerialNumberCommand', '')):
	IDENTIFIER = 0x09
	SHAPE = ''
	RESPONSE = GetSerialNumberResponse



class GetFirmwareVersionResponse(StructType, namedtuple('GetFirmwareVersionResponse', 'version_encoded')):
	SHAPE = '<h'

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls.from_version(simulator.firmware_version)

	@classmethod
	def from_version(cls, version_number):
		return cls(cls.encode_version(version_number))

	@staticmethod
	def encode_version(version_number):
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
		return int(version_number * 100 + 500)

	@property
	def version(self):
		if self.version_encoded > 0x0200:
			return self.version_encoded / 100.0 - 5
		else:
			return self.version_encoded / 100.0

@add_command
class GetFirmwareVersionCommand(StructCommand, namedtuple('GetFirmwareVersionCommand', '')):
	IDENTIFIER = 0x0e
	SHAPE = ''
	RESPONSE = GetFirmwareVersionResponse



class GetProfileNumberResponse(StructType, namedtuple('GetProfileNumberResponse', 'number')):
	SHAPE = '<h'

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls(simulator.current_profile)

@add_command
class GetProfileNumberCommand(StructCommand, namedtuple('GetProfileNumberCommand', '')):
	IDENTIFIER = 0x1c
	SHAPE = ''
	RESPONSE = GetProfileNumberResponse



class GetProfileDataResponse(StructType, namedtuple('GetProfileDataResponse', 'size profiles')):
	LENGTH = 4
	# TODO is this int32 length or int16 length and something else?
	SHAPE = '<i' + str(LENGTH * NewtonProfile.SIZE) + 's'

	@classmethod
	def from_simulator(cls, _command, simulator):
		assert len(simulator.profiles) == cls.LENGTH
		return cls(len(simulator.profiles) * NewtonProfile.SIZE, simulator.profiles)

	@classmethod
	def _decode(cls, length, data):
		assert length == cls.LENGTH * NewtonProfile.SIZE, (length, data)
		assert length == len(data), (length, len(data), data)
		return length, [
				NewtonProfile.from_binary(data[x * NewtonProfile.SIZE:(x + 1) * NewtonProfile.SIZE])
				for x in range(cls.LENGTH)
		]

	def _encode(self):
		return (len(self.profiles) * NewtonProfile.SIZE, ''.join(profile.to_binary() for profile in self.profiles))

@add_command
class GetProfileDataCommand(StructCommand, namedtuple('GetProfileDataCommand', '')):
	IDENTIFIER = 0x1f
	SHAPE = ''
	RESPONSE = GetProfileDataResponse



class GetFileResponse(namedtuple('GetFileResponse', 'ride_data')):
	@classmethod
	def parse(cls, data):
		return cls(NewtonRide.from_binary(data))

	@classmethod
	def from_binary(cls, data):
		return cls(NewtonRide.from_binary(data))

	def to_binary(self):
		return self.ride_data.to_binary()

	@classmethod
	def from_simulator(cls, command, simulator):
		return cls(simulator.rides[command.ride_number])

@add_command
class GetFileCommand(StructCommand, namedtuple('GetFileCommand', 'ride_number')):
	IDENTIFIER = 0x20
	SHAPE = '<h'
	RESPONSE = GetFileResponse



class GetFileListResponse(StructListType, namedtuple('GetFileListResponse', 'size records')):
	SHAPE = '<h'
	RECORD_TYPE = NewtonRideHeader

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls(len(simulator.rides), [ride.get_header() for ride in simulator.rides])

@add_command
class GetFileListCommand(StructCommand, namedtuple('GetFileListCommand', '')):
	IDENTIFIER = 0x21
	SHAPE = ''
	RESPONSE = GetFileListResponse



class UnknownCommandResponse(StructType, namedtuple('UnknownCommandResponse', 'unknown_0 unknown_1')):
	SHAPE = '<hh'

	@classmethod
	def from_simulator(cls, _command, _simulator):
		return cls(2, 0)

@add_command
class UnknownCommand(StructCommand, namedtuple('UnknownCommand', '')):
	"""
	This is sent before GetSpaceUsageCommand...
	"""
	IDENTIFIER = 0x22
	SHAPE = ''
	RESPONSE = UnknownCommandResponse



@add_command
class UploadFirmwareCommand(StructCommand, namedtuple('UploadFirmwareCommand', '')):
	# Is followed by /lots/ of (length 37) data which violates checksum.
	# I don't really want to work out how to decode this.
	IDENTIFIER = 0x01
	SHAPE = ''
	RESPONSE = None



class EraseAllResponse(object):
	@staticmethod
	def from_simulator(command, simulator):
		simulator.rides[:] = []
		return None

@add_command
class EraseAllCommand(StructCommand, namedtuple('EraseAllCommand', '')):
	IDENTIFIER = 0x07
	SHAPE = ''
	RESPONSE = EraseAllResponse



@add_command
class SetUnitsCommand(StructCommand, namedtuple('SetUnitsCommand', 'units_type')):
	IDENTIFIER = 0x0a
	SHAPE = '<h'
	RESPONSE = None

	METRIC = 1
	ENGLISH = 0



class SetOdometerResponse(object):
	@staticmethod
	def from_simulator(command, simulator):
		simulator.odometer_distance = command.distance_km

@add_command
class SetOdometerCommand(StructCommand, namedtuple('SetOdometerCommand', 'distance_km')):
	# Unsure of units
	IDENTIFIER = 0x0b
	SHAPE = '<i'
	RESPONSE = SetOdometerResponse

	def _encode(self):
		return (int(round(self.distance_km * 10)),)

	@classmethod
	def _decode(cls, distance):
		return (distance * 0.1,)



@add_command
class SetSampleRateCommand(StructCommand, namedtuple('SetSampleRateCommand', 'unknown sample_rate')):
	IDENTIFIER = 0x0c
	SHAPE = '<hh'
	RESPONSE = None

	SAMPLE_RATE_1_SECOND = 0
	SAMPLE_RATE_5_SECONDS = 1

	@staticmethod
	def _decode(unknown, sample_rate):
		# No idea what this is, but always seems to be 0
		assert unknown == 0
		return (unknown, sample_rate)



class GetOdometerResponse(StructType, namedtuple('GetOdometerResponse', 'unknown_0 unknown_1 unknown_2 distance_km')):
	# TODO unknowns are observed at 1, 1, 0
	SHAPE = '<hhhi'

	def _encode(self):
		return (self.unknown_0, self.unknown_1, self.unknown_2, int(round(self.distance_km * 10)),)

	@classmethod
	def _decode(cls, unknown_0, unknown_1, unknown_2, distance):
		assert unknown_0 == 1
		assert unknown_1 == 1
		assert unknown_2 == 0
		return (unknown_0, unknown_1, unknown_2, distance * 0.1,)

	@classmethod
	def from_simulator(cls, _command, simulator):
		return cls(1, 1, 0, simulator.odometer_distance)

@add_command
class GetOdometerCommand(StructCommand, namedtuple('GetOdometerCommand', '')):
	IDENTIFIER = 0x0d
	SHAPE = ''
	RESPONSE = GetOdometerResponse



@add_command
class SetTrainerWeightsCommand(StructCommand, namedtuple('SetTrainerWeightsCommand', 'constant linear quadratic cubic')):
	""" All coefficients are in terms of a polynomial in mph, outputting Watts. """
	IDENTIFIER = 0x14
	SHAPE = '<ffff'
	RESPONSE = None



class NewtonInterval(StructType, namedtuple('NewtonInterval', 'power_watts work_secs rest_secs')):
	SHAPE = '<hhh'

@add_command
class SetIntervalsCommand(StructListCommand, namedtuple('SetIntervalsCommand', 'size size_byte records')):
	# Dunno what size_byte re
	IDENTIFIER = 0x19
	SHAPE = '<hb'
	RECORD_TYPE = NewtonInterval
	RESPONSE = None

	@classmethod
	def parse(cls, data):
		# TODO sort out this mess
		return super(SetIntervalsCommand, cls).from_binary(data)

	@staticmethod
	def _decode(size, size_byte):
		assert size == size_byte
		return size, size_byte



SET_PROFILE_FIELDS = [
		('total_mass_lb', 'h'),
		('user_edited', 'H'),
		('wheel_circumference_mm', 'h'),
		('sample_smoothing', 'H'),
		('aero', 'f'),
		('fric', 'f'),
		('unknown_6', 'f'), # Verified equal to Profile. Values include -38.0
		('unknown_7', 'f'), # Verified equal to Profile. Values include 1.0
		('wind_scaling_sqrt', 'f'),
		('speed_id', 'H'),
		('cadence_id', 'H'),
		('hr_id', 'H'),
		('power_id', 'H'),
		# Distressingly, the 'type' fields are 'B' in the actual profile.
		('speed_type', 'H'),
		('cadence_type', 'H'),
		('hr_type', 'H'),
		('power_type', 'H'),
		('tilt_cal', 'h'),
		('cal_mass_lb', 'h'),
		('rider_mass_lb', 'h'),
		('unknown_9', 'h'), # Verified equal to Profile. Values include 1850
		('ftp_per_kilo_ish', 'h'),
		('ftp_over_095', 'h'),
		('unknown_a', 'h'), # Verified equal to Profile.
]
class SetProfileDataResponse(object):
	@staticmethod
	def from_simulator(command, simulator):
		old = simulator.profiles[simulator.current_profile]
		new = old._replace(**{key: getattr(command, key) for key in command._fields if hasattr(old, key)})
		simulator.profiles[simulator.current_profile] = new
		return None

@add_command
class SetProfileDataCommand(StructCommand, namedtuple('SetProfileDataCommand', zip(*SET_PROFILE_FIELDS)[0])):
	IDENTIFIER = 0x1a
	SHAPE = '<' + ''.join(zip(*SET_PROFILE_FIELDS)[1])
	RESPONSE = SetProfileDataResponse

	@classmethod
	def _decode(cls, *args):
		args = list(args)
		args[cls._fields.index('tilt_cal')] = args[cls._fields.index('tilt_cal')] * 0.1
		return args

	def _encode(self):
		return self._replace(tilt_cal=int(round(self.tilt_cal * 10)))



class SetProfileNumberResponse(object):
	@staticmethod
	def from_simulator(command, simulator):
		simulator.current_profile = command.number
		return None

@add_command
class SetProfileNumberCommand(StructCommand, namedtuple('SetProfileNumberCommand', 'number')):
	IDENTIFIER = 0x1d
	SHAPE = '<h'
	RESPONSE = SetProfileNumberResponse


SET_PROFILE2_FIELDS = [
		('power_smoothing_seconds', 'H'),
		('unknown_a', 'h'), # Verified equal to Profile.
]
class SetProfileData2Response(object):
	@staticmethod
	def from_simulator(command, simulator):
		old = simulator.profiles[simulator.current_profile]
		new = old._replace(**{key: getattr(command, key) for key in command._fields if hasattr(old, key)})
		simulator.profiles[simulator.current_profile] = new
		return None

@add_command
class SetProfileData2Command(StructCommand, namedtuple('SetProfileData2Command', 'power_smoothing_seconds unknown_c')):
	IDENTIFIER = 0x1e
	SHAPE = '<hh'
	RESPONSE = SetProfileData2Response



SCREEN_FIELDS = [
		"s{}{}{}".format(screen, pos, field)
		for screen in (1, 2)
		for field in ('agg', 'dat', 'unk')
		for pos in ('t', 'm', 'b')
]
@add_command
class SetScreensCommand(StructCommand, namedtuple('SetScreensCommand', SCREEN_FIELDS)):
	# TOP:
	# Speed:            ( 0,  2,  1)
	# Average Speed:    ( 2,  2,  1)
	# Wind:             (16, 18, 17)
	# Average Wind:     (18, 18, 17)
	# Slope:            (13, 15, 14)
	# Average Slope:    (15, 15, 14)
	# Power:            ( 7,  9,  8)
	# Average Power:    ( 9,  9,  8)
	# Blank:            (22, 20, 19)
	# MIDDLE:
	# Power:            ( 7,  9,  8)
	# Distance/Power:   ( 3,  5,  4)
	# Normalized Power: (21, 21, 21)
	# Wind:             (16, 18, 17) # Same as TOP
	# Blank:            (22, 20, 19) # Same as TOP
	# BOTTOM
	# Trip Time:        ( 6,  6,  6)
	# Other Data:       (10, 12, 11) # Same as Blank
	# Blank:            (10, 12, 11) # Not same as TOP/MIDDLE
	IDENTIFIER = 0x29
	SHAPE = 'b' * 18
	RESPONSE = None



class GetAllScreensResponse(StructType, namedtuple('GetAllScreensResponse', 'data')):
	SHAPE = '76s' # TODO

	@classmethod
	def from_simulator(cls, _command, _simulator):
		return cls('\x48\x00\x00\x00' + '\x00\x03\x06\x02\x05\x06\x01\x04\x06\x00\x07\n\x02\t\x0c\x01\x08\x0b' * 4)

@add_command
class GetAllScreensCommand(StructCommand, namedtuple('GetAllScreensCommand', '')):
	IDENTIFIER = 0x2a
	SHAPE = ''
	RESPONSE = GetAllScreensResponse
