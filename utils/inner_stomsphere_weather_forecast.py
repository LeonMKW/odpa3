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
    transformed = {}

    for station_code, station_data in raw_weather.items():
        new_station_dict = {
            "station_name": station_code,
            "alerts": {"wind": [], "rain": []},
            "antenna_name": station_data.get("antenna_name"),
            "latitude": station_data.get("latitude"),
            "longitude": station_data.get("longitude"),
            "timezone": station_data.get("timezone"),
        }

        # Process current conditions
        cc = station_data.get("currentConditions", {})
        windspeed = cc.get("windspeed")
        if windspeed is not None:
            cc["B_wind_scale"] = compute_beaufort_scale(windspeed)
            cc["B_wind_scale_chinese"] = compute_beaufort_scale_chinese(cc["B_wind_scale"])

        precip = cc.get("precip")
        if precip is not None:
            cc["precipitation_scale"] = compute_precip_scale(precip)

        new_station_dict["currentConditions"] = cc

        # Initialize days
        new_days = []
        for d in station_data.get("days", []):
            day_copy = dict(d)
            old_hours = day_copy.pop("hours", [])
            new_hours = []

            for hour in old_hours:
                hour_dt = f"{d.get('datetime')} {hour.get('datetime')}"
                ws = hour.get("windspeed")
                pr = hour.get("precip")

                if ws is not None:
                    b_scale = compute_beaufort_scale(ws)
                    hour["B_wind_scale"] = b_scale
                    hour["B_wind_scale_chinese"] = compute_beaufort_scale_chinese(b_scale)

                    if 6 <= b_scale <= 7:
                        new_station_dict["alerts"]["wind"].append(f"{hour_dt}: 6-7级风力预警")
                    elif 8 <= b_scale <= 9:
                        new_station_dict["alerts"]["wind"].append(f"{hour_dt}: 8-9级风力预警")
                    elif b_scale >= 10:
                        new_station_dict["alerts"]["wind"].append(f"{hour_dt}: 10+级风力预警")

                if pr is not None:
                    hour["precipitation_scale"] = compute_precip_scale(pr)

                    if pr > 100:
                        new_station_dict["alerts"]["rain"].append(f"{hour_dt}: 特大暴雨预警")
                    elif pr > 50:
                        new_station_dict["alerts"]["rain"].append(f"{hour_dt}: 大雨预警")
                    elif pr > 25:
                        new_station_dict["alerts"]["rain"].append(f"{hour_dt}: 中雨预警")

                new_hours.append(hour)

            day_copy["hours"] = new_hours
            new_days.append(day_copy)

        new_station_dict["days"] = new_days

        # Assign to transformed dictionary
        transformed[station_code] = new_station_dict

    return transformed


def parse_timestamp_to_ms(value):
    """
    Attempts to parse 'value' into an integer millisecond timestamp.
    Accepts either:
      - A numeric string (already milliseconds),
      - An ISO8601 string like '2025-04-07T10:25:43.000Z',
      - An int/float.
    Returns an integer (milliseconds).
    """
    if value is None:
        return None

    # If it's already an integer or float, just return int(value).
    if isinstance(value, (int, float)):
        return int(value)

    # If it's a string that looks purely numeric, parse as integer.
    # e.g. '1744020925000'
    stripped = str(value).strip()
    if stripped.isdigit():
        return int(stripped)

    # Otherwise, assume it's an ISO8601 date like "2025-04-07T10:25:43.000Z".
    # Convert to a datetime, then to Unix ms.
    dt_obj = datetime.strptime(stripped, '%Y-%m-%dT%H:%M:%S.%fZ')
    dt_utc = dt_obj.replace(tzinfo=pytz.UTC)
    return int(dt_utc.timestamp() * 1000)


def get_gateway_task(post_token_url,
                     post_token_user_name,
                     post_token_password, gateway_tasks_url, start, end):
    # print(f"gatewayStart: {start}, End: {end}")

    # No need to convert start and end to datetime objects; they are already in milliseconds
    ts1 = int(start)  # Start time in milliseconds
    ts2 = int(end)  # End time in milliseconds

    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    headers = {
        # 'x-web-token': 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEifQ.eyJpZCI6MTE3Mywic3ViIjoiOSIsImF1ZCI6IjgiLCJleHAiOjE3NDgwNzUwMDksImlhdCI6MTc0Mjg5MTAwOX0.HXNnCaWVIsF9D1hxlwgqnOy03OHxPed09G12qiZXug2oYKwvyv6ADTVTAEd2e1i1-qtve179oomF8CEWsayQag',
        'x-web-token': token,
        'Content-Type': 'application/json'  # Explicitly specify JSON format
    }

    payload = {
        "startAt": ts1,
        "endAt": ts2,
        "spacecraftIds": [],
        "antennaIDs": [],
        "taskType": ["COMMUNICATION"]
    }

    response = requests.post(gateway_tasks_url, headers=headers, json=payload)
    return response


def get_weather_forecast_data(post_token_url, post_token_user_name, post_token_password,
                              gateway_station_code_url, gateway_station_location_url,
                              tf1, tf2, gateway_station_name,
                              weather_forecast_url, weather_forecast_key,
                              gateway_tasks_url):
    # Handle default timestamps
    current_time_sec = int(time.time())
    if not tf1:
        tf1_ms = current_time_sec * 1000  # "now" in ms
    else:
        tf1_ms = parse_timestamp_to_ms(tf1)  # convert whatever user gave us to ms

    if not tf2:
        tf2_ms = (current_time_sec + 86400) * 1000  # "tomorrow" in ms
    else:
        tf2_ms = parse_timestamp_to_ms(tf2)  # convert user input to ms

    # Convert ms -> seconds for the weather API URL, if that API expects seconds
    # (Your code showed dividing by 1000).
    tf1_sec = tf1_ms // 1000
    tf2_sec = tf2_ms // 1000

    # If gateway_station_name is a list, join into a space-separated string
    if isinstance(gateway_station_name, list):
        keyword = ' '.join(gateway_station_name)
    else:
        keyword = gateway_station_name

    # Now call fetch_antennas_lat_lon
    antenna_locations = fetch_antennas_lat_lon(
        post_token_url, post_token_user_name, post_token_password,
        gateway_station_code_url, gateway_station_location_url,
        keyword
    )
    if not antenna_locations:
        return {"Error": "No antenna location data found"}

    weather_results = {}
    transformed_data = {}  # define outside the try-block so it's always in scope

    for antenna_code, antenna_info in antenna_locations.items():
        lat = antenna_info.get("latitude")
        lon = antenna_info.get("longitude")

        if lat is None or lon is None:
            weather_results[antenna_code] = {"Error": "Invalid lat/lon"}
            continue

        # Construct weather URL. If the external weather API wants seconds, we pass tf1_sec/tf2_sec
        weather_query_url = (
            f"{weather_forecast_url}/{lat},{lon}/{tf1_sec}/{tf2_sec}"
            f"?key={weather_forecast_key}&contentType=json&lang=zh&unitGroup=metric"
        )

        try:
            resp = requests.get(weather_query_url, timeout=60)
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

            # Transform the data (if needed):
            transformed_data = transform_weather_data(weather_results)

            # Ensure every antenna has these two lists (so they appear even if empty):
            for st_code in transformed_data:
                transformed_data[st_code].setdefault("wind_during_task", [])
                transformed_data[st_code].setdefault("rain_during_task", [])

            # Fetch gateway tasks in the same time range (ms):
            gateway_resp = get_gateway_task(
                post_token_url,
                post_token_user_name,
                post_token_password,
                gateway_tasks_url,
                tf1_ms,  # pass ms
                tf2_ms
            )
            try:
                g_data = gateway_resp.json()
            except Exception:
                g_data = {"code": 999, "data": {"list": []}}

            if g_data.get("code") != 0:
                tasks_list = []
            else:
                tasks_list = g_data.get("data", {}).get("list", [])

            # Cross-reference tasks with wind/rain alerts
            # We'll store them in "wind_during_task" / "rain_during_task"
            # The "code" e.g. "GSGW1803" from tasks -> antenna->code => same as antenna_code
            station_alerts = transformed_data.get(antenna_code, {}).get("alerts", {})
            wind_alerts = station_alerts.get("wind", [])
            rain_alerts = station_alerts.get("rain", [])

            # We define a helper to parse a time string to ms:
            def parse_yyyymmdd_hhmmss_to_ms(dt_str):
                # dt_str e.g. "2025-04-07 03:00:00"
                bj_tz = pytz.timezone("Asia/Shanghai")
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                dt_bj = bj_tz.localize(dt_obj)
                return int(dt_bj.timestamp() * 1000)

            for t in tasks_list:
                station_code = t.get("antenna", {}).get("code")
                if not station_code:
                    continue
                if station_code not in transformed_data:
                    continue

                # Possibly different fields for time
                start_task_ms = parse_timestamp_to_ms(t.get("beginTime") or t.get("startAt"))
                end_task_ms = parse_timestamp_to_ms(t.get("endAt"))

                if not (start_task_ms and end_task_ms):
                    continue

                # If station_code doesn't exist in final 'transformed_data', skip
                if station_code not in transformed_data:
                    continue

                # Ensure we have lists
                if "wind_during_task" not in transformed_data[station_code]:
                    transformed_data[station_code]["wind_during_task"] = []
                if "rain_during_task" not in transformed_data[station_code]:
                    transformed_data[station_code]["rain_during_task"] = []

                # Check wind alerts
                for w_alert in wind_alerts:
                    # e.g. "2025-04-07 03:00:00: 6-7级风力预警"
                    splitted = w_alert.split(": ", maxsplit=1)
                    if len(splitted) < 2:
                        continue
                    time_part = splitted[0]
                    msg_part = splitted[1]
                    alert_time_ms = parse_yyyymmdd_hhmmss_to_ms(time_part)

                    if start_task_ms <= alert_time_ms <= end_task_ms:
                        transformed_data[station_code]["wind_during_task"].append({
                            "time": time_part,
                            "message": msg_part
                        })

                # Check rain alerts
                for r_alert in rain_alerts:
                    splitted = r_alert.split(": ", maxsplit=1)
                    if len(splitted) < 2:
                        continue
                    time_part = splitted[0]
                    msg_part = splitted[1]
                    alert_time_ms = parse_yyyymmdd_hhmmss_to_ms(time_part)

                    if start_task_ms <= alert_time_ms <= end_task_ms:
                        transformed_data[station_code]["rain_during_task"].append({
                            "time": time_part,
                            "message": msg_part
                        })

        except requests.RequestException as e:
            transformed_data[antenna_code] = {"Error": f"Failed to fetch weather: {e}"}

    return transformed_data
