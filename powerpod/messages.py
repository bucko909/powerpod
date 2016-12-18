from collections import namedtuple
import struct

from .types import StructType, StructListType, NewtonTime, NewtonRideHeader, NewtonRide, NewtonProfile

class NewtonCommand(object):
	MAP = {}

	def get_response(self, simulator):
		return self.RESPONSE.from_simulator(self, simulator).to_binary()

def add_command(cls):
	NewtonCommand.MAP[cls.IDENTIFIER] = cls
	return cls

class StructCommand(NewtonCommand, StructType):
	@classmethod
	def from_binary(cls, data):
		assert struct.unpack('b', data[0])[0] == self.IDENTIFIER
		return super(StructCommand, self).from_binary(data[1:])

	@classmethod
	def parse(cls, data):
		# TODO sort out this mess
		return super(StructCommand, cls).from_binary(data)

	def to_binary(self):
		return struct.pack('b', self.IDENTIFIER) + super(StructCommand, self).to_binary()



@add_command
class SetTimeCommand(NewtonCommand, namedtuple('SetTimeCommand', 'unknown newton_time')):
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



class GetProfileDataResponse(StructType, namedtuple('GetProfileDataResponse', 'profiles')):
	LENGTH = 4
	# TODO is this int32 length or int16 length and something else?
	SHAPE = '<i' + str(LENGTH * NewtonProfile.SIZE) + 's'

	@classmethod
	def from_simulator(cls, _command, simulator):
		assert len(simulator.profiles) == cls.LENGTH
		return cls(simulator.profiles)

	@classmethod
	def _decode(cls, length, data):
		assert length == cls.LENGTH
		assert len(data) == NewtonProfile.SIZE * length
		return [
				NewtonProfile.from_binary(data[x * NewtonProfile.SIZE:(x + 1) * NewtonProfile.SIZE])
				for x in range(length)
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
