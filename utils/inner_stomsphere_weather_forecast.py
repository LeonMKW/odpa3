# -*- coding: UTF-8 -*-
import json
from datetime import datetime, timedelta
from json.decoder import JSONDecodeError
import pandas as pd
import requests
import re
import dfply as d

from utils.db import get_mongo
from utils.flightcontrol_utils import tm_table
import pytz
from utils.authentication import get_header_token
import time
from utils.authentication import get_header_token


def search_antennas_by_keyword(post_token_url, post_token_user_name, post_token_password,
                               gateway_station_code_url,
                               keyword):
    # Fetch the token
    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    # Define the headers with the required token
    headers = {
        # 'x-web-token': 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEifQ.eyJpZCI6MTE3Mywic3ViIjoiOSIsImF1ZCI6IjgiLCJleHAiOjE3NDgwNzUwMDksImlhdCI6MTc0Mjg5MTAwOX0.HXNnCaWVIsF9D1hxlwgqnOy03OHxPed09G12qiZXug2oYKwvyv6ADTVTAEd2e1i1-qtve179oomF8CEWsayQag',
        'x-web-token': token,
        'Content-Type': 'application/json'  # Explicitly specify JSON format
    }

    body = {
        "states": [1, 2],
        "page": 1,
        "pageSize": 20,
        "keyword": keyword
    }

    try:
        resp = requests.post(gateway_station_code_url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

    except requests.RequestException as e:
        print(f"Error searching antennas: {e}")
        return []

    if data.get("code") != 0:
        print(f"Unexpected code in search result: {data}")
        return []

    # Return the "list"
    antennas = data.get("data", {}).get("list", [])
    return antennas


def get_antennas_geographic_location(post_token_url, post_token_user_name, post_token_password,
                                     gateway_station_location_url,
                                     antenna_ids):
    # Fetch the token
    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    # Define the headers with the required token
    headers = {
        # 'x-web-token': 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEifQ.eyJpZCI6MTE3Mywic3ViIjoiOSIsImF1ZCI6IjgiLCJleHAiOjE3NDgwNzUwMDksImlhdCI6MTc0Mjg5MTAwOX0.HXNnCaWVIsF9D1hxlwgqnOy03OHxPed09G12qiZXug2oYKwvyv6ADTVTAEd2e1i1-qtve179oomF8CEWsayQag',
        'x-web-token': token,
        'Content-Type': 'application/json'  # Explicitly specify JSON format
    }

    body = {
        "ids": antenna_ids,
        "configFields": ["geographicLocation"]
    }

    try:
        resp = requests.post(gateway_station_location_url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Error requesting detail for antennas: {e}")
        return {}

    # structure: code=0, data->list = [...], each item has "id" and config->geographicLocation
    if data.get("code") != 0:
        print(f"Unexpected code in detail result: {data}")
        return {}

    detail_list = data.get("data", {}).get("list", [])

    # Convert to a dict: { id -> (latitude, longitude, altitude) }
    results = {}
    for ant in detail_list:
        ant_id = ant.get("id")
        if not ant_id:
            continue
        geo = ant.get("config", {}).get("geographicLocation", {})
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        alt = geo.get("altitude")
        # store it
        results[ant_id] = {
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "antenna_code": ant.get("code"),
            "antenna_name": ant.get("name")
        }

    return results


def fetch_antennas_lat_lon(post_token_url, post_token_user_name, post_token_password,
                           gateway_station_code_url,
                           gateway_station_location_url,
                           keyword):
    """
    1) search the antennas by 'keyword'
    2) gather their IDs
    3) get details (lat/lon) via detail endpoint
    4) return a dict { antenna_code: { lat, lon, alt } }
    """
    # 1) search
    antennas = search_antennas_by_keyword(post_token_url, post_token_user_name, post_token_password,
                                          gateway_station_code_url,
                                          keyword)
    if not antennas:
        print("No antennas found for keyword")
        return {}

    # 2) gather IDs
    antenna_ids = [a["id"] for a in antennas if a.get("id")]

    # 3) get geographic location
    detail_dict = get_antennas_geographic_location(post_token_url, post_token_user_name, post_token_password,
                                                   gateway_station_location_url,
                                                   antenna_ids)

    # 4) build a final dict keyed by code or something
    final_results = {}
    for a in antennas:
        ant_id = a["id"]
        code = a["code"]
        if ant_id in detail_dict:
            lat = detail_dict[ant_id]["latitude"]
            lon = detail_dict[ant_id]["longitude"]
            alt = detail_dict[ant_id]["altitude"]
            final_results[code] = {
                "id": ant_id,
                "name": a.get("name"),
                "latitude": lat,
                "longitude": lon,
                "altitude": alt
            }
        else:
            final_results[code] = {"Error": "No detail found"}

    return final_results


# scale helper functions
def compute_beaufort_scale(windspeed_kmh):
    """
    Convert speed in km/h to Beaufort scale (0..12).
    Basic reference: https://en.wikipedia.org/wiki/Beaufort_scale
    Example thresholds in km/h:
      0-1  => 0
      1-5  => 1
      6-11 => 2
      ...
      ~118+ => 12
    """
    speed = float(windspeed_kmh)

    if speed < 1:
        return 0
    elif speed <= 5:
        return 1
    elif speed <= 11:
        return 2
    elif speed <= 19:
        return 3
    elif speed <= 28:
        return 4
    elif speed <= 38:
        return 5
    elif speed <= 49:
        return 6
    elif speed <= 61:
        return 7
    elif speed <= 74:
        return 8
    elif speed <= 88:
        return 9
    elif speed <= 102:
        return 10
    elif speed <= 117:
        return 11
    else:
        return 12


def compute_beaufort_scale_chinese(b_scale):
    """
    Maps the numeric B_wind_scale (0..12) to the Chinese name.
    <1, 无风,1软风,2轻风,3微风,4和风,5劲风,6强风,7疾风,8大风,9烈风,10狂风,11暴风,12飓风
    """
    mapping = {
        0: "无风",
        1: "软风",
        2: "轻风",
        3: "微风",
        4: "和风",
        5: "劲风",
        6: "强风",
        7: "疾风",
        8: "大风",
        9: "烈风",
        10: "狂风",
        11: "暴风",
        12: "飓风"
    }
    return mapping.get(b_scale, "未知")


def compute_precip_scale(precip_mm):
    """
    Simple example of a 'Chinese' precipitation scale:
    e.g. 0 => '无雨', 0-0.1 => '微量', 0.1-10 => '小雨', 10-25 => '中雨', etc.
    Adjust to your needs.
    """
    p = float(precip_mm)
    if p <= 0:
        return "无雨"
    elif p < 0.1:
        return "微量"
    elif p < 10:
        return "小雨"
    elif p < 25:
        return "中雨"
    elif p < 50:
        return "大雨"
    elif p < 100:
        return "暴雨"
    else:
        return "特大暴雨"


# transform weather data functions
def transform_weather_data(raw_weather):
    """
    Takes the dictionary structure from get_weather_forecast_data:

    {
      "GSGW0101": {
        "alerts": [],
        "antenna_name": ...,
        "currentConditions": {...},
        "days": [ { "hours": [ ... ] }, ... ],
        "latitude": ...,
        "longitude": ...,
        "timezone": ...
      },
      "GSGW1803": {...},
      ...
    }

    Returns a new dictionary with changes:
    1) top-level => 'station_name'
    2) add 'B_wind_scale' from windspeed
    3) add 'precipitation_scale' from precip
    4) add 'forecast_alert'
    """

    # We'll build a new dictionary. Potentially multiple stations
    # => we can store them in a list or keep them as dict.
    # If your front-end expects a single station, handle accordingly.
    transformed = {}

    for station_code, station_data in raw_weather.items():
        # Build a new top-level structure
        new_station_dict = {}

        # 1) rename station_code -> "station_name"
        # we'll put "station_name": station_code in the new dictionary
        new_station_dict["station_name"] = station_code

        # copy over existing top-level fields you want to keep
        new_station_dict["alerts"] = station_data.get("alerts", [])
        new_station_dict["antenna_name"] = station_data.get("antenna_name")
        new_station_dict["latitude"] = station_data.get("latitude")
        new_station_dict["longitude"] = station_data.get("longitude")
        new_station_dict["timezone"] = station_data.get("timezone")

        # 4) add "forecast_alert" as a placeholder
        new_station_dict["forecast_alert"] = "TODO: fill logic here"

        # For "currentConditions", we can add B_wind_scale and precipitation_scale
        cc = station_data.get("currentConditions", {})
        # if "windspeed" is in km/h
        windspeed = cc.get("windspeed")  # can be float or None
        if windspeed is not None:
            cc["B_wind_scale"] = compute_beaufort_scale(windspeed)

        precip = cc.get("precip")  # mm
        if precip is not None:
            cc["precipitation_scale"] = compute_precip_scale(precip)

        new_station_dict["currentConditions"] = cc

        # For days -> hours
        new_days = []
        for d in station_data.get("days", []):
            # We'll copy day except for hours (transform hours)
            day_copy = dict(d)
            old_hours = day_copy.pop("hours", [])
            new_hours = []
            for hour in old_hours:
                # Insert B_wind_scale
                ws = hour.get("windspeed")
                if ws is not None:
                    b_scale = compute_beaufort_scale(ws)
                    hour["B_wind_scale"] = b_scale
                    hour["B_wind_scale_chinese"] = compute_beaufort_scale_chinese(b_scale)

                # Insert precipitation_scale
                pr = hour.get("precip")
                if pr is not None:
                    hour["precipitation_scale"] = compute_precip_scale(pr)

                new_hours.append(hour)

            day_copy["hours"] = new_hours
            new_days.append(day_copy)

        new_station_dict["days"] = new_days

        # Insert into the final dict
        transformed[station_code] = new_station_dict

    return transformed


def get_weather_forecast_data(post_token_url, post_token_user_name, post_token_password,
                              gateway_station_code_url, gateway_station_location_url,
                              tf1, tf2, gateway_station_name,
                              weather_forecast_url, weather_forecast_key):
    # Handle default timestamps
    current_time_sec = int(time.time())
    if not tf1:
        tf1 = (current_time_sec - 86400)  # 1 day ago
    else:
        tf1 = int(tf1) // 1000  # assuming timestamp in milliseconds

    if not tf2:
        tf2 = (current_time_sec + 86400)  # 1 day ahead
    else:
        tf2 = int(tf2) // 1000

    # Check if gateway_station_name is a list, if yes, convert it to space-separated string
    if isinstance(gateway_station_name, list):
        keyword = ' '.join(gateway_station_name)
    else:
        keyword = gateway_station_name

    # Now call fetch_antennas_lat_lon with the keyword
    antenna_locations = fetch_antennas_lat_lon(
        post_token_url, post_token_user_name, post_token_password,
        gateway_station_code_url, gateway_station_location_url,
        keyword
    )

    if not antenna_locations:
        return {"Error": "No antenna location data found"}

    # For each antenna, query weather forecast
    weather_results = {}
    for antenna_code, antenna_info in antenna_locations.items():
        lat = antenna_info.get("latitude")
        lon = antenna_info.get("longitude")

        if lat is None or lon is None:
            weather_results[antenna_code] = {"Error": "Invalid lat/lon"}
            continue

        # Construct weather URL
        weather_query_url = (
            f"{weather_forecast_url}/{lat},{lon}/{tf1}/{tf2}"
            f"?key={weather_forecast_key}&contentType=json&lang=zh&unitGroup=metric"
        )

        # Query weather data
        try:
            resp = requests.get(weather_query_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Filter required fields
            filtered_days = []
            for day in data.get("days", []):
                filtered_hours = []
                for hour in day.get("hours", []):
                    filtered_hour = {
                        key: hour.get(key)
                        for key in ["cloudcover", "conditions", "datetime", "datetimeEpoch",
                                    "humidity", "icon", "precip", "precipprob", "preciptype",
                                    "severerisk", "temp", "uvindex", "visibility", "winddir",
                                    "windgust", "windspeed", "source"]
                    }
                    filtered_hours.append(filtered_hour)

                day_filtered = {key: day[key] for key in day if key != "hours"}
                day_filtered["hours"] = filtered_hours
                filtered_days.append(day_filtered)

            # Store results
            weather_results[antenna_code] = {
                "antenna_name": antenna_info.get("name"),
                "latitude": lat,
                "longitude": lon,
                "timezone": data.get("timezone"),
                "days": filtered_days,
                "alerts": data.get("alerts"),
                "currentConditions": data.get("currentConditions")
            }

            transform_weather_data(weather_results)

        except requests.RequestException as e:
            weather_results[antenna_code] = {"Error": f"Failed to fetch weather: {e}"}

    return weather_results
