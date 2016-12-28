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

class StructCommand(NewtonCommand, StructType):
	@classmethod
	def from_binary(cls, data):
		assert struct.unpack('b', data[0])[0] == cls.IDENTIFIER
		return super(StructCommand, cls).from_binary(data[1:])

	@classmethod
	def parse(cls, data):
		# TODO sort out this mess
		return super(StructCommand, cls).from_binary(data)

	def to_binary(self):
		return struct.pack('b', self.IDENTIFIER) + super(StructCommand, self).to_binary()



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
	def from_simulator(cls, _command, _simulator):
		return cls(0)

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
		return cls(len(simulator.profiles), simulator.profiles)

	@classmethod
	def _decode(cls, length, data):
		assert length == cls.LENGTH * NewtonProfile.SIZE, (length, data)
		assert length == len(data), (length, len(data), data)
		return length, [
				NewtonProfile.from_binary(data[x * NewtonProfile.SIZE:(x + 1) * NewtonProfile.SIZE])
				for x in range(cls.LENGTH)
		]

	def _encode(self):
		return (len(self.profiles), ''.join(profile.to_binary() for profile in self.profiles))

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



@add_command
class SetOdometerCommand(StructCommand, namedtuple('SetOdometerCommand', 'odometer_distance')):
	# Unsure of units
	IDENTIFIER = 0x0b
	SHAPE = '<i'
	RESPONSE = None

	def _encode(self):
		return (int(round(self.odometer_distance * 10)),)

	@classmethod
	def _decode(cls, odometer_distance):
		return (odometer_distance * 0.1,)



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



class GetOdometerResponse(StructType, namedtuple('GetOdometerResponse', 'unknown_0 unknown_1 unknown_2 odometer_distance')):
	# TODO unknowns are observed at 1, 1, 0
	SHAPE = '<hhhi'

	def _encode(self):
		return (self.unknown_0, self.unknown_1, self.unknown_2, int(round(self.odometer_distance * 10)),)

	@classmethod
	def _decode(cls, unknown_0, unknown_1, unknown_2, odometer_distance):
		assert unknown_0 == 1
		assert unknown_1 == 1
		assert unknown_2 == 0
		return (unknown_0, unknown_1, unknown_2, odometer_distance * 0.1,)

@add_command
class GetOdometerCommand(StructCommand, namedtuple('GetOdometerCommand', '')):
	IDENTIFIER = 0x0d
	SHAPE = ''
	RESPONSE = GetOdometerResponse



@add_command
class SetTrainerWeightsCommand(StructCommand, namedtuple('SetTrainerWeightsCommand', 'data')):
	IDENTIFIER = 0x14
	SHAPE = '16s' # TODO
	RESPONSE = None



class NewtonInterval(object):
	pass # TODO

@add_command
class SetIntervalsCommand(StructCommand, namedtuple('SetIntervalsCommand', 'size records')):
	IDENTIFIER = 0x19
	SHAPE = '<h'
	RECORD_TYPE = NewtonInterval
	RESPONSE = None



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
		('tilt_mult_10', 'h'),
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



class SetProfileNumberResponse(object):
	@staticmethod
	def from_simulator(command, simulator):
		simulator.current_profile = command.profile_number
		return None

@add_command
class SetProfileNumberCommand(StructCommand, namedtuple('SetProfileNumberCommand', 'profile_number')):
	IDENTIFIER = 0x1d
	SHAPE = '<h'
	RESPONSE = None


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
class SetProfileData2Command(StructCommand, namedtuple('PostSetProfileDataCommand', 'power_smoothing_seconds unknown_c')):
	IDENTIFIER = 0x1e
	SHAPE = '<hh'
	RESPONSE = SetProfileData2Response



@add_command
class SetScreensCommand(StructCommand, namedtuple('SetScreensCommand', 'data')):
	IDENTIFIER = 0x29
	SHAPE = '18s' # TODO
	RESPONSE = None



class GetAllScreensResponse(StructType, namedtuple('GetAllScreensResponse', '')):
	pass # TODO

@add_command
class GetAllScreensCommand(StructCommand, namedtuple('GetAllScreensCommand', '')):
	IDENTIFIER = 0x2a
	SHAPE = ''
	RESPONSE = GetAllScreensResponse
