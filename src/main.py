"""R2B2 Extractor.

usage: main.py [-h] [-f CONFIG] [-o OUTPATH] [-l {INFO,WARN,ERROR,DEBUG}]

optional arguments:
  -h, --help            show this help message and exit
  -f CONFIG, --config CONFIG
                        Filename of the config JSON, default ../config.json
  -o OUTPATH, --outpath OUTPATH
                        Output dir, default ../output
  -l {INFO,WARN,ERROR,DEBUG}, --loglevel {INFO,WARN,ERROR,DEBUG}
"""

import os
import sys
import csv
import json

from logging import getLogger, basicConfig, INFO
from argparse import ArgumentParser
from datetime import datetime, timedelta
import requests

def main():
    """Main function to run extraction
    """
    # Argumetn parser
    argparser = ArgumentParser()
    argparser.add_argument("-f", "--config", action="store", default="../config.json",
                           help="Filename of the config JSON,\ndefault ../config.json")
    argparser.add_argument("-o", "--outpath", action="store", default="../output",
                           help="Output dir,\ndefault ../output")
    argparser.add_argument("-l", "--loglevel", action="store",
                           default="INFO", choices=["INFO", "WARN", "ERROR", "DEBUG"])

    args = argparser.parse_args()

    # Logger
    basicConfig(
        level=INFO, format="[{asctime}] {levelname}: {message}", style="{")
    logger = getLogger(__name__)
    logger.setLevel(args.loglevel)

    # Config path
    config_path = args.config

    if not os.path.exists(config_path):
        raise Exception(
            "Configuration not specified, was expected at '{}'".format(config_path))

    with open(config_path, encoding="utf-8") as conf_file:
        conf = json.load(conf_file)
    
    # Get datetime from config
    ## fixed
    if conf["date_type"] == "fixed":
        datetime_from = datetime.strptime(
            conf["from"],
            "%Y-%m-%d"
        )
        datetime_to = datetime.strptime(conf["to"], "%Y-%m-%d")
        date_from = datetime_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = datetime_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        extract(date_from, date_to, logger, conf, args)
    ## interval
    elif conf["date_type"] == "interval":
        datetime_to = datetime.now()
        if not conf["include_today"]:
            datetime_to = datetime_to.replace(hour=0, minute=0, second=0, microsecond=0)
        datetime_from = datetime_to - timedelta(days=conf["date_interval"])
        date_from = datetime_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = datetime_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        extract(date_from, date_to, logger, conf, args)
    ## backfill
    else:
        now = datetime.now()
        if not conf["include_today"]:
            now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days = [(now - timedelta(days=d)) for d in range(0, conf["date_interval"])]
        for datetime_to in days:
            datetime_from = datetime_to - timedelta(days=1)
            date_from = datetime_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            date_to = datetime_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            extract(date_from, date_to, logger, conf, args)

def extract(date_from, date_to, logger, conf, args):
    logger.info(
        "Requested date in '%s' mode, downloading data from %s to %s",
        conf["date_type"],
        date_from,
        date_to
    )

    # OAuth - get acces token
    url_oauth = "https://login.trackad.cz/api/oauth2/token"

    payload = "grant_type=client_credentials&client_id={0}&client_secret={1}&scope=aym-api".format(
        conf["credentials"]["client_id"], conf["credentials"]["client_secret"])

    headers = {'content-type': 'application/x-www-form-urlencoded'}

    response = requests.request(
        "POST", url_oauth, data=payload, headers=headers)

    response_data = response.json()
    if not "access_token" in response_data:
        logger.critical(response.text)
        raise PermissionError(
            "Wrong response from server, there was no 'access_token'")

    token = response_data["access_token"]

    # Get stats
    url_stats = "https://aym.r2b2.cz/api/v1/publisher/stats"
    stats_conf = {
        "from": date_from,
        "to": date_to,
        "dimensions": conf["dimensions"],
        "displayCustomName": conf["displayCustomName"]
    }

    headers = {
        'content-type': "application/json",
        'authorization': "Bearer {}".format(token)
    }

    response = requests.request(
        "POST", url_stats, data=json.dumps(stats_conf), headers=headers)

    try:
        stats = response.json()
    except json.decoder.JSONDecodeError as err:
        logger.critical("Response from server was invalid JSON (%s)", err)
        logger.critical(response.text)
        sys.exit(255)

    if ("status" or "payload") not in stats.keys():
        logger.error("Unexpected response \n keys: %s", stats.keys())
        sys.exit(255)

    if not stats["status"] == "ok":
        logger.error("Unexpected response status: %s", stats["status"])
        sys.exit(255)

    # main data
    data = stats["payload"]
    if not data:
        raise Exception("No data found in......")

    # add corresponding date and time from config
    for row in data:
        row["date_from"] = stats_conf["from"]
        row["date_to"] = stats_conf["to"]

    # Save output
    output_path = args.outpath
    os.makedirs(output_path, exist_ok=True)

    output_fname = os.path.join(output_path, "output.csv")

    logger.info("Exporting stats to '%s'", output_fname)

    if os.path.exists(output_fname):
        appending = True
    else:
        appending = False

    with open(output_fname, "a" if appending else "w", encoding="utf-8") as out_file:
        writer = csv.DictWriter(
            out_file, fieldnames=data[0].keys(), dialect=csv.unix_dialect)
        if not appending:
            writer.writeheader()
        writer.writerows(data)

if __name__ == "__main__":
    main()
