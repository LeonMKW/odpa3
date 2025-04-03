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