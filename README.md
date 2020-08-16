# Strava Tools

This repo contains a collection of tools primarily around strava segments. It contains a few runnable scripts

* **Segment Leaderboard**: A tool for automatically creating segment challenge leaderboards.
* **Segment Tracker**: Takes a leaderboard config file and outputs segments that a particular user has not completed yet.
* **Star Segments**: Takes a list of segments and stars them.
* **Route Builder**: A tool for automatically creating a route from a set of segments.
* **Individual Segment Rankings**: Gives csv file with segment,ranking,total_num_riders for a particular person. Not documented because its bad right now.

See below for more information on each tool

## Strava Segment Leaderboard

### Overview

Welcome to the segment leaderboard creator, the best tool ever for creating leaderboards during segment challenges. What's that you say? I should be using Strava APIs instead of parsing HTML and copying cookie files from a browser? Sounds great! Let me just check ... oops [looks like NO](https://www.dcrainmaker.com/2020/05/strava-cuts-off-leaderboard-for-free-users-reduces-3rd-party-apps-for-all-and-more.html)

So yeah, in the absence of doing things in a proper way, I wrote this instead! The goal of this tool is to create a leaderboard for segment challenges. These are events where riders ride a variety of segments. Each rider is given a certain number of points depending on their place on the segment. The total on all segments is then summed to get the total points for each rider. Then we sort by total, and voila, leaderboard.

### Config File

The tool takes as input a JSON configuration file with a list of segments and configuration options. It allows for multiple runs, that is, different outputs with different options.

Format is as follows. Comments are to describe the fields, but obviously you can't copy them since json doesn't allow comments.

~~~~
{
    # A list of segment ids that you want to be on the leaderboard. These are strings.
    "segments": ["1", "2"],

    # The number of points assigned to each rank on the leaderboard per segment. So in this example
    # first place gets ten, second five, and third one.
    "points": [ 10, 5, 1],

    # The number of points a participant gets just for doing a segment. This is added to
    # the points they receive for placing. So in this example, first place would receive
    # 10 + 1 = 11 points.
    "participation_points": 1,

    # The number of points a participant gets just for doing the segment if they don't
    # rank in the points list. That is, if the points list length is 3 and they come in
    # fourth, they get this many points.
    "unmatched_participation_points": 1,

    # The list of run configurations to do. Each one allows for a different set of options
    # and output files.
    "runs": [
      {
        # The name of the file that where you want the data output.
        "output_file": "WomenRankingsThisMonth.txt",

        # The additional URL parameters for this configuration.
        # This one says "Overall list for all women in the past month". This
        # can be a list in which case the results are combined. This is useful if
        # you want to create a category like "masters" which is 40+, but Strava
        # only supports querying in age group buckets of ten.
        "options": ["filter=overall&date_range=this_month&gender=F"]
      },
      {
        "output_file": "OverallToday.txt",
        "options": ["filter=overall&date_range=today"]
      }
    ]
}
~~~~

Take a look at the august_neighborhood_segment_challenge.txt file in the examples folder for a detailed working example.

### Cookie File

The cookie file is in standard [netscape/mozilla format](https://xiix.wordpress.com/2006/03/23/mozillafirefox-cookie-format/). You'll need to install the [cookies.txt chrome extension](https://chrome.google.com/webstore/detail/cookiestxt/njabckikapfpffapmjgojcnbfjonfjfg?hl=en) to get this information

### Steps to run the program

This assumes you have the cookies.txt chrome extension and python installed

1. Open strava.com and login if you haven't
2. Open the cookies.txt extension and download the cookies for that page, let's call it "stravacookies.txt"
3. Run the program `python leaderboard.py --config_file=examples/august_neighborhood_segment_challenge.txt --cookie_file=stravacookies.txt --output_dir=/Users/myuser`
4. Bask in the glory of your fully armed and operational leaderboard

The output format is a CSV file with athlete_name, total_points, total_num_segments as the fields

## Segment Tracker

The segment tracker is designed to work with leaderboard challenges, where a person wants to know what segments they still have to complete. The command line is the same
as the leaderboard plus the name of the person you want to track. Example: `python segmentracker.py --config_file=examples/august_neighborhood_segment_challenge.txt --cookie_file=stravacookies.txt --output_dir=/Users/vjc --name="Vinay Chaudhary"`

## Route Builder

The route builder takes a list of segments and automatically creates a route using Google Maps bike directions. For this to work you need both a strava public access token and a Google Maps API token. Both are free to get. The APIs used here are
subject to QPS limits, and the Strava API calls are extremely restrictive (1000 queries a day). To get around this the program caches all of the calls to the Strava
APIs in the `segment_information/` directory so that once it downloads the segment
it doesnt need to call that API again for it.

To run the route builder, do the following steps.

1. Get a Strava public API access token. To do this, you need to register a strava app.
Follow the steps [here](https://developers.strava.com/docs/getting-started/#account). Then take note of the "Your Access Token" field in the ["My API Application" page](https://www.strava.com/settings/api)
2. Next, get a Google Maps API key. If you have not used Google Cloud Platform or Maps
APIs before, this takes a few steps. Follow the instructions [here](https://developers.google.com/maps/documentation/directions/get-api-key)
3. If you've never run the program before you'll need to install the google maps python
library and the haversine distance library. To do so, run `pip install -U googlemaps` and then `pip install haversine`.
4. Now run the command with the Strava access token and Maps API key. Below is the usage and example. It will output the gpx file in the location you specified.
5. Upload the route to Strava or Garmin
   * **Strava**: The gpx to strava route feature no longer works for me, so I've been uploading the gpx file as a ride and then making a route from it. To do this, upload your gpx file as a ride. Mark it as private to avoid sharing the ride you didn't actually do. Now click the ... icon next to the ride and create a route from it. Delete your fake ride once you are done.
   * **Garmin**: Garmin supports just uploading the GPX file. Go to Garmin Connect,
  click Training->Courses then click "Import" and select the output GPX file.

~~~~
usage: routebuilder.py [-h] --maps_api_key MAPS_API_KEY --segments SEGMENTS
                       --output_file OUTPUT_FILE --start_lat_lng START_LAT_LNG
                       --strava_access_token STRAVA_ACCESS_TOKEN
                       [--max_segments MAX_SEGMENTS] [--next_point NEXT_POINT]
                       [--heldkarp]

Determines a route from a selection of Strava segments Example: ./routebuilder.py
--maps_api_key=2342342 --strava_access_token=121321 --segments=24977520,24627589
--output_file=output.gpx --start_lat_lng="41.448160, -79.930200"

optional arguments:
  -h, --help            show this help message and exit
  --maps_api_key MAPS_API_KEY
                        The Google Maps API key to use
  --segments SEGMENTS   The csv list of segments you want in the route
  --output_file OUTPUT_FILE
                        The location of the output gpx file which will contain the
                        route
  --start_lat_lng START_LAT_LNG
                        The starting latitude and longitude pair in (lat,lng) format
  --strava_access_token STRAVA_ACCESS_TOKEN
                        The Strava access token used to access Strava APIs
  --max_segments MAX_SEGMENTS
                        The maximum number of segments you want in the route. Note
                        that this can produce some rather non optimal routes since
                        it doesn't do anything special except stop the greedy
                        algorithm early. It also doesn't work with the heldkarp
                        option.
  --next_point NEXT_POINT
                        If set, this is the lat/lng pair for the the place you want
                        to go after the start location. This is useful if you want
                        to do segments in an area but also want to get to that area
                        from your home
  --heldkarp            Use the Held-Karp algorithm instead of the greedy one. This
                        becomes exponential in the number of segments rather than
                        quadratric. It is recommended that you do not use this for
                        greater than 15 segments. This produces the "optimal route"
                        using bike directions
~~~~

## Star Segments

Star segments takes a list of segments and stars them. This is useful in conjunction
with route builder to star any segments you have on your route. Its a bit of a pain to
use though since you need a personalized login token and that kind of sucks to get without an actual website.
