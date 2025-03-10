import json
import requests
import pandas as pd
from utils.authentication import get_header_token
import logging
from datetime import datetime
from utils.db import get_mongo
from utils.space_weather_forecast import space_weather_forecast
from utils.od_utils import compute_mean_altitude, calc_alt_diff


def sei_dingtalk_news(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex, satID_list,
                      mean_6element_url, get_calc_result_url):
    # Ensure tf1 and tf2 are integers
    tf1 = int(tf1)
    tf2 = int(tf2)

    mongo = get_mongo()
    satIDs = satID_list.split(",")

    # 1 Fetch Space Environment Data
    space_env_data = space_weather_forecast(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex)
    if space_env_data == "sepc down":
        return {"Error": "Failed to fetch space environment data"}

    # print(space_env_data)

    # 2 Fetch Satellite Data from MongoDB (Closest Record Not Less Than tf1)
    satellite_data = []
    for satID in satIDs:
        closest_cursor = mongo.get_doc_closest_but_not_less("ephemeris_pa", satID, tf1 // 1000)

        # Ensure all documents are added (not just one satellite)
        closest_records = list(closest_cursor)  # Convert cursor to list

        if closest_records:  # Append all found records
            satellite_data.extend(closest_records)

    # print(satellite_data)

    # 3 Fetch Satellite Data from MongoDB (Closest Record Not Less Than tf1)
    ma = compute_mean_altitude(satellite_data, mean_6element_url, get_calc_result_url)
    # print(ma)
    # 4 altitude change
    ad = calc_alt_diff(satellite_data, mean_6element_url, get_calc_result_url, alt_change_time=12)
    # print(ad)

    # Format the Data for DingTalk
    # report_content = format_sei_report(space_env_data, satellite_data, altitude_data)

    return space_env_data, satellite_data, ma, ad
