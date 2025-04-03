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


def filter_hours_fields(data):
    allowed_fields = {
        "cloudcover", "conditions", "datetime", "datetimeEpoch", "humidity", "icon",
        "precip", "precipprob", "preciptype", "severerisk", "temp", "uvindex",
        "visibility", "winddir", "windgust", "windspeed", "source"
    }

    days = data.get("days", [])
    for day in days:
        hours = day.get("hours", [])
        filtered_hours = []
        for hour in hours:
            # Pick out only allowed fields
            filtered_hour = {
                key: hour[key]
                for key in allowed_fields
                if key in hour
            }
            filtered_hours.append(filtered_hour)
        # Replace the original hours with the filtered hours
        day["hours"] = filtered_hours
    return data


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

        except requests.RequestException as e:
            weather_results[antenna_code] = {"Error": f"Failed to fetch weather: {e}"}

    return weather_results