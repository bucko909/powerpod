import argparse
import functools
import logging
import os
import os.path
import re
import sys
import time

import powerpod

LOGGER = logging.getLogger(__name__)

CMD_SPLIT = re.compile(r'(?:[^\\\s]|\\.)+')
WHITESPACE_QUOTE = functools.partial(re.compile(r'(\\s)').sub, r'\\\1')

ACTIONS = {}

def add_action(cls):
	ACTIONS[cls.PARSER.prog] = cls

class Action(object):
	PARSER = NotImplemented
	def __init__(self, extra):
		self.extra = extra

@add_action
class GetAllRidesAction(Action):
	PARSER = argparse.ArgumentParser('get_all_rides')
	def run(self, protocol, args):
		response = protocol.do_command(powerpod.GetFileListCommand())
		LOGGER.debug(repr(response))
		for i, header in enumerate(response.records):
			filename = "powerpod.%s-%0.1fkm.raw" % (header.start_time.as_datetime().strftime("%Y-%m-%dT%H-%M-%S"), header.distance_metres / 1000)
			filepath = os.path.join(args.ride_directory, filename)
			args.actions.append(make_action("get_ride {} --filename={}".format(i, WHITESPACE_QUOTE(filepath))))

@add_action
class GetRideAction(Action):
	PARSER = argparse.ArgumentParser('get_ride')
	PARSER.add_argument('index', type=int)
	PARSER.add_argument('--filename')
	def run(self, protocol, args):
		time.sleep(1)
		response = protocol.do_command(powerpod.GetFileCommand(self.extra.index))
		filename = self.extra.filename
		if filename is None:
			out = sys.stdout
		else:
			out = open(filename, 'w')
		LOGGER.info("index=%s header=%s filename=%s", self.extra.index, response.ride_data.get_header(), filename)
		out.write(response.ride_data.to_binary())

def make_action(string):
	parts = CMD_SPLIT.findall(string)
	if not parts:
		raise ValueError("Invalid command {}".format(string))
	if parts[0] not in ACTIONS:
		raise ValueError("Unknown command {}".format(string))
	action_class = ACTIONS[parts[0]]
	args = action_class.PARSER.parse_args(parts[1:])
	return action_class(args)

def arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--port', default='/dev/ttyUSB0')
	parser.add_argument(
			'--profile-number',
			dest='profile_number',
			choices=[0, 1, 2, 3],
			help="""
				Set profile for profile editing operations.
				Default is to use current profile; use of this option may
				temporarily switch to a different profile.
			""",
	)
	parser.add_argument(
			'--ride-output-directory',
			dest='ride_directory',
			default='./rides',
			help='For --get-all-rides',
	)
	parser.add_argument(
			'--profile-output-directory',
			dest='profile_directory',
			default='./profiles',
			help='For --get-all-profiles',
	)
	parser.add_argument(
			'--help-actions',
			#action=ActionsHelp,
	)
	parser.add_argument(
			'actions',
			nargs='+',
			type=make_action,
			help="""
				Actions to perform. See --help-actions for a list.
			""",
	)
	return parser

def main():
	logging.basicConfig(level=logging.INFO)
	args = arg_parser().parse_args()
	kwargs = {}
	serial_connection = powerpod.NewtonSerialConnection(port=args.port)
	protocol = powerpod.NewtonSerialProtocol(serial_connection, device_side=False)
	for action in args.actions:
		action.run(protocol, args)

if __name__ == '__main__':
	main()
