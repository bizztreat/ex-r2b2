import os
import csv
import json
import requests
from logging import getLogger, basicConfig, INFO
from argparse import ArgumentParser
from datetime import datetime


start = datetime.now()

## Argumetn parser
argparser = ArgumentParser()
argparser.add_argument("-f", "--config", action="store", default="../config.json",
                       help="Filename of the config JSON,\ndefault ../config.json")
argparser.add_argument("-o", "--outpath", action="store", default="../output",
                       help="Output dir,\ndefault ../output")
argparser.add_argument("-l", "--loglevel", action="store",
                       default="INFO", choices=["INFO", "WARN", "ERROR", "DEBUG"])

args = argparser.parse_args()

## Logger
basicConfig(level=INFO, format="[{asctime}] {levelname}: {message}", style="{")
logger = getLogger(__name__)
logger.setLevel(args.loglevel)

## Config path
config_path = args.config

if not os.path.exists(config_path):
    raise Exception("Configuration not specified, was expected at '{}'".format(config_path))

with open(config_path, encoding="utf-8") as conf_file:
    conf = json.load(conf_file)

## OAuth - get acces token
url_oauth = "https://login.trackad.cz/api/oauth2/token"

payload = "grant_type=client_credentials&client_id={0}&client_secret={1}&scope=aym-api".format(conf["credentials"]["client_id"], conf["credentials"]["client_secret"])
headers = {'content-type': 'application/x-www-form-urlencoded'}

response = requests.request("POST", url_oauth, data=payload, headers=headers)

token = response.json()["access_token"]


## Get stats
url_stats = "https://aym.r2b2.cz/api/v1/publisher/stats"
stats_conf=conf["stats_request_body"]

headers = {
    'content-type': "application/json",
    'authorization': "Bearer {}".format(token)
    }

response = requests.request("POST", url_stats, data=json.dumps(stats_conf), headers=headers)

stats = response.json()
 

if ("status" or "payload") not in stats.keys( ):
    logger.error("Unexpected response \n keys: {0}".format(stats.keys( )))
else:
    if not stats["status"]=="ok":
        logger.error("Unexpected response status: {0}".format(stats["status"]))


# main data
data = stats["payload"]
if not data:
    raise Exception("No data found in......")

# add corresponding date and time from config
for d in data:
    d["datetime_from"] = stats_conf["from"]
    d["datetime_to"] = stats_conf["to"]


## Save output
output_path = args.outpath
os.makedirs(output_path, exist_ok=True)

logger.info("Exporting stats to '{}'".format(os.path.join(output_path, "output.csv")))

with open(os.path.join(output_path, "output.csv"), "w", encoding="utf-8") as out_file:
    writer = csv.DictWriter(out_file, fieldnames=data[0].keys(), dialect=csv.unix_dialect)
    writer.writeheader()
    writer.writerows(data)


end = datetime.now()
runtime_sec = round(end.timestamp() - start.timestamp(), 2)

logger.info("Started at {0}, finished at {1}, runtime: {2} seconds".format(start, end, runtime_sec))


