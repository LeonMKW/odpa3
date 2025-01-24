# -*- coding: UTF-8 -*-
import json
from datetime import datetime, timedelta
from json.decoder import JSONDecodeError
import pandas as pd
import requests
import re
import dfply as d
from utils.flightcontrol_utils import tm_table
import pytz
from utils.authentication import get_header_token


def satellite_properties(post_token_url, post_token_user_name, post_token_password, gnss_config, satIDs):
    # Fetch the token
    token = get_header_token(post_token_url, post_token_user_name, post_token_password)

    # Define the headers with the required token
    headers = {
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
    # print(satellite_property)
    # print(ephemeris)
    # Convert the UTC time to a Unix timestamp (milliseconds)
    begin_time = int(datetime.strptime(ephemeris["epochTimeUTC"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
    # Convert to Beijing time (UTC + 8 hours)
    beijing_time = begin_time + 28800 * 1000  # 8 hours * 60 minutes * 60 seconds * 1000 milliseconds
    # Calculate endTime by adding hours (converted to milliseconds) to beginTime
    end_time = beijing_time + hours * 3600 * 1000  # Convert hours to milliseconds

    # Get the Beijing date for the start time
    beijing_date = datetime.utcfromtimestamp(beijing_time / 1000) + timedelta(
        hours=8)  # Convert back to UTC and add 8 hours for Beijing time
    date_str = beijing_date.strftime("%m-%d")  # Format the date as 'MM-DD'

    # Construct the URL for the GET request to the F10.7 API
    url = f"{get_F10point7}?starttime={beijing_date.strftime('%Y%m%d')}&sid=0.6115449414235199"

    # Make the GET request to fetch data
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from F10.7 API: {response.text}")

    # Extract the JSON portion from the HTML response using the first '###' as a separator
    response_text = response.text.split('###')[0]  # Only keep the part before the '###'

    try:
        # Parse the remaining JSON portion
        data = json.loads(response_text)
    except json.JSONDecodeError:
        raise Exception("Failed to decode JSON from the response.")

    # Remove scalar fields like 'min', 'max', 'numDivLines'
    scalar_keys = ['min', 'max', 'numDivLines']
    for key in scalar_keys:
        if key in data:
            del data[key]

    # Now parse the JSON-encoded strings into actual lists
    xaxis = json.loads(data['xaxis'])
    realvalue = json.loads(data['realvalue'])
    futurevalue = json.loads(data['futurevalue'])

    # Convert to DataFrame
    df = pd.DataFrame({
        'xaxis': xaxis,
        'realvalue': realvalue,
        'futurevalue': futurevalue
    })
    # print(df.to_string())
    # Convert 'realvalue' and 'futurevalue' to numeric, setting 'null' as NaN
    df['realvalue'] = pd.to_numeric(df['realvalue'], errors='coerce')
    df['futurevalue'] = pd.to_numeric(df['futurevalue'], errors='coerce')

    # Find the row where the xaxis matches the beijing_date
    date_row = df[df['xaxis'] == date_str]

    # Initialize radiation flow with the default value
    radiation_flow = 73

    if not date_row.empty:
        # Get the realvalue or futurevalue for the matched date
        real_val = date_row['realvalue'].values[0]
        future_val = date_row['futurevalue'].values[0]

        # Determine radiation flow based on the realvalue and futurevalue
        if pd.notna(real_val):
            radiation_flow = int(real_val)
        elif pd.notna(future_val):
            radiation_flow = int(future_val)
    # Construct the orbit calculation body
    return {
        "thrusterForce": 0,
        "firePeriods": [],
        "calcStepInSeconds": 1,
        "radiationFlow": radiation_flow,  # Use the computed radiationFlow value
        "beginTime": beijing_time,  # 13-digit Unix timestamp in milliseconds
        "endTime": end_time,  # 13-digit Unix timestamp in milliseconds
        "satelliteMass": satellite_property["mass"],  # Satellite mass from satellite_od_dict
        "satelliteArea": satellite_property["windwardArea"],  # Satellite surface area
        "orbitElements": {
            "CD": ephemeris["CD"],  # Drag coefficient
            "epochTimeUTC": ephemeris["epochTimeUTC"],  # Orbital epoch in UTC
            "a": ephemeris["a"],  # Semi-major axis
            "e": ephemeris["e"],  # Eccentricity
            "i": ephemeris["i"],  # Inclination
            "dw": ephemeris["dw"],  # Argument of perigee
            "xw": ephemeris["xw"],  # Longitude of ascending node
            "M": ephemeris["M"]  # Mean anomaly
        }
    }


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


# def get_all_altitude(post_token_url,
#                      post_token_user_name,
#                      post_token_password, metedataservice_url, influxdb_orbdata, client_orbdata, satID, start, end):
#     satellite_od_dict = satellite_properties(post_token_url,
#                                              post_token_user_name,
#                                              post_token_password, metedataservice_url, satID)
#     satellitecode = satellite_od_dict['code']
#     tf1 = pd.to_datetime(start).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
#     tf2 = pd.to_datetime(end).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
#
#     # Use the modified function to get data or nearest data
#     points = influxdb_orbdata.get_distinct_alt(client_orbdata, tf1, tf2, satellitecode)
#
#     points_df = pd.DataFrame(points)
#     if len(points_df) == 0:
#         return pd.DataFrame()  # or handle it as needed
#
#     return points_df
#
#
# def get_altitude(post_token_url,
#                  post_token_user_name,
#                  post_token_password, metedataservice_url, influxdb_orbdata, client_orbdata, satID, start, end):
#     satellite_od_dict = satellite_properties(post_token_url,
#                                              post_token_user_name,
#                                              post_token_password, metedataservice_url, satID)
#     satellitecode = satellite_od_dict['code']
#
#     # Ensure the input timestamps are in the correct format
#     tf1 = pd.to_datetime(start).strftime('%Y-%m-%dT%H:%M:%SZ')
#     tf2 = pd.to_datetime(end).strftime('%Y-%m-%dT%H:%M:%SZ')
#
#     # Query data for the current interval
#     points = influxdb_orbdata.get_distinct_alt(client_orbdata, tf1, tf2, satellitecode)
#     points_df = pd.DataFrame(points)
#
#     # Print the DataFrame to check it
#     # print(points_df.to_string())
#
#     return points_df
#
#
# def get_phase(post_token_url,
#               post_token_user_name,
#               post_token_password, metedataservice_url, influxdb_orbdata, client_orbdata, satID):
#     satellite_od_dict = satellite_properties(post_token_url,
#                                              post_token_user_name,
#                                              post_token_password, metedataservice_url, satID)
#     satellitecode = satellite_od_dict['code']
#
#     filters = 'WHERE _satelliteCode = \'' + satellitecode + '\' '
#
#     # Query data for the current interval
#     points = influxdb_orbdata.get_distinct_phase(client_orbdata, filters=filters, limit=1)
#     points_df = pd.DataFrame(points)
#     # 检查points_df是否为空
#     if points_df.empty:
#         points_df = pd.DataFrame({
#             'time': ['0'],
#             'phase': [0],
#             '_satelliteCode': [satellitecode]
#         })
#         return points_df
#     else:
#         return points_df
#
#
# def get_phase_new(influxdb_orbdata, client_orbdata):
#     filter1 = 'WHERE _satelliteCode = \'GS-2 & GS-2AP01\' '
#     filter2 = 'WHERE _satelliteCode = \'GS-2AP01 & GS-2AP02\' '
#     filter3 = 'WHERE _satelliteCode = \'GS-2AP02 & GS-2BP01\' '
#     filter4 = 'WHERE _satelliteCode = \'GS-2BP01 & GS-2AP03\' '
#
#     # Query data for the current interval
#     points1 = influxdb_orbdata.get_distinct_phase_diff(client_orbdata, filters=filter1, limit=1)
#     points2 = influxdb_orbdata.get_distinct_phase_diff(client_orbdata, filters=filter2, limit=1)
#     points3 = influxdb_orbdata.get_distinct_phase_diff(client_orbdata, filters=filter3, limit=1)
#     points4 = influxdb_orbdata.get_distinct_phase_diff(client_orbdata, filters=filter4, limit=1)
#
#     # Convert each result to DataFrame
#     points_df1 = pd.DataFrame(points1)
#     points_df2 = pd.DataFrame(points2)
#     points_df3 = pd.DataFrame(points3)
#     points_df4 = pd.DataFrame(points4)
#
#     # Concatenate all DataFrames into one
#     points_df = pd.concat([points_df1, points_df2, points_df3, points_df4], ignore_index=True)
#
#     # 检查points_df是否为空
#     if points_df.empty:
#         points_df = pd.DataFrame({
#             'time': ['0'],
#             'phase_diff': [0],
#             '_satelliteCode': ['0']
#         })
#
#     return points_df
