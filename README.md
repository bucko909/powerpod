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

* Add to powerpod-command:
  * Get space usage.
  * Set time.
  * Switch profile.
  * Get/set profile stuff:
    * Power smoothing (get from profile).
    * Sample smoothing (get from profile).
    * ANT+ ids and types (what are the types?).
    * Aero/Rolling properties.
    * Wheel circumference.
    * Total/rider mass.
    * Tilt cal.
    * Cal mass.
    * FTP.
    * Units.
  * Make options to dump/restore profiles.
    * To raw.
    * To JSON (dump known fields).
  * Get(?)/set trainer weights. Find a standard list of them; find out what they do?
  * Get/set intervals (for Newton).
* New stuff:
  * Figure out how to put the device into various cal modes.
  * Figure out screens data.
    * Get/set screens (for Newton).
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
