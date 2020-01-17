# R2B2 Extractor

## Description

Extractor for pulling data from R2B2 into .csv files. There are two endpoints - `stats` and `private-deals` available. The extractor downloads all the available dimensions for the selected endpoints:

* stats: day, website, placement
* private-deals: day, website, deal, placement, advertiser, buyer

See [R2B2 API documentation ](https://aym.r2b2.cz/api/v1/docs/) or [user guide](https://aym.r2b2.cz/api/v1/docs/help/guide.php) for further details.

## Requirements

R2B2 API credentials

## How to use it

Create or modify `config.json` file. As described in `sample-config.json`.
There are 3 options how to specify the period to download.

- To download the data over fixed period, set `date_type` to `fixed` and specify `from` and `to`.

- To download the data over the last n days before today, set `date_type` to `interval` and specify the number of days as `date_interval`. You can choose whether to include today's data or not in the `interval` download. 
- To download daily data for the last n days before today, set `date_type` to `backfill` and specify the number of days as `date_interval`.  

Specify the endpoints to download: `stats` or `private-deals` or both of them. You can choose whether to dislpay custom name or not for `stats` endpoint.

### Config explanation

| Parameter | Type | Description |
| --- | --- | --- |
| credentials | dictionary | R2B2 API credentials |
| date_type | string | fixed or interval or backfill |
| date_interval | int | number of days before today |
| include_today | boolean | include today's data for interval date type   |
| from | string | date in YYYY-MM-DD format   |
| to | string | date in YYYY-MM-DD format  |
| endpoints | list of strings | endpoint names   |
| display_custom_name | boolean | display custom name for stats endpoint |


