import argparse
import logging
import os
import os.path
import re
import time

import powerpod

LOGGER = logging.getLogger(__name__)

class Action(object):
	pass

class GetAllRides(Action):
	def run(self, protocol, args):
		response = protocol.do_command(powerpod.GetFileListCommand())
		LOGGER.debug(repr(response))
		for i, header in enumerate(response.records):
			filename = "powerpod.%s-%0.1fkm.raw" % (header.start_time.as_datetime().strftime("%Y-%m-%dT%H-%M-%S"), header.distance_metres / 1000)
			LOGGER.info("index=%s header=%s filename=%s", i, header, filename)
			time.sleep(1)
			response = protocol.do_command(powerpod.GetFileCommand(i))
			filepath = os.path.join(args.ride_directory, filename)
			open(filepath, 'w').write(response.ride_data.to_binary())

def make_action(string):
	assert string == 'get_all_rides'
	return GetAllRides()

def arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--port', default='/dev/ttyUSB0')
	parser.add_argument(
			'--ride-output-directory',
			dest='ride_directory',
			default='./rides',
			help='For --get-all-rides',
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
