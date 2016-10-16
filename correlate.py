import connection
import sys
import urllib2
import simplejson
import datetime

newton_ride = connection.NewtonRide.from_binary(open(sys.argv[1], 'r').read())
url = 'https://www.strava.com/api/v3/activities/%s/streams/time,distance,cadence,heartrate,velocity_smooth?access_token=%s' % (sys.argv[2], open('/home/bucko/.strava-token', 'r').read()[:-1])
strava_ride = simplejson.load(urllib2.urlopen(url))
strava_names = [x['type'] for x in strava_ride]
strava_points = [dict(zip(strava_names, x)) for x in zip(*(x['data'] for x in strava_ride))]

def get_strava_chunks(ride):
	chunks = []
	chunk = []
	holes = []
	i = 0
	for data in ride:
		if data['time'] != i:
			holes.append(data['time'] - i)
			for i in range(holes[-1]):
				chunk.append(None)
			#chunks.append(chunk)
			#chunk = []
			print "skip", i, data['time'], data['time'] - i
			i = data['time']
		i += 1
		chunk.append(data)
	if chunk:
		chunks.append(chunk)
	return chunks, holes

def get_newton_chunks(ride):
	chunks = []
	chunk = []
	holes = []
	expect = ride.start_time.as_datetime()
	for data in ride.data:
		if hasattr(data, 'newton_time'):
			print "skip", expect, data.newton_time.as_datetime(), data.newton_time.as_datetime() - expect
			if not chunks and not chunk:
				expect = data.newton_time.as_datetime()
				continue
			if not chunk:
				continue
			holes.append((data.newton_time.as_datetime() - expect).total_seconds())
			for i in range(int(holes[-1])):
				chunk.append(None)
			expect = data.newton_time.as_datetime() #- datetime.timedelta(seconds=1)
			#chunks.append(chunk)
			#chunk = []
			continue
		expect += datetime.timedelta(seconds=1)
		chunk.append(data)
	if chunk:
		chunks.append(chunk)
	return chunks, holes

strava_chunks, strava_holes = get_strava_chunks(strava_points)
newton_chunks, newton_holes = get_newton_chunks(newton_ride)

strava_idx = newton_idx = 0

def covariance(xs, ys):
	zipped = zip(xs, ys)
	xsum = ysum = sum2 = xysum = 0
	count = 0.0
	for x, y in zipped:
		if x is None or y is None:
			continue
		count += 1
		xsum += x
		ysum += y
		sum2 += (x + y) * (x + y)
		xysum += x*y
	xmean = xsum / count
	ymean = ysum / count
	variance = (sum2 / count - (xsum + ysum) * (ysum + xsum) / count / count) / 2
	if variance == 0:
		return 0.0
	return ((xysum - xmean * ysum - ymean * xsum) / count + xmean * ymean) / variance

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
	window = min(len(newton_chunk) - 2, len(strava_chunk) - 2, 500)
	for offset in range(-window, window + 1):
		newton_offset = max(offset, 0)
		strava_offset = max(-offset, 0)
		cov = [covariance(stream[0][newton_offset:], stream[1][strava_offset:]) for stream in streams]
		if sum(cov) > sum(best_cov):
			best_cov = cov
			best = offset
		print cov, offset, best_cov, best
	newton_offset = max(best, 0)
	strava_offset = max(-best, 0)
	return newton_offset, strava_offset, min(len(newton_chunk) - newton_offset, len(strava_chunk) - strava_offset), best_cov

newton_offset = strava_offset = 0
newton_progress = strava_progress = 0

while newton_idx < len(newton_chunks) and strava_idx < len(strava_chunks):
	newton_chunk = newton_chunks[newton_idx][newton_offset:]
	strava_chunk = strava_chunks[strava_idx][strava_offset:]
	print len(newton_chunk), len(strava_chunk)
	newton_start, strava_start, length, error = correlate(newton_chunk, strava_chunk)
	print "correlate", newton_start, strava_start, length, error
	if len(newton_chunk) > newton_offset + length + 5:
		newton_offset += newton_start + length
		newton_progress += length
	else:
		print "newton skip", newton_holes[newton_idx]
		newton_progress += newton_holes[newton_idx] + len(newton_chunk)
		newton_idx += 1
		newton_offset = 0
	print "newton", newton_idx, newton_offset, newton_progress
	if len(strava_chunk) > strava_start + length + 5:
		strava_offset += strava_start + length
		strava_progress += length
	else:
		print "strava skip", strava_holes[strava_idx]
		strava_progress += strava_holes[strava_idx] + len(strava_chunk)
		strava_idx += 1
		strava_offset = 0
	print "strava", strava_idx, strava_offset, strava_progress


import ipdb
#ipdb.set_trace()
