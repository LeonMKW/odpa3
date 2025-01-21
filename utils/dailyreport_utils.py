import logging
import pprint
import json
import pandas as pd
from requests import post
import pytz
from datetime import datetime, timedelta
from utils.db import get_mongo
from dateutil import parser
import requests
import arrow
from utils.authentication import get_header_token

# def obp(cur, satellitecode):
#     # orbit status
#     query_orbit_precision = f"""
#     SELECT *
#     FROM orbit_precision_summary
#     WHERE spacecraft = '{satellitecode}'
#     ORDER BY timestamp DESC
#     LIMIT 1;
#     """
#
#     cur.execute(query_orbit_precision)
#     op = cur.fetchone()
#     obp_df = pd.DataFrame([op])
#     # Drop unnecessary columns
#     obp_df = obp_df[['mse']]
#     return obp_df

# def get_obh(post_token_url,
#             post_token_user_name,
#             post_token_password, mete_data_service, influxdb_orbdata, client_orbdata, satID, start, end):
#     satI = satID.split(",")  # Split the comma-separated satellite IDs into a list
#     all_altitudes = []
#
#     for sat in satI:
#         altitude_df = get_all_altitude(post_token_url,
#                                        post_token_user_name,
#                                        post_token_password, mete_data_service, influxdb_orbdata, client_orbdata, sat,
#                                        start, end)
#         altitude_df['alt'] = round(altitude_df['alt'] / 1000, 3)
#         altitude_df['_satelliteCode'] = altitude_df['_satelliteCode']
#         all_altitudes.append(altitude_df[['alt', '_satelliteCode']])
#
#     # Combine all altitude dataframes into one
#     combined_df = pd.concat(all_altitudes, ignore_index=True)
#     result = combined_df.to_dict(orient='records')  # Convert DataFrame to a list of dictionaries
#
#     return json.dumps(result)
#
#
# def obh(post_token_url,
#         post_token_user_name,
#         post_token_password, mete_data_service, influxdb_orbdata, client_orbdata, satID, start, end):
#     # Assumes start and end are defined here or passed to this function
#     altitude = get_altitude(post_token_url,
#                             post_token_user_name,
#                             post_token_password, mete_data_service, influxdb_orbdata, client_orbdata, satID, start, end)
#     # print(altitude)
#     altitude['alt'] = round(altitude['alt'] / 1000, 3)
#     altitude = altitude[['alt']]
#
#     return altitude
#
#
# def o2pphase(post_token_url,
#              post_token_user_name,
#              post_token_password, mete_data_service, influxdb_orbdata, client_orbdata, satID):
#     phase = get_phase(post_token_url,
#                       post_token_user_name,
#                       post_token_password, mete_data_service, influxdb_orbdata, client_orbdata, satID)
#     phase['phase'] = round(phase['phase'], 3)
#     phase = phase[['phase']]
#     return phase
#
#
# def o2pphase_new(influxdb_orbdata, client_orbdata):
#     phase = get_phase_new(influxdb_orbdata, client_orbdata)
#     phase['phase_diff'] = round(phase['phase_diff'], 3)
#     return phase

