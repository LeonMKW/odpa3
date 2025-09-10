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


def satellite_properties(post_token_url, post_token_user_name, post_token_password, gnss_config, satIDs):
    # Fetch the token
    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    # Define the headers with the required token
    headers = {
        # 'x-web-token': 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEifQ.eyJpZCI6MTQ4NCwic3ViIjoiOSIsImF1ZCI6IjgiLCJleHAiOjE3NTg4NTQ2NzMsImlhdCI6MTc1MzY3MDY3M30.N7cmpBYMbqbZbyqWuVXRHO4x5VXMlIDx-gmW6bCcOcRVXSak6r0B9fCYAmzeewyAvC_Fy8u1WO-noYxf03ntCw',
        'x-web-token': token,
        'Content-Type': 'application/json'  # Explicitly specify JSON format
    }

    # Prepare the body with the satellite IDs
    body = {"ids": [str(satIDs)]}

    # Make the POST request
    try:
        res = requests.post(url=gnss_config, json=body, headers=headers, timeout=300)
        res.raise_for_status()  # Raise HTTPError for non-200 responses

        # Parse the JSON response
        response = res.json()

        # Extract required fields
        data_list = response["data"]["list"][0]
        gps_config = data_list["config"]["gpsConfig1"]["tmConfig"][0]
        satellite_code = data_list["code"]
        tc_tm_version = data_list["tcTmVersion"]
        mass = data_list.get("mass")  # Get the mass field
        windward_area = data_list.get("windwardArea")  # Get the windwardArea field

        # Process the GPS config
        gps_config.pop("other", None)  # Remove the 'other' key
        gps_config["filterScript"] = gps_config["filterScript"].replace("fields.", "").replace("==", "=")

        # Modify tcTmVersion
        if satellite_code == "GS-1a":
            tc_tm_version = "tm_all"
        else:
            tc_tm_version = f"tm_all_{tc_tm_version}"

        # Combine all processed data into a single dictionary
        satellite_property = {
            "gpsConfig": gps_config,
            "satelliteCode": satellite_code,
            "tcTmVersion": tc_tm_version,
            "mass": mass,
            "windwardArea": windward_area
        }
        # print(satellite_property)
        return satellite_property

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None
    except KeyError as e:
        print(f"KeyError: {e}")
        return None
    except IndexError as e:
        print(f"IndexError: {e}")
        return None


def satellite_codes(post_token_url, post_token_user_name, post_token_password, gnss_config, satIDs):
    # Fetch the token
    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    # Define the headers with the required token
    headers = {
        # 'x-web-token': 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEifQ.eyJpZCI6MTQ4NCwic3ViIjoiOSIsImF1ZCI6IjgiLCJleHAiOjE3NTg4NTQ2NzMsImlhdCI6MTc1MzY3MDY3M30.N7cmpBYMbqbZbyqWuVXRHO4x5VXMlIDx-gmW6bCcOcRVXSak6r0B9fCYAmzeewyAvC_Fy8u1WO-noYxf03ntCw',
        'x-web-token': token,
        'Content-Type': 'application/json'  # Explicitly specify JSON format
    }

    # Ensure satIDs is a list
    if isinstance(satIDs, str):
        satIDs = satIDs.split(",")

    # Prepare the body with the satellite IDs
    body = {"ids": satIDs}

    # Make the POST request
    try:
        res = requests.post(url=gnss_config, json=body, headers=headers, timeout=300)
        res.raise_for_status()  # Raise HTTPError for non-200 responses

        # Parse the JSON response
        response = res.json()

        # Extract only the required fields (code, externalCode, name)
        satellite_list = response.get("data", {}).get("list", [])

        filtered_satellites = [
            {
                "id": sat["id"],
                "code": sat["code"],
                "externalCode": sat["externalCode"],
                "name": sat["name"]
            }
            for sat in satellite_list
        ]

        return filtered_satellites  # Return the filtered list

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None
    except KeyError as e:
        print(f"KeyError: {e}")
        return None
    except IndexError as e:
        print(f"IndexError: {e}")
        return None


def gnss_get_last_12(post_token_url,
                     post_token_user_name,
                     post_token_password, _influxdb, client, satIDs, gnss_config):
    # Fetch the satellite properties
    satellite_od_dict = satellite_properties(post_token_url,
                                             post_token_user_name,
                                             post_token_password,
                                             gnss_config,
                                             satIDs)

    # Extract required fields from satellite_od_dict
    satellite_code = satellite_od_dict['satelliteCode']
    tm_timestamp = satellite_od_dict['gpsConfig']['timestamp']
    tm_valid = satellite_od_dict['gpsConfig']['filterScript']  # Replace '==' with '='

    # Build the filter query
    filter1 = (
        f"where _satelliteCode = '{satellite_code}' AND {tm_valid} "
        f"AND time <= now() - 12h ORDER BY time DESC"
    )

    # Query data for the current interval
    points = _influxdb.get_all(client, satellite_od_dict['tcTmVersion'], [tm_timestamp], filter1, limit=1)
    points_df = pd.DataFrame(points)

    # Extract the last GNSS time
    gnsstime_last = int(points_df[tm_timestamp].iloc[0])
    return gnsstime_last


def ephemeris_acquire(post_token_url,
                      post_token_user_name,
                      post_token_password, startAt, endAt, spacecraftIds, get_ephemeris):
    # Fetch the token
    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    # Define the headers with the required token
    headers = {
        # 'x-web-token': 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjEifQ.eyJpZCI6MTQ4NCwic3ViIjoiOSIsImF1ZCI6IjgiLCJleHAiOjE3NTg4NTQ2NzMsImlhdCI6MTc1MzY3MDY3M30.N7cmpBYMbqbZbyqWuVXRHO4x5VXMlIDx-gmW6bCcOcRVXSak6r0B9fCYAmzeewyAvC_Fy8u1WO-noYxf03ntCw',
        'x-web-token': token,
        'Content-Type': 'application/json'
    }

    # Prepare the payload
    payload = {
        "keyword": "",
        "spacecraftIds": [spacecraftIds],
        "beginTime": startAt,
        "endTime": endAt,
        "page": 1,
        "pageSize": 20,
        "states": [1, 2],
        "order": 6
    }
    # Make the POST request
    try:
        res = requests.post(url=get_ephemeris, json=payload, headers=headers, timeout=300)
        # print(res.text)
        res.raise_for_status()  # Raise an error for HTTP responses not 200

        # Parse the response
        response_data = res.json()["data"]

        # Extract the list of ephemeris data
        ephemeris_list = response_data["list"]

        if len(ephemeris_list) == 0:
            print("No data found for the given criteria.")
            return None

        # Extract the first record
        record = ephemeris_list[0]

        # Flatten nested fields like orbitElements, source, and compare
        orbit_elements = record.pop('orbitElements', {})
        source = record.pop('source', {})
        compare = record.pop('compare', {})

        # Combine all data into a single dictionary
        ephemeris = {
            **record,
            **orbit_elements,
            **source,
            **compare
        }

        # Keep only the required fields
        required_fields = [
            "epochTimeUTC", "a", "e", "i", "dw", "xw", "M", "CD",
            "spacecraftId", "from", "sourceType", "id", "gpsCount", "difference"
        ]
        ephemeris = {key: ephemeris[key] for key in required_fields if key in ephemeris}
        return ephemeris

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return None
    except KeyError as e:
        print(f"KeyError: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def orbitcal_body(satellite_property, ephemeris, get_F10point7, hours=1):
    # Convert the UTC time to a Unix timestamp (milliseconds)
    begin_time = int(datetime.strptime(ephemeris["epochTimeUTC"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
    # Convert to Beijing time (UTC + 8 hours)
    beijing_time = begin_time + 28800 * 1000
    # Calculate endTime by adding hours (converted to milliseconds)
    end_time = beijing_time + hours * 3600 * 1000

    # Get the Beijing date for the start time
    beijing_date = datetime.utcfromtimestamp(beijing_time / 1000) + timedelta(hours=8)
    date_str = beijing_date.strftime("%m-%d")

    # Construct the URL for the GET request to the F10.7 API
    url = f"{get_F10point7}?starttime={beijing_date.strftime('%Y%m%d')}&sid=0.6115449414235199"

    # Make the GET request to fetch data
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from F10.7 API: {response.text}")

    # Extract the JSON portion from the HTML response using the first '###' as a separator
    response_text = response.text.split('###')[0]

    try:
        # Parse the JSON portion
        data = json.loads(response_text)
    except json.JSONDecodeError:
        raise Exception("Failed to decode JSON from the response.")

    # Remove scalar fields like 'min', 'max', 'numDivLines'
    for key in ['min', 'max', 'numDivLines']:
        data.pop(key, None)

    # Parse the JSON-encoded strings into actual lists
    xaxis = json.loads(data['xaxis'])
    realvalue = json.loads(data['realvalue'])
    futurevalue = json.loads(data['futurevalue'])

    # Convert to DataFrame
    df = pd.DataFrame({
        'xaxis': xaxis,
        'realvalue': realvalue,
        'futurevalue': futurevalue
    })
    df['realvalue'] = pd.to_numeric(df['realvalue'], errors='coerce')
    df['futurevalue'] = pd.to_numeric(df['futurevalue'], errors='coerce')

    # Find the row where the xaxis matches the Beijing date (formatted as MM-DD)
    date_row = df[df['xaxis'] == date_str]

    # Initialize radiation flow (F10.7 value) with the default value
    f107 = 73
    if not date_row.empty:
        real_val = date_row['realvalue'].values[0]
        future_val = date_row['futurevalue'].values[0]
        if pd.notna(real_val):
            f107 = int(real_val)
        elif pd.notna(future_val):
            f107 = int(future_val)

    # Construct the orbit calculation body (keeping the format used later on)
    orbit_body = {
        "thrusterForce": 0,
        "firePeriods": [],
        "calcStepInSeconds": 1,
        "radiationFlow": 73,  # This remains constant for the propagation API
        "beginTime": beijing_time,
        "endTime": end_time,
        "satelliteMass": satellite_property["mass"],
        "satelliteArea": satellite_property["windwardArea"],
        "orbitElements": {
            "CD": ephemeris["CD"],
            "epochTimeUTC": ephemeris["epochTimeUTC"],
            "a": ephemeris["a"],
            "e": ephemeris["e"],
            "i": ephemeris["i"],
            "dw": ephemeris["dw"],
            "xw": ephemeris["xw"],
            "M": ephemeris["M"]
        }
    }

    # Return a tuple: (orbit propagation body, computed F10.7 value)
    return orbit_body, f107


def get_gnss_data(satellite_property, ephemeris, _influxdb, client):
    # Extract necessary information from satellite_property and ephemeris
    gps_config = satellite_property['gpsConfig']
    satellite_code = satellite_property['satelliteCode']

    # Get the fields from gpsConfig
    tm_x = gps_config['x']
    tm_y = gps_config['y']
    tm_z = gps_config['z']
    tm_time = gps_config['timestamp']
    tm_valid = gps_config['filterScript']

    # Convert ephemeris epochTimeUTC to timestamp (tf1)
    epoch_time_utc = ephemeris['epochTimeUTC']

    tf1 = datetime.strptime(epoch_time_utc, '%Y-%m-%dT%H:%M:%S.%fZ')
    # tf1_timestamp = int(tf1.timestamp())  # Convert to timestamp

    # Calculate tf2 (12 hours after tf1)
    tf2 = tf1 + timedelta(hours=12)
    tf2_utc = tf2.strftime(
        '%Y-%m-%dT%H:%M:%S.') + f"{tf2.microsecond // 1000:03d}Z"  # Ensuring milliseconds are formatted

    # Build the InfluxDB query filters
    filters = f"where _satelliteCode = '{satellite_code}' AND time >= '{epoch_time_utc}' AND time <= '{tf2_utc}' " \
              f"AND {tm_valid} "

    # Query GNSS data from InfluxDB
    points = _influxdb.get_all(client, satellite_property['tcTmVersion'], [tm_time, tm_x, tm_y, tm_z], filters,
                               limit=86400)
    points_df = pd.DataFrame(points)

    if not len(points_df):
        points_df = pd.DataFrame(columns=['time', '_satelliteCode', 'timestamp', 'x', 'y', 'z'])
    else:
        points_df.columns = ['time', '_satelliteCode', 'timestamp', 'x', 'y', 'z']
    # print([points_df.to_string()])
    return points_df


def compute_mean_altitude(ephemeris_list, mean_6element_url, get_calc_result_url):
    """
    Compute the mean altitude for a list of ephemeris data by querying an external API.

    :param ephemeris_list: List of ephemeris data dictionaries
    :return: List of {spacecraftId, altitude} dictionaries
    :param mean_6element_url: calc mean element from osculating element
    :param get_calc_result_url: get result from calculation


    """

    # API endpoints
    submit_url = mean_6element_url
    result_url = get_calc_result_url

    altitude_data = []

    for ephemeris in ephemeris_list:
        payload = {
            "orbitElements": {
                "epochTimeUTC": ephemeris["epochTimeUTC"],
                "a": ephemeris["a"],
                "e": ephemeris["e"],
                "i": ephemeris["i"],
                "dw": ephemeris["dw"],
                "xw": ephemeris["xw"],
                "M": ephemeris["M"],
                "CD": ephemeris["CD"]
            },
            "version": "v2"
        }

        try:
            # Step 1: Submit the orbit elements
            response = requests.post(submit_url, json=payload, timeout=10)
            response.raise_for_status()  # Raise error for non-200 responses

            response_data = response.json()
            if response_data.get("code") != 0 or "data" not in response_data:
                print(f"Error submitting orbit data for spacecraft {ephemeris['spacecraftId']}: {response_data}")
                continue

            request_id = response_data["data"]["id"]  # Get the ID from response

            # Step 2: Wait 3 seconds before checking result
            time.sleep(2)

            # Step 3: Query result with retry mechanism (Max 3 attempts)
            for attempt in range(3):
                result_payload = {"id": request_id}
                result_response = requests.post(result_url, json=result_payload, timeout=10)
                result_response.raise_for_status()

                result_data = result_response.json()

                # If successful, extract altitude
                if result_data.get("code") == 0 and "data" in result_data:
                    result_content = result_data["data"].get("resultContent", {}).get("results", [])
                    if result_content:
                        altitude = result_content[0].get("altitude", "N/A")
                        altitude_data.append({"spacecraftId": ephemeris["spacecraftId"], "altitude": altitude})
                        break  # Exit loop once we get a valid response

                # If response says "calculation not completed", retry after 3 seconds
                elif result_data.get("code") == 51006:
                    print(f"Retrying {ephemeris['spacecraftId']} (Attempt {attempt + 1}/3): Calculation not complete.")
                    time.sleep(3)
                else:
                    print(f"Error fetching result for spacecraft {ephemeris['spacecraftId']}: {result_data}")
                    break  # Stop retrying if another error occurs

            else:
                # If we exhaust all retries, log failure
                print(f"Failed to get altitude for spacecraft {ephemeris['spacecraftId']} after 3 attempts.")

        except requests.exceptions.RequestException as e:
            print(f"HTTP request failed for spacecraft {ephemeris['spacecraftId']}: {e}")

    return altitude_data


def calc_alt_diff(ephemeris_list, mean_6element_url, get_calc_result_url, alt_change_time=12):
    """
    Calculate the altitude change over a given period for each spacecraft.

    :param ephemeris_list: List of ephemeris data dictionaries
    :param mean_6element_url: URL to compute mean elements
    :param get_calc_result_url: URL to get calculation results
    :param alt_change_time: Time interval (in hours) to compare altitude change (default 12 hours)
    :return: List of {spacecraftId, altitude_change} dictionaries
    """

    mongo = get_mongo()
    previous_ephemeris_list = []

    for ephemeris in ephemeris_list:
        spacecraft_id = ephemeris["spacecraftId"]
        current_timestamp = ephemeris["timestamp"]
        target_timestamp = current_timestamp - (alt_change_time * 3600)  # Convert hours to seconds

        # Query previous ephemeris from MongoDB
        closest_cursor = mongo.get_doc_closest_but_not_greater("ephemeris_pa", spacecraft_id, target_timestamp)
        closest_record = list(closest_cursor)

        if closest_record:
            previous_ephemeris_list.append(closest_record[0])  # Store the previous ephemeris

    if not previous_ephemeris_list:
        print("No previous ephemeris data found.")
        return []

    # Compute mean altitudes for current and previous ephemeris
    current_altitudes = compute_mean_altitude(ephemeris_list, mean_6element_url, get_calc_result_url)
    # print("Current Altitudes:", current_altitudes)

    time.sleep(3)  # Ensure processing time before querying results

    # FIXED: Use `previous_ephemeris_list` instead of `ephemeris_list`
    previous_altitudes = compute_mean_altitude(previous_ephemeris_list, mean_6element_url, get_calc_result_url)
    # print("Previous Altitudes:", previous_altitudes)

    # Create a mapping for easy lookup
    prev_alt_dict = {entry["spacecraftId"]: entry["altitude"] for entry in previous_altitudes}

    alt_diff_list = []

    for entry in current_altitudes:
        spacecraft_id = entry["spacecraftId"]
        current_alt = entry["altitude"]
        previous_alt = prev_alt_dict.get(spacecraft_id, None)

        if previous_alt is not None:
            alt_diff = current_alt - previous_alt
            alt_diff_list.append({"spacecraftId": spacecraft_id, "altitude_change": alt_diff})

    # print("Altitude Changes:", alt_diff_list)
    return alt_diff_list
