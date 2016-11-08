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
	data = powerpod.GetFileListCommand().get_binary()
	print repr(data)
	protocol.write_message(data)
	response = powerpod.GetFileListCommand.RESPONSE.parse(protocol.read_message())
	print response
	headers = response.headers
	for i, header in enumerate(headers):
		filename = "powerpod.%s-%0.1fkm.raw" % (header.start_time.as_datetime().strftime("%Y-%m-%dT%H-%M-%S"), header.distance_metres / 1000)
		print i, header, filename
		time.sleep(1)
		protocol.write_message(powerpod.GetFileCommand(i).get_binary())
		response_raw = protocol.read_message()
		response = powerpod.GetFileCommand.RESPONSE.parse(response_raw).ride_data
		assert response.get_binary() == response_raw, map(repr, [response_raw[:100], response.get_binary()[:100]])
		open(os.path.join('rides', filename), 'w').write(response.get_binary())

if __name__ == '__main__':
	main()
