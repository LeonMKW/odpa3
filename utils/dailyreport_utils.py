import json
import requests
import pandas as pd
from utils.authentication import get_header_token
import logging
from datetime import datetime
from utils.db import get_mongo
from utils.space_weather_forecast import space_weather_forecast
from utils.od_utils import compute_mean_altitude,calc_alt_diff

# def satellite_properties_general(post_token_url, post_token_user_name, post_token_password, metedataservice_url, satIDs):
#
#     # Construct the API URL
#     metedataserviceurl = metedataservice_url + '/v2/api/spacecrafts/detail'
#
#     # Get authentication token
#     token = get_header_token(post_token_url, post_token_user_name, post_token_password)
#
#     # Define headers with the authentication token
#     headers = {
#         'x-web-token': token,
#         'Content-Type': 'application/json'
#     }
#
#     # Convert "2,3" into ["2", "3"]
#     satID_list = satIDs.split(",") if isinstance(satIDs, str) else satIDs
#     payload = {"ids": [str(satID) for satID in satID_list]}  # Convert each ID to string inside a list
#
#     try:
#         # Make the POST request
#         res = requests.post(url=metedataserviceurl, json=payload, headers=headers, timeout=300)
#         res.raise_for_status()  # Raise exception for non-200 responses
#
#         # Parse the JSON response
#         response_data = res.json()
#         sat_data_list = response_data.get("data", {}).get("list", [])
#
#         if not sat_data_list:
#             print("No data found for given satellite IDs.")
#             return {}
#
#         # Dictionary to store results
#         satellite_info = {}
#
#         # Extract 'code' and 'tcTmVersion' for each satellite
#         for sat in sat_data_list:
#             sat_id = str(sat.get("id", "N/A"))  # Convert ID to string for dictionary keys
#             satellite_info[sat_id] = {
#                 "code": sat.get("code", "N/A"),
#                 "tcTmVersion": sat.get("tcTmVersion", "N/A")
#             }
#
#         # print(f"Satellite Properties: {satellite_info}")  # Debugging output
#         return satellite_info
#
#     except requests.exceptions.RequestException as e:
#         print(f"HTTP request failed: {e}")
#         return {}
#
#
# def get_altitude(post_token_url, post_token_user_name, post_token_password,
#                  metedataservice_url, influxdb_orbdata, client_orbdata, satIDs, start, end):
#
#
#     # Fetch all satellite properties in one request
#     satellite_properties_data = satellite_properties_general(post_token_url, post_token_user_name,
#                                                              post_token_password, metedataservice_url, satIDs)
#
#     altitude_data = []
#
#     for satID in satIDs.split(","):  # Ensure we iterate over satellite IDs
#         sat_properties = satellite_properties_data.get(satID)
#
#         if not sat_properties:
#             print(f"Warning: No satellite properties found for {satID}")
#             continue
#
#         satellite_code = sat_properties["code"]  # Get `code` for querying altitude
#
#         # Convert timestamps to UTC format
#         tf1 = pd.to_datetime(start, unit="ms").strftime('%Y-%m-%dT%H:%M:%SZ')
#         tf2 = pd.to_datetime(end, unit="ms").strftime('%Y-%m-%dT%H:%M:%SZ')
#
#         # Query altitude from InfluxDB
#         points = influxdb_orbdata.get_distinct_alt(client_orbdata, tf1, tf2, satellite_code)
#         points_df = pd.DataFrame(points)
#
#         if not points_df.empty:
#             latest_altitude = points_df.iloc[-1].to_dict()  # Get latest altitude data
#             altitude_data.append({"satellite_id": satID, "altitude": latest_altitude})
#
#     return altitude_data


def sei_dingtalk_news(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex, satID_list,
                      mean_6element_url,get_calc_result_url):


    # Ensure tf1 and tf2 are integers
    tf1 = int(tf1)
    tf2 = int(tf2)

    mongo = get_mongo()
    satIDs = satID_list.split(",")

    # 1 Fetch Space Environment Data
    space_env_data = space_weather_forecast(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex)
    if space_env_data == "sepc down":
        return {"Error": "Failed to fetch space environment data"}

    # 2 Fetch Satellite Data from MongoDB (Closest Record Not Less Than tf1)
    satellite_data = []
    for satID in satIDs:
        closest_cursor = mongo.get_doc_closest_but_not_less("ephemeris_pa", satID, tf1 // 1000)

        # Ensure all documents are added (not just one satellite)
        closest_records = list(closest_cursor)  # Convert cursor to list

        if closest_records:  # Append all found records
            satellite_data.extend(closest_records)

    print(satellite_data)

    # 3 Fetch Satellite Data from MongoDB (Closest Record Not Less Than tf1)
    compute_mean_altitude(satellite_data, mean_6element_url, get_calc_result_url)

    # 4 altitude change
    calc_alt_diff(satellite_data, mean_6element_url, get_calc_result_url, alt_change_time=12)


    # Format the Data for DingTalk
    # report_content = format_sei_report(space_env_data, satellite_data, altitude_data)

    return 'report_content'
