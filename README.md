# License

BSD, 2 clause.

Copyright (c) 2016, David Buckley
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# PowerPod in Python

Python code for talking to Velocomp PowerPod hardware (and probably works on Newton/iBike devices, too). Quite heavily under construction, but tested somewhat on my Linux machine.

Also includes a browser extension to get the data to render in Firefox/Chrome (only tested in Chrome).

While I've made an attempt to get profile data decoded, my main focus is on importing ride data. The contents of the profile are somewhat interesting, though. If you want to mess with profile data (tweaking ride parameters etc.), for now at least I recommend you use Isaac.

I don't intend to ever deal with firmware updates. If you want to update your firmware, *use Isaac*.

## Getting rides

Get all of the rides from the device into the `rides` directory, obliterating existing data without prompt.

```
mkdir rides && ./powerpod-command get_all_rides
```

## Syncing up a Strava ride

Make an `extradata.json` file for the Strava extension, trying to guess a relative offset.

```
python correlate.py <raw_ride_file> <strava_ride_id> > extradata.json
```

## Showing PowerPod data in Strava

Add the `ext` directory as an extension in your browser, and host `extradata.json` on your local webserver root.

TODO:

* Make this load an URL from the ride description/user profile.

## Pretending to be a PowerPod

Get two cp210x USB adapters and loop one into the other. Run Isaac on a machine with one end, and `simulator.py` on the other.

I've been using this to test my understanding of the protocol. I've been testing by plugging both USB adaptors in locally and showing one to `simulator.py` and the other to Isaac running in VirtualBox.

## Protocol

Protocol was reverse engineered by dumping USB chatter. It is dealt with, to the best of my knowledge of how it works, in `powerpod.connection`.

There's an "Interrupt" packet, and whenever that happens on the wire, protocol desyncs. I must be doing that wrong.

`NewtonSerialProtocol` tries to be a machine for sending and receiving data from the device.

Many commands and other wire types are represented by classes in `powerpod.messages`. These were reverse engineered by dumping USB chatter while values in Isaac were altered. Ride data was correlated against the CSV files output by Isaac.

Isaac detects device presence by looping "get serial number" and "get firmware version". It sets the device clock on connect, and every hour.

## TODO / Roadmap

* New stuff:
  * Remaining fields in ride header.
    * Add asserts for "seen" values to make spotting stuff easier.
    * Figure out why Isaac alters altitude numbers a bit.
      * Is it because of tilt cal?
      * Correction?
        * What correction?
    * Average temperature -- how does this affect pressure? Does this mean anything else?
  * Remaining ride fields:
    * `unknown_0` may be tilt cal correction (or just corrected tilt cal).
    * `acceleration_maybe` -- maybe try strobing it and try a mass change in Isaac?
    * Everything else.
  * WTF is `ftp_per_kilo_ish` actually? Get some good data.
* Tool to convert `.raw` -> `.gpx`.
  * Something to print out a decoded header, too (wrong shape for GPX!).
  * Alter correlate tool to correlate two `.gpx` files (PowerTap time invariably disagrees with GPS by at least a few seconds).
  * Split out GPX correlate tool to a new repo?
* Get Strava extra thing to fetch from a URL in the ride.
  * Auto-upload to eg. Amazon S3.
  * Split out into a distinct repo?

## Unknown stuff

### Cal rides

Don't know how to set these. I reset my profile, then went through the setup menu and picked defaults, then "better accuracy". Isaac did:

```
INFO:__main__:<- GetProfileNumberCommand()
INFO:__main__:-> GetProfileNumberResponse(number=0)
INFO:__main__:<- GetFirmwareVersionCommand()
INFO:__main__:-> GetFirmwareVersionResponse(version_encoded=1112)
INFO:__main__:<- SetProfileNumberCommand(number=0)
INFO:__main__:-> None
INFO:__main__:<- SetSampleRateCommand(unknown=0, sample_rate=0)
INFO:__main__:-> None
INFO:__main__:<- SetUnitsCommand(units_type=0)
INFO:__main__:-> None
INFO:__main__:<- SetProfileDataCommand(total_mass_lb=205, user_edited=32781, wheel_circumference_mm=2096, sample_smoothing=10251, aero=0.5536454319953918, fric=11.30159854888916, unknown_6=0.0, unknown_7=0.0, wind_scaling_sqrt=1.2247449159622192, speed_id=0, cadence_id=0, hr_id=0, power_id=0, speed_type=0, cadence_type=0, hr_type=0, power_type=0, tilt_cal=-0.7000000000000001, cal_mass_lb=205, rider_mass_lb=180, unknown_9=1803, ftp_per_kilo_ish=1, ftp_over_095=85, unknown_a=769)
INFO:powerpod.messages:Setting profile: {'user_edited': (32780, 32781), 'wind_scaling_sqrt': (1.1510859727859497, 1.2247449159622192), 'aero': (0.4889250099658966, 0.5536454319953918), 'fric': (11.310999870300293, 11.30159854888916)}
INFO:__main__:-> None
INFO:__main__:<- SetProfileData2Command(power_smoothing_seconds=1, unknown_c=50)
INFO:__main__:-> None
```

Going through the same thing again with "best accuracy", it does exactly the same, but with different model parameters:

```
INFO:powerpod.messages:Setting profile: {'user_edited': (32780, 32781), 'wind_scaling_sqrt': (1.1510859727859497, 1.0), 'aero': (0.4889250099658966, 0.369096964597702), 'fric': (11.310999870300293, 11.30159854888916)}
```

So it could be that the 1.0/0.369/11.3016 setup triggers a cal ride.
