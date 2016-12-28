import argparse
import logging
import os
import os.path
import time

import powerpod

LOGGER = logging.getLogger(__name__)

def arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--port')
	return parser

def main():
	logging.basicConfig(level=logging.INFO)
	args = arg_parser().parse_args()
	kwargs = {}
	serial_connection = powerpod.NewtonSerialConnection(port=args.port)
	protocol = powerpod.NewtonSerialProtocol(serial_connection, device_side=False)
	response = protocol.do_command(powerpod.GetFileListCommand())
	LOGGER.debug(repr(response))
	for i, header in enumerate(response.records):
		filename = "powerpod.%s-%0.1fkm.raw" % (header.start_time.as_datetime().strftime("%Y-%m-%dT%H-%M-%S"), header.distance_metres / 1000)
		LOGGER.info("index=%s header=%s filename=%s", i, header, filename)
		time.sleep(1)
		response = protocol.do_command(powerpod.GetFileCommand(i))
		open(os.path.join('rides', filename), 'w').write(response.ride_data.to_binary())

if __name__ == '__main__':
	main()
