# -*- coding: UTF-8 -*-
import pandas as pd
import requests
import dfply as d
from datetime import datetime
from utils.authentication import get_header_token


def lenz(df):
    return len(df) == 0


def tm_table(post_token_url,
             post_token_user_name,
             post_token_password, metedataservice_url, satIDs):
    # Update the URL to include the new path
    metedataserviceurl = metedataservice_url + '/v2/api/openapi-transform/get-all-spacecraft'

    token = get_header_token(post_token_url,
                             post_token_user_name,
                             post_token_password)

    # Define the headers with the required token
    headers = {
        'x-web-token': token
    }

    query2 = """
    query{
        getAllSpacecraft{
        id
        code
        label: name
        tctmVersion
        }
    }
    """

    # Make the POST request with the updated URL and headers
    res = requests.post(url=metedataserviceurl, json={"query": query2}, headers=headers)
    # print(res.json())
    res.raise_for_status()  # Ensure the request was successful
    all_info = res.json()["data"]["getAllSpacecraft"]
    sat_ID_code = {}
    for i in range(0, len(all_info)):
        if all_info[i]['id'] in satIDs:
            sat_ID_code[all_info[i]['id']] = {"code": all_info[i]['code'],
                                              "tm_version": 'tm_all_' + all_info[i]["tctmVersion"]}
    for key in sat_ID_code:
        if key == '1':
            sat_ID_code[key]['tm_version'] = 'tm_all'
            break

    return sat_ID_code


# def electric_propulsion(post_token_url,
#                         post_token_user_name,
#                         post_token_password, metedataservice_url, _influxdb, client, tf1, tf2, satID):
#     tm = tm_table(post_token_url,
#                   post_token_user_name,
#                   post_token_password, metedataservice_url, satID)
#     satelliteCode = tm[satID]['code']
#     tmversion = tm[satID]['tm_version']
#
#     # Convert the input timestamps to datetime objects
#     tf1 = pd.to_datetime(tf1)
#     tf2 = pd.to_datetime(tf2)
#
#     # Initialize an empty DataFrame to store the results
#     result_df = pd.DataFrame()
#
#     # Query data in 10-day intervals
#     interval = pd.DateOffset(days=7)
#     current_start = tf1
#     while current_start <= tf2:
#         current_end = current_start + interval
#
#         # Ensure the end timestamp does not exceed tf2
#         if current_end > tf2:
#             current_end = tf2
#
#         filters = 'where _satelliteCode = \'' + satelliteCode + '\' AND time >= \'' + \
#                   current_start.strftime('%Y-%m-%dT%H:%M:%SZ') + '\' AND time <= \'' + \
#                   current_end.strftime('%Y-%m-%dT%H:%M:%SZ') + '\''
#
#         # Query data for the current interval
#         if satID == '1':
#             points = _influxdb.get_all(client, tmversion, ['TMK2629_orbit_thruster_start_milliseconds'], filters,
#                                        limit=1000000)
#             points_df = pd.DataFrame(points)
#             points_df = points_df >> d.rename(electric_propulsion='TMK2629_orbit_thruster_start_milliseconds')
#
#         elif satID == '14':
#             points = _influxdb.get_all(client, tmversion, ['TMK2311'], filters, limit=1000000)
#             points_df = pd.DataFrame(points)
#             points_df = points_df >> d.rename(electric_propulsion='TMK2311')
#
#         else:
#             points = _influxdb.get_all(client, tmversion, ['TMT041'], filters, limit=1000000)
#             points_df = pd.DataFrame(points)
#             points_df = points_df >> d.rename(electric_propulsion='TMT041')
#
#         if not len(points_df):
#             points_df = pd.DataFrame(columns=['time', 'satelliteCode', 'electric_propulsion'])
#         else:
#             points_df['time'] = pd.to_datetime(points_df['time'], format="ISO8601", utc=True)
#
#         # Concatenate the results for the current interval to the result DataFrame
#         result_df = pd.concat([result_df, points_df], ignore_index=True)
#
#         # Move to the next interval
#         current_start = current_end + pd.Timedelta(seconds=1)
#
#     # print(result_df.to_string())
#     # dtype = result_df.dtypes['electric_propulsion']
#     # print(dtype)
#     return result_df
#
#
# def monitor_data(post_token_url,
#                  post_token_user_name,
#                  post_token_password, metedataservice_url, _influxdb_chonograf, client, tf1, tf2, satID):
#     tm = tm_table(post_token_url,
#                   post_token_user_name,
#                   post_token_password, metedataservice_url, satID)
#     satelliteCode = tm[satID]['code']
#
#     # Convert the input timestamps to datetime objects
#     tf1 = pd.to_datetime(tf1)
#     tf2 = pd.to_datetime(tf2)
#
#     # Initialize an empty DataFrame to store the results
#     result_df = pd.DataFrame()
#
#     # Query data in 10-day intervals
#     interval = pd.DateOffset(days=7)
#     current_start = tf1
#     while current_start <= tf2:
#         current_end = current_start + interval
#
#         # Ensure the end timestamp does not exceed tf2
#         if current_end > tf2:
#             current_end = tf2
#
#         filters = 'where satelliteCode = \'' + satelliteCode + '\' AND time >= \'' + \
#                   current_start.strftime('%Y-%m-%dT%H:%M:%SZ') + '\' AND time <= \'' + \
#                   current_end.strftime('%Y-%m-%dT%H:%M:%SZ') + '\''
#
#         # Query data for the current interval
#         points = _influxdb_chonograf.get_all_monitors(client, 'monitors', ['value'], filters, limit=1000000)
#         points_df = pd.DataFrame(points)
#         points_df = points_df >> d.rename(fire='value')
#
#         if not len(points_df):
#             points_df = pd.DataFrame(columns=['time', 'satelliteCode', 'fire'])
#         else:
#             points_df['time'] = pd.to_datetime(points_df['time'], format="ISO8601", utc=True)
#
#         # Concatenate the results for the current interval to the result DataFrame
#         result_df = pd.concat([result_df, points_df], ignore_index=True)
#
#         # Move to the next interval
#         current_start = current_end + pd.Timedelta(seconds=1)
#
#     # print(result_df.to_string())
#     # dtype = result_df.dtypes['fire']
#     # print(dtype)
#     return result_df
#
#
# def orbit_data(post_token_url,
#                post_token_user_name,
#                post_token_password, metedataservice_url, _influxdb, client, tf1, tf2, satID):
#     tm = tm_table(post_token_url,
#                   post_token_user_name,
#                   post_token_password, metedataservice_url, satID)
#     satelliteCode = tm[satID]['code']
#     tmversion = tm[satID]['tm_version']
#
#     # Convert the input timestamps to datetime objects
#     tf1 = pd.to_datetime(tf1)
#     tf2 = pd.to_datetime(tf2)
#
#     # Initialize an empty DataFrame to store the results
#     result_df = pd.DataFrame()
#
#     # Query data in 10-day intervals
#     interval = pd.DateOffset(days=7)
#     current_start = tf1
#     while current_start <= tf2:
#         current_end = current_start + interval
#
#         # Ensure the end timestamp does not exceed tf2
#         if current_end > tf2:
#             current_end = tf2
#
#         filters = 'where _satelliteCode = \'' + satelliteCode + '\' AND time >= \'' + \
#                   current_start.strftime('%Y-%m-%dT%H:%M:%SZ') + '\' AND time <= \'' + \
#                   current_end.strftime('%Y-%m-%dT%H:%M:%SZ') + '\''
#
#         # Query data for the current interval
#         if satID == '1':
#             points = _influxdb.get_all(client, tmversion, ['TMK1050_orbit_elements_now_state'], filters, limit=1000000)
#             points_df = pd.DataFrame(points)
#             points_df = points_df >> d.rename(orbit_stat='TMK1050_orbit_elements_now_state')
#
#         elif satID == '14':
#             points = _influxdb.get_all(client, tmversion, ['TMK108'], filters, limit=1000000)
#             points_df = pd.DataFrame(points)
#             points_df = points_df >> d.rename(orbit_stat='TMK108')
#
#         else:
#             points = _influxdb.get_all(client, tmversion, ['TMK045'], filters, limit=1000000)
#             points_df = pd.DataFrame(points)
#             points_df = points_df >> d.rename(orbit_stat='TMK045')
#
#         if not len(points_df):
#             points_df = pd.DataFrame(columns=['time', 'satelliteCode', 'orbit_stat'])
#         else:
#             points_df['time'] = pd.to_datetime(points_df['time'], format="ISO8601", utc=True)
#
#         # Concatenate the results for the current interval to the result DataFrame
#         result_df = pd.concat([result_df, points_df], ignore_index=True)
#
#         # Move to the next interval
#         current_start = current_end + pd.Timedelta(seconds=1)
#
#     # print(result_df.to_string())
#     return result_df