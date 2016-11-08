import re

CSV_FIELD = re.compile(r'(?:^|(?<=,))(?:[^,"]*|"(?:[^"\\]|\\.)*")(?:(?=,)|$)')
CSV_FIELDS = lambda line: [x[1:-1] if len(x) > 2 and x[0] == '"' else x for x in CSV_FIELD.findall(line[:-1])]
class IsaacCSV(object):
	def __init__(self, header, data):
		self.header = header
		self.data = data

	@classmethod
	def from_filename(cls, filename):
		fd = open(filename, 'r')
		_blah = fd.readline() # boring header
		_blah = fd.readline() # date
		header_fields = CSV_FIELDS(fd.readline())
		if header_fields[0:1] == ['', '<-Weight (kg) Energy (kJ)']:
			header_fields[0:1] = ['Weight (kg)', 'Energy (kJ)']
		header_data = CSV_FIELDS(fd.readline())
		header = dict(zip(header_fields, header_data))
		ride_fields = CSV_FIELDS(fd.readline())
		data = []
		for line in fd:
			data.append(dict(zip(ride_fields, CSV_FIELDS(line))))
		return cls(header, data)

