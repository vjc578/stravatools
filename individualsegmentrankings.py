import sys
import leaderboard
import json
import argparse

class SegmentIndividualAggregator(leaderboard.SegmentRankingsGatherer):
    def __init__(self,  segment, config, run_config, name, stats):
         super().__init__(segment, config, run_config)
         self.stats = stats
         self.name = name

    def process_rankings(self, rankings):
        prev_time = -1
        rank = 1
        count = 1

        # Olympic tie breaking rules, if the same people get the same time they get
        # the same number of points, then the next person gets the N-1st next points slot,
        # where N is the number of ties. So if the points are 35, 30, 25, 20 and the first
        # two people tie, then the first two get 35 and the next gets 25, not 30.
        for (name, time) in rankings:
            if time != prev_time:
                rank = count
            count = count + 1
            prev_time = time
            if name == self.name:
                self.stats.append("{},{},{}".format(self.segment, rank, len(rankings)))
                break

def main():
    parser = argparse.ArgumentParser(
        description="Outputs a list of segments that you still need to do"
    )

    parser.add_argument("--config_file", type=str, required=True)
    parser.add_argument("--cookie_file", type=str, required=True)
    parser.add_argument("--name", type=str, required=True)
    parser.add_argument("--output_file", type=str, required=True)

    args = parser.parse_args()

    config_file = open(args.config_file, "r")
    config_file_contents = config_file.read()
    json_config = json.loads(config_file_contents)
    cookie_file = args.cookie_file
    config = leaderboard.Config(json_config, cookie_file)

    # TODO: Output per config, not just the first one.
    stats = []
    for segment in config.segments:
            aggregator = SegmentIndividualAggregator(segment, config, config.run_configs[0], args.name, stats)
            aggregator.run()

    with open(args.output_file, 'w') as file:
            for stat in stats:
                file.write(stat + "\n")

if __name__ == "__main__":
    main()
