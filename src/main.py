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
from time import sleep
import requests

ENDPOINTS = {
    "stats": "https://aym.r2b2.cz/api/v1/publisher/stats",
    "private-deals": "https://aym.r2b2.cz/api/v1/publisher/stats/private-deals"
}

SCOPES = {
    "stats": "aym-api",
    "private-deals": "aym-api-deals"
}

DIMENSIONS = {
    "stats": [
        "day",
        "website",
        "placement"
    ],
    "private-deals":[
        "day", 
        "website", 
        "deal_name",
        "deal_id",
        "placement", 
        "advertiser", 
        "buyer"
    ]
}

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
        level=INFO, format="[{asctime}] {levelname}: {message}", style="{", stream=sys.stdout)
    logger = getLogger(__name__)
    logger.setLevel(args.loglevel)

    # Config path
    config_path = args.config

    if not os.path.exists(config_path):
        raise Exception(
            "Configuration not specified, was expected at '{}'".format(config_path))

    with open(config_path, encoding="utf-8") as conf_file:
        conf = json.load(conf_file)["parameters"]

    # Get datetime from config
    ## fixed
    if conf["date_type"] == "fixed":
        datetime_from = datetime.strptime(
            conf["from"],
            "%Y-%m-%d"
        )
        datetime_to = datetime.strptime(conf["to"], "%Y-%m-%d") + timedelta(1)
        date_from = datetime_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = datetime_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if "stats" in conf["endpoints"]:
            extract(date_from, date_to, logger, conf, args, "stats")
        if "private-deals" in conf["endpoints"]:
            extract(date_from, date_to, logger, conf, args, "private-deals")
    ## interval
    elif conf["date_type"] == "interval":
        datetime_to = datetime.now()
        if not conf["include_today"]:
            datetime_to = datetime_to.replace(hour=0, minute=0, second=0, microsecond=0)
        datetime_from = datetime_to - timedelta(days=conf["date_interval"])
        datetime_from = datetime_from.replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = datetime_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = datetime_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if "stats" in conf["endpoints"]:
            extract(date_from, date_to, logger, conf, args, "stats")
        if "private-deals" in conf["endpoints"]:
            extract(date_from, date_to, logger, conf, args, "private-deals")
    ## backfill
    else:
        now = datetime.now()
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days = [(now - timedelta(days=d)) for d in range(0, conf["date_interval"])]
        for datetime_to in days:
            datetime_from = datetime_to - timedelta(days=1)
            date_from = datetime_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            date_to = datetime_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            if "stats" in conf["endpoints"]:
                extract(date_from, date_to, logger, conf, args, "stats")
            if "private-deals" in conf["endpoints"]:
                extract(date_from, date_to, logger, conf, args, "private-deals")

def extract(date_from, date_to, logger, conf, args, endpoint):
    logger.info(
        "Requested date in '%s' mode, downloading data from %s to %s",
        conf["date_type"],
        date_from,
        date_to
    )

    # OAuth - get acces token
    url_oauth = "https://aym.r2b2.cz/api/oauth2/access-token"

    payload = "grant_type=client_credentials&client_id={0}&client_secret={1}&scope={2}".format(
        conf["credentials"]["client_id"], conf["credentials"]["#client_secret"], SCOPES[endpoint])

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
    url = ENDPOINTS[endpoint]
    stats_conf = {
        "from": date_from,
        "to": date_to,
        "dimensions": DIMENSIONS[endpoint]
    }
    if endpoint == "stats":
        stats_conf["displayCustomName"] = conf["display_custom_name"]
    
    headers = {
        'content-type': "application/json",
        'authorization': "Bearer {}".format(token)
    }

    response = requests.request(
        "POST", url, data=json.dumps(stats_conf), headers=headers)

    try:
        stats = response.json()
    except json.decoder.JSONDecodeError as err:
        logger.critical("Response from server was invalid JSON (%s)", err)
        logger.critical(response.text)
        sys.exit(1)

    if ("status" or "payload") not in stats.keys():
        logger.error(response.text)
        logger.error("Unexpected response \n keys: %s", stats.keys())
        sys.exit(1)

    if not stats["status"] == "ok":
        logger.error(response.text)
        logger.error("Unexpected response status: %s", stats["status"])
        if "payload" in stats and "message" in stats["payload"]:
            logger.error(stats["payload"]["message"])
            if stats["payload"]["message"] == "messages:oauthAccessTokenWasNotFound" or stats["payload"]["errorType"] == "access_denied":
                logger.info("This is a known R2B2 API Bug, will retry in 10 seconds")
                sleep(10)
                return extract(date_from, date_to, logger, conf, args, endpoint)
        sys.exit(1)

    # main data
    data = stats["payload"]
    if not data:
        logger.warning("Endpoint %s returned no data", endpoint)
        return

    # add corresponding date and time from config
    for row in data:
        row["date_from"] = stats_conf["from"]
        row["date_to"] = stats_conf["to"]

    # Save output
    output_path = args.outpath
    os.makedirs(output_path, exist_ok=True)

    output_fname = os.path.join(output_path, "{}.csv".format(endpoint))

    logger.info("Exporting %s to '%s'", endpoint, output_fname)

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
