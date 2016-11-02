import connection
import logging
import argparse

LOGGER = logging.getLogger(__name__)

def arg_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument('--port')
	return parser

def main():
	logging.basicConfig(level=logging.DEBUG)
	args = arg_parser().parse_args()
	kwargs = {}
	serial_connection = connection.NewtonSerialConnection(port=args.port)
	protocol = connection.NewtonSerialProtocol(serial_connection, device_side=False)
	data = connection.GetFileListCommand().get_binary()
	print repr(data)
	protocol.write_message(data)
	headers = connection.GetFileListCommand.RESPONSE.parse(protocol.read_message()).headers
	for i, header in enumerate(headers):
		print i, header
		protocol.write_message(connection.GetFileCommand(i).get_binary())
		print connection.GetFileCommand.RESPONSE.parse(protocol.read_message())

if __name__ == '__main__':
	main()
