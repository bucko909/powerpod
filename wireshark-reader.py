# pcap the USB, and filter it to just your device.
# Now do <pcapfile tshark --disable-protocol ppp --disable-protocol prp -Y 'usb.data_flag == "present (0)" && usb.transfer_type == 0x03' -e frame.time_epoch -e usb.endpoint_number.direction -e usb.capdata -Tfields -r - | python -u wireshark-reader.py 2>&1 | less
# Now hope we understand everything! HA HA HA!

import argparse
from collections import deque
import ipdb
import logging
import sys

import powerpod

LOGGER = logging.getLogger(__name__)

class LogReader(object):
	def __init__(self, stream):
		self.stream = stream
		self.queue = deque()

	def parse(self):
		for line in self.stream:
			line = line.strip('\n')
			timestamp_str, direction_str, data_str = line.split('\t')
			if data_str == '':
				continue
			timestamp = float(timestamp_str)
			to_device = direction_str == '0'
			# Data comes out in colon-sep hex form
			data = ''.join(chr(int(x, 16)) for x in data_str.split(':'))
			self.queue.append((timestamp, to_device, data))
			print timestamp, to_device, repr(data)

	def device_read(self):
		if self.queue[0][1]:
			raise Exception("Reading from device when next message was to it %r" % (self.queue[0],))
		return self.queue.popleft()[2]

	def host_read(self):
		if not self.queue[0][1]:
			raise Exception("Reading from host when next message was to it %r" % (self.queue[0],))
		return self.queue.popleft()[2]

class FakeReader(object):
	def __init__(self, more):
		self.more = more
		self.read_buf = ''

	def read(self, amount):
		retval = ''
		while amount > 0:
			if self.read_buf:
				this_amount = min(amount, len(self.read_buf))
				amount -= this_amount
				retval += self.read_buf[:this_amount]
				self.read_buf = self.read_buf[this_amount:]
			else:
				self.read_buf = self.more()
		return retval

class FakeConnection(object):
	def __init__(self, reader, writer):
		self._reader = reader
		self._writer = writer

	def read(self, length):
		assert self._writer.read_buf == '', self._writer.read_buf
		return self._reader.read(length)

	def write(self, data):
		assert self._reader.read_buf == '', self._reader.read_buf
		found = self._writer.read(len(data))
		assert found == data, (found, data)
		return len(data)

def main():
	logging.basicConfig(level=logging.DEBUG)
	reader = LogReader(sys.stdin)
	reader.parse()
	host_reader = FakeReader(reader.host_read)
	device_reader = FakeReader(reader.device_read)
	host_protocol = powerpod.NewtonSerialProtocol(FakeConnection(host_reader, device_reader), device_side=True)
	device_protocol = powerpod.NewtonSerialProtocol(FakeConnection(device_reader, host_reader), device_side=False)
	while reader.queue:
		try:
			command = host_protocol.read_message()
			print "->", repr(command)
			# TODO
			# After a \x07 (erase all), the device responds '\x00' twice. Once is command ack, twice I guess means "yep, done!"
			# After a \x1a (set profile) and \x1e ("post set profile") and \x1d (set profile number), the device has no response at all.
			# Interrupts are also really common when executing set profile.
			if command[0] != '\x04':
				response = device_protocol.read_message()
				print "<-", repr(response)
		except:
			import traceback
			traceback.print_exc()
			while reader.queue[0][1:] != (True, '\x80'):
				print "Dropping", reader.queue.popleft()
			host_reader.read_buf = ''
			device_reader.read_buf = ''

if __name__ == '__main__':
	main()
