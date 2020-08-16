#!/usr/bin/env python3.8

import argparse
import sys
import pprint
import subprocess
import json
import math

from os import path

import googlemaps
import heldkarp
from datetime import datetime
import time
from haversine import haversine, Unit

def compute_distance_in_miles(latlons):
    distance = 0
    prev = latlons[0]
    for latlon in latlons:
        distance = distance + haversine((float(prev["lat"]), float(prev["lng"])),
                                        (float(latlon["lat"]), float(latlon["lng"])),
                                        unit=Unit.MILES)
    return distance

def download_segment_data(access_token, segment_id):
  completed = subprocess.run(["curl", "-G", "https://www.strava.com/api/v3/segments/{}".format(segment_id), "-H", "Authorization: Bearer {}".format(access_token)], capture_output=True)
  segment_json = completed.stdout.decode("utf-8")
  with open("segment_information/{}.json".format(segment_id), 'w') as file:
      file.write(segment_json)

def write_gpx(latlons, filename):
    overall_distance = compute_distance_in_miles(latlons)

    # We move at 1mph, so set the start time to back far enough so the ride doesn't
    # end in the future. Note that we attempt to make this look like a real ride
    # because otherwise Strava rejects the GPX file. Unfortunately the only way
    # to create a route on Strava is to upload it as a ride first and then make
    # a route from that, so we have to do this.
    current_time = time.time() - overall_distance * 3600 * 2
    current_datetime_string = datetime.fromtimestamp(current_time).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    with open(filename, 'w') as file:
        file.write(r'<?xml version="1.0" encoding="UTF-8"?>')
        file.write('\n')
        file.write(r'''<gpx xmlns="http://www.topografix.com/GPX/1/1"
                        xmlns:gpxdata="http://www.cluetrust.com/XML/GPXDATA/1/0"
                        creator="--No GPS SELECTED--" version="8.1">''')
        file.write('<metadata><time>{}</time></metadata>'.format(current_datetime_string))
        file.write(r'  <name>Example gpx</name><type>Biking</type>')
        file.write('\n')
        file.write(r'  <trk><name>Example gpx</name><number>1</number><trkseg>')
        file.write('\n')
        prev_latlon = latlons[0]
        for latlon in latlons:
            # Move forward at 1mph plus a 1 second slack.
            difference_distance = compute_distance_in_miles([prev_latlon, latlon])
            current_time = current_time + 1 + (3600)*difference_distance

            current_datetime_string = datetime.fromtimestamp(current_time).strftime(
              "%Y-%m-%dT%H:%M:%SZ")
            file.write('    <trkpt lat="{}" lon="{}"><time>{}</time></trkpt>'.format(latlon["lat"], latlon["lng"], current_datetime_string))
            file.write('\n')
            prev_latlon = latlon
        file.write('  </trkseg></trk>')
        file.write('\n')
        file.write('</gpx>')

def get_segment_information(strava_access_token, segment_id):
  filename = "segment_information/{}.json".format(segment_id)
  if not path.exists(filename):
      download_segment_data(strava_access_token, segment_id)

  with open(filename, "r") as file:
    segment_json = json.loads(file.read())
    segment_polyline = segment_json["map"]["polyline"]
    segment_length = segment_json["distance"]
    segment_latlngs = googlemaps.convert.decode_polyline(segment_polyline)
    return {"length": segment_length, "latlngs" : segment_latlngs}

def get_directions(gmaps, start_latlng, end_latlng):
    directions_result = gmaps.directions(start_latlng, end_latlng, mode="bicycling")
    polyline = directions_result[0]["overview_polyline"]["points"]
    return googlemaps.convert.decode_polyline(polyline)

def get_segment_ordering_heldkarp(gmaps, start_latlng, segment_information, indices):
    # 2N segments. Need to include from start of a segment to end of a segment, but
    # there is only one path there.
    start_and_segment_information = [{'length': 1, 'latlngs': [start_latlng, start_latlng]}] + segment_information
    number_of_points = 1 + len(segment_information)
    distances = [[0] * number_of_points for i in range(number_of_points)]
    segment_distances = []
    for i in range(len(start_and_segment_information)):
        origin_latlngs = start_and_segment_information[i]["latlngs"]

        # Start at the end
        origin = origin_latlngs[len(origin_latlngs) - 1]

        # Compute distance of end of this segment to start of all the other ones.
        destination_segment_information = start_and_segment_information[:i] + start_and_segment_information[i+1:]
        destinations = [x["latlngs"][0] for x in destination_segment_information]
        matrix = gmaps.distance_matrix([origin], destinations, mode="bicycling", units="metric")
        distance_destinations = matrix["rows"][0]['elements']

        for j in range(len(start_and_segment_information)):
            if i == j: continue
            elif j > i: destination_index = j-1
            else: destination_index = j

            # Go from end to start of next value.
            distance_destination = distance_destinations[destination_index]["distance"]["value"]
            distances[i][j] = distance_destination + start_and_segment_information[j]["length"]

    print("Completed constructing distance matrix")
    path = heldkarp.held_karp(distances)
    result = []
    for i in path:
        if i == 0: continue
        else:
            indices.append(i-1)
            result.append(segment_information[i-1]["latlngs"])
    return result

def get_segment_ordering_greedy(gmaps, start_latlng, segment_latlngs, max_segments, indices):
    # This uses the nearest neighbor greedy algorithm for determining
    # the segment ordering. It starts with the origin, then finds the next
    # closest segment, and then the next closest, etc. This is not optimal, but
    # it works if you have a very large number of segments. For a smaller number where
    # you want an optimal solution, use the heldkarp algorithm above.
    result = []
    origin = start_latlng
    remaining = set(range(0, len(segment_latlngs)))
    while (len(remaining) > 0):
        distances = []
        for i in range(0, len(segment_latlngs)):
            # Already visited this segment
            if i not in remaining: continue

            segment_latlng_start = segment_latlngs[i][0]

            distances = distances + [(i, compute_distance_in_miles([origin, segment_latlng_start]))]

        # Sort by distance.
        distances.sort(key=(lambda a : a[1]))

        # Get the actual distances for the then closest.
        top_ten_destinations = [segment_latlngs[i][0] for (i, _) in distances[:10]]
        matrix = gmaps.distance_matrix([origin], top_ten_destinations, mode="bicycling")
        distance_destinations = matrix["rows"][0]['elements']
        indices_sorted = sorted(range(len(distance_destinations)),
                                 key=lambda k: distance_destinations[k]["distance"]["value"])

        closest_index = distances[indices_sorted[0]][0]
        closest_next_segment = segment_latlngs[closest_index]

        # Take the closest as the next value, and its end point as the next start.
        result = result + [closest_next_segment]
        origin = closest_next_segment[len(closest_next_segment) - 1]
        remaining.remove(closest_index)
        indices.append(closest_index)

        if max_segments != -1 and len(segment_latlngs) - len(remaining) >= max_segments:
            break

    return result

def make_gpx(gmaps, start_latlng, next_latlng, segment_latlngs, output_file_name):
    latlngs = [start_latlng]
    if (next_latlng is not None):
        latlngs = latlngs + get_directions(gmaps, start_latlng, next_latlng)
    for segment_latlng in segment_latlngs:
        # Go from previous point to start of segment
        latlngs = latlngs + get_directions(gmaps, latlngs[len(latlngs) -1], segment_latlng[0])

        # Go from start of segment to end
        latlngs =  latlngs + segment_latlng

    # Go from last segment back to first.
    latlngs = latlngs + get_directions(gmaps, latlngs[len(latlngs) -1], start_latlng)
    write_gpx(latlngs, output_file_name)

def main():
    parser = argparse.ArgumentParser(
        description=(r"""Determines a route from a selection of Strava segments
                     Example:
                     ./routebuilder.py --maps_api_key=2342342
                                      --strava_access_token=121321
                                      --segments=24977520,24627589
                                      --output_file=output.gpx --start_lat_lng="41.448160, -79.930200"
                     """))

    parser.add_argument("--maps_api_key", type=str, required=True,
                        help="The Google Maps API key to use")
    parser.add_argument("--segments", type=str, required=True,
                        help='The csv list of segments you want in the route')
    parser.add_argument("--output_file", type=str, required=True,
                        help="The location of the output gpx file which will contain the route")
    parser.add_argument("--start_lat_lng", type=str, required=True,
                        help="The starting latitude and longitude pair in (lat,lng) format")
    parser.add_argument("--strava_access_token", type=str, required=True,
                        help="The Strava access token used to access Strava APIs")
    parser.add_argument("--max_segments", type=int, required=False, default=-1,
                        help=("""The maximum number of segments you want in the route.
                                 Note that this can produce some rather non optimal routes
                                 since it doesn't do anything special except stop the
                                 greedy algorithm early. It also doesn't work with the
                                 heldkarp option.
                              """))
    parser.add_argument("--next_point", type=str, required=False, default=None,
                        help=("""If set, this is the lat/lng pair for the the place you
                                 want to go after the start location. This is useful
                                 if you want to do segments in an area but also want
                                 to get to that area from your home"""))
    parser.add_argument("--heldkarp", dest='heldkarp',
                        action='store_true', required=False, default=False,
                        help=("""Use the Held-Karp algorithm instead of the greedy one.
                                 This becomes exponential in the number of segments
                                 rather than quadratric. It is recommended that you
                                 do not use this for greater than 15 segments.
                                 This produces the "optimal route" using bike directions"""))

    args = parser.parse_args()
    segments = args.segments.split(',')
    (start_lat, start_lng) = args.start_lat_lng.split(',')
    start_latlng = start_latlng = {"lat": start_lat, "lng": start_lng}

    if args.next_point is not None:
        (next_lat, next_lng) = args.next_point.split(',')
        next_latlng = {"lat": next_lat, "lng": next_lng}
    else: next_latlng = None

    gmaps = googlemaps.Client(key=args.maps_api_key)

    indices = []
    segment_information = [get_segment_information(args.strava_access_token, s) for s in segments]

    if not args.heldkarp:
        segment_latlngs_ordered = get_segment_ordering_greedy(
            gmaps, next_latlng if next_latlng is not None else start_latlng,
            [x["latlngs"] for x in segment_information], args.max_segments, indices)
    else:
        segment_latlngs_ordered = get_segment_ordering_heldkarp(
            gmaps, next_latlng if next_latlng is not None else start_latlng, segment_information, indices)

    make_gpx(gmaps, start_latlng, next_latlng, segment_latlngs_ordered, args.output_file)
    print([segments[i] for i in indices])

if __name__ == "__main__":
    main()
