import json
import requests
import pandas as pd
from datetime import datetime
import json
import requests


def fetch_ap_index(url):
    """
    Fetch and process Ap Index data from the provided URL.

    :param url: API endpoint to fetch Ap Index data.
    :return: JSON containing 'xaxis', 'futurevalue', and 'realvalue' (without 'max').
    """
    try:
        # Make the GET request
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}: {response.text}")

        # Extract JSON from response before "###"
        response_text = response.text.split("###")[0]
        data = json.loads(response_text)

        # Remove the 'max' field
        data.pop("max", None)

        return data  # Return processed Ap Index data

    except Exception as e:
        return {"Error": f"Failed to process Ap Index data: {str(e)}"}


def fetch_f107_index(url):
    """
    Fetch and process F10.7 Index data from the provided URL.

    :param url: API endpoint to fetch F10.7 data.
    :return: JSON containing 'xaxis', 'futurevalue', and 'realvalue' (without 'min', 'max', 'numDivLines').
    """
    try:
        # Make the GET request
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}: {response.text}")

        # Extract JSON from response before "###"
        response_text = response.text.split("###")[0]
        data = json.loads(response_text)

        # Remove unnecessary fields
        for key in ['min', 'max', 'numDivLines']:
            data.pop(key, None)

        return data  # Return processed F10.7 Index data

    except Exception as e:
        return {"Error": f"Failed to process F10.7 Index data: {str(e)}"}


def fetch_kp_index(url):
    """
    Fetch and process Kp Index data from the provided URL.

    :param url: API endpoint to fetch Kp data.
    :return: JSON containing only 'observe' data.
    """
    try:
        # Make the GET request
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}: {response.text}")

        # Parse the JSON response
        data = response.json()

        # Remove unnecessary fields
        for key in ["subcaption", "bgnday", "endday", "forecast"]:
            data.pop(key, None)

        return data  # Return processed Kp Index data (only "observe")

    except Exception as e:
        return {"Error": f"Failed to process Kp Index data: {str(e)}"}


def space_weather_forecast(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex):
    """
    Fetches space environment data (F10.7, Ap, and Kp indices) for the given time range.

    :param tf1: Start time (13-digit Unix timestamp in milliseconds)
    :param tf2: End time (13-digit Unix timestamp in milliseconds)
    :param get_F10point7: URL to fetch F10.7 data
    :param get_ApIndex: URL to fetch Ap index
    :param get_KpIndex: URL to fetch Kp index
    :return: JSON containing space weather data or "sepc down" if any request fails
    """

    # Convert tf1 and tf2 from Unix timestamp (milliseconds) to YYYYMMDD and MM-DD format
    start_date = datetime.utcfromtimestamp(int(tf1) / 1000).strftime('%Y%m%d')
    end_date = datetime.utcfromtimestamp(int(tf2) / 1000).strftime('%Y%m%d')

    # Construct API URLs dynamically
    F107url = f"{get_F10point7}?starttime={start_date}&sid=0.6115449414235199"
    Apurl = f"{get_ApIndex}?starttime={start_date}&endtime={end_date}&sid=0.28182909407741774"
    Kpurl = f"{get_KpIndex}?starttime={start_date}&endtime={end_date}&sid=0.575286767183163"

    try:
        # Fetch and process data
        F10point7_value = fetch_f107_index(F107url)
        if "Error" in F10point7_value:
            print(f"Error fetching F10.7 Index: {F10point7_value['Error']}")
            return "sepc down"

        Ap_value = fetch_ap_index(Apurl)
        if "Error" in Ap_value:
            print(f"Error fetching Ap Index: {Ap_value['Error']}")
            return "sepc down"

        Kp_value = fetch_kp_index(Kpurl)
        if "Error" in Kp_value:
            print(f"Error fetching Kp Index: {Kp_value['Error']}")
            return "sepc down"

        return {
            "F107": F10point7_value,
            "ApIndex": Ap_value,
            "KpIndex": Kp_value
        }

    except Exception as e:
        print(f"Critical failure in space_weather_forecast: {str(e)}")
        return "sepc down"

