import collections
import sys
import urllib2
import simplejson
import datetime

import powerpod

def get_strava_filled(ride):
	filled_data = []
	i = 0
	for data in ride:
		if data['time'] != i:
			for i in range(data['time'] - i):
				filled_data.append(None)
			i = data['time']
		filled_data.append(data)
		i += 1
	return filled_data

def get_newton_filled(ride):
	filled_data = []
	expect = ride.start_time.as_datetime()
	for data in ride.data:
		if hasattr(data, 'newton_time'):
			extra_seconds = int((data.newton_time.as_datetime() - expect).total_seconds())
			for i in range(extra_seconds):
				filled_data.append(None)
			expect = data.newton_time.as_datetime()
			continue
		filled_data.append(data)
		expect += datetime.timedelta(seconds=1)
	return filled_data

def covariance(xs, ys):
	zipped = zip(xs, ys)
	xsum = ysum = x2sum = y2sum = xysum = 0
	count = 0.0
	for x, y in zipped:
		if x is None or y is None:
			continue
		count += 1
		xsum += x
		ysum += y
		x2sum += x * x
		y2sum += y * y
		xysum += x * y
	xmean = xsum / count
	ymean = ysum / count
	xdev = (x2sum / count - xsum * xsum / count / count) ** 0.5
	ydev = (y2sum / count - ysum * ysum / count / count) ** 0.5
	if xdev == 0 or ydev == 0:
		return 0.0
	return ((xysum - xmean * ysum - ymean * xsum) / count + xmean * ymean) / xdev / ydev

def correlate(newton_chunk, strava_chunk):
	streams = []
	if 'heartrate' in strava_chunk[0]:
		streams.append((
				[x.heart_rate if x else None for x in newton_chunk],
				[x['heartrate'] if x else None for x in strava_chunk]
			))
	if 'cadence' in strava_chunk[0]:
		streams.append((
				[x.cadence if x else None for x in newton_chunk],
				[x['cadence'] if x else None for x in strava_chunk]
			))
	if 'velocity_smooth' in strava_chunk[0]:
		streams.append((
				[x.speed_mph if x else None for x in newton_chunk],
				[x['velocity_smooth'] if x else None for x in strava_chunk]
			))
	best_cov = [float('-inf')]
	best = 0
	window = min(len(newton_chunk) - 2, len(strava_chunk) - 2, 60)
	for offset in range(-window, window + 1):
		newton_offset = max(offset, 0)
		strava_offset = max(-offset, 0)
		cov = [covariance(stream[0][newton_offset:], stream[1][strava_offset:]) for stream in streams]
		if sum(cov) > sum(best_cov):
			best_cov = cov
			best = offset
	newton_offset = max(best, 0)
	strava_offset = max(-best, 0)
	return newton_offset, strava_offset, min(len(newton_chunk) - newton_offset, len(strava_chunk) - strava_offset), best_cov

newton_ride = powerpod.NewtonRide.from_binary(open(sys.argv[1], 'r').read())
url = 'https://www.strava.com/api/v3/activities/%s/streams/time,distance,cadence,heartrate,velocity_smooth?access_token=%s' % (sys.argv[2], open('/home/bucko/.strava-token', 'r').read()[:-1])
strava_ride = simplejson.load(urllib2.urlopen(url))
strava_names = [x['type'] for x in strava_ride]
strava_points = [dict(zip(strava_names, x)) for x in zip(*(x['data'] for x in strava_ride))]

strava_filled = get_strava_filled(strava_points)
newton_filled = get_newton_filled(newton_ride)

print >>sys.stderr, "correlating..."
newton_start, strava_start, length, error = correlate(newton_filled, strava_filled)
print >>sys.stderr, "correlate", newton_start, strava_start, length, error

records = {
		'newton_heartrate': lambda record, _ride: record.heart_rate,
		'newton_cadence': lambda record, _ride: record.cadence,
		'newton_ground_velocity': lambda record, _ride: round(record.speed_mph * 1.602, 2),
		'newton_air_velocity': lambda record, ride: round(record.wind_speed_kph(offset=ride.wind_tube_pressure_offset - 10, reference_pressure_Pa=ride.reference_pressure_Pa, reference_temperature_kelvin=ride.reference_temperature_kelvin, wind_scaling_sqrt=ride.wind_scaling_sqrt), 2),
		'newton_slope': lambda record, _ride: round(record.tilt, 1),
		'newton_temp': lambda record, _ride: round(record.temperature_kelvin - 273.15, 2),
		'newton_elevation': lambda record, _ride: round(record.elevation_metres, 2),
		'newton_power': lambda record, _ride: record.power_watts,
		'newton_thingy': lambda record, _ride: record.unknown_0,
		'newton_acceleration': lambda record, _ride: record.acceleration_maybe / 10.0,
		'elev_corr': lambda record, _ride: record.elevation_metres + record.unknown_0 / .3048,
}

def integrate_slope(record, _ride):
	if not hasattr(integrate_slope, 'buf'):
		integrate_slope.buf = collections.deque()
		integrate_slope.buf_len = 0.0
		integrate_slope.buf_int = 0.0
	integrate_slope.buf.append(record)
	integrate_slope.buf_len += record.speed_mph * 1602 / 3600.0
	integrate_slope.buf_int += record.speed_mph * 1602 * (record.tilt + 0.1) * 0.01 / 3600.0
	while integrate_slope.buf_len > 3000 and False:
		old = integrate_slope.buf.popleft()
		integrate_slope.buf_len -= old.speed_mph * 1602 / 3600.0
		integrate_slope.buf_int -= old.speed_mph * 1602 * old.tilt / 3600.0
	if integrate_slope.buf_len > 2900:
		return integrate_slope.buf_int #/ integrate_slope.buf_len
	else:
		return None
records['slope_average'] = integrate_slope

data = {name: {'type': name, 'resolution': 'high', 'original_size': len(strava_points), 'series_type': 'distance', 'data': []} for name in records.keys()}
data['time'] = strava_ride[strava_names.index('time')]
# Lead in with nulls
for i in range(strava_start):
	if strava_filled[i] is None:
		continue
	for name, _make in records.items():
		data[name]['data'].append(None)
# Fill in the newton records
for i in range(length):
	if strava_filled[strava_start + i] is None:
		continue
	for name, make in records.items():
		if newton_filled[i + newton_start] is None:
			data[name]['data'].append(None)
		else:
			data[name]['data'].append(make(newton_filled[i + newton_start], newton_ride))
# Lead out with nulls
for i in range(len(strava_filled) - strava_start - length):
	if strava_filled[strava_start + length + i] is None:
		continue
	for name, _make in records.items():
		data[name]['data'].append(None)
print simplejson.dumps(data.values(), separators=(',', ':'))
