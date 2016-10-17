var extraData = null;

var loaded = function () {
	extraData = JSON.parse(this.responseText);
	// ensure we have an analysis; copied from Strava code
	var chart_context = pageView.chartContext()
	pageView.analysisRequest() == null && pageView.analysisRequest(chart_context.createRequest());
	// add extra stream type formatters
	var analysis = chart_context.analysis();
	analysis.stackedStreamTypes.splice(5, 0, 'grade_smooth');
	analysis.stackedStreamTypes.splice(6, 0, 'altitude');
	add_field('newton_air_velocity', 'velocity_smooth', 'Wind Speed (Newton)');
	add_field('newton_ground_velocity', 'velocity_smooth', 'Ground Speed (Newton)');
	add_field('newton_cadence', 'cadence', 'Cadence (Newton)');
	add_field('newton_heartrate', 'heartrate', 'Heart Rate (Newton)');
	add_field('newton_temp', 'temp', 'Temperature (Newton)');
	add_field('newton_elevation', 'altitude', 'Elevation (Newton)');
	add_field('newton_slope', 'grade_smooth', 'Slope (Newton)');
	add_field('slope_average', 'altitude', 'Slope (N) Average');
	add_field('elev_corr', 'altitude', 'Corrected (N) Ele');
	add_field('newton_power', 'watts', 'Power (Newton)');
	add_field('newton_thingy', 'altitude', 'Unknown (Newton)');
	add_field('newton_acceleration', 'grade_smooth', 'Acceleration? (Newton)');
	// inject extra types
	try_inject();
}

function add_field(name, base, english) {
	var chart_context = pageView.chartContext()
	var stream_types = chart_context.Ride().streamTypes;
	var analysis = chart_context.analysis();
	stream_types[name] = stream_types[base];
	analysis.stackedStreamTypes.splice(analysis.stackedStreamTypes.indexOf(base) + 1, 0, name);
	Strava.I18n.Locales.DICTIONARY.strava.charts.activities.chart_context[name] = english;
}

var try_inject = function () {
	var stream_data = pageView.analysisRequest().streams.streamData.data;
	if (stream_data == null) {
		console.log("Retrying");
		window.setTimeout(try_inject, 10);
		return;
	}
	var chart_context = pageView.chartContext();
	var stream_types = chart_context.Ride().streamTypes;
	for (var i = 0; i < extraData.length; i++) {
		if (!(extraData[i]['type'] in stream_types)) {
			console.log("Skipping " + extraData[i]["type"] + " as no formatter")
		} else if (!(extraData[i]['type'] in stream_data)) {
			console.log("Injecting " + extraData[i]["type"]);
			stream_data[extraData[i]['type']] = extraData[i]['data'];
			//analysis.stackedStreamTypes.splice(0, 0, extraData[i]['type']);
			//analysis.streamTypes.splice(0, 0, extraData[i]['type']);
		} else {
			console.log("Skipping " + extraData[i]["type"] + " as exists")
		}
	}
}

var extra_fetch = new XMLHttpRequest();
extra_fetch.addEventListener('load', loaded);
extra_fetch.open("GET", "https://localhost/extradata.json");
extra_fetch.send();

// Patch d3 to force Strava lines to leave holes where data is missing.
var old_line = d3.svg.line;
d3.svg.line = function new_line() { return old_line.apply(this, arguments).defined(function (x) { return !('y' in x) || x.y != null; }) }
