import json
import requests
import pandas as pd
from datetime import datetime, timedelta
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

    # Convert tf1 and tf2 to YYYYMMDD format
    start_date = datetime.utcfromtimestamp(int(tf1) / 1000).strftime('%Y%m%d')
    end_date = datetime.utcfromtimestamp(int(tf2) / 1000).strftime('%Y%m%d')

    # Adjust start_date for prediction (-2 days) and real values (+16 days)
    adjusted_predict_start_timestamp = (int(tf1) / 1000) - (0 * 86400)  # -2 days for prediction
    start_date_predict = datetime.utcfromtimestamp(adjusted_predict_start_timestamp).strftime('%Y%m%d')

    adjusted_real_start_timestamp = (int(tf1) / 1000) + (16 * 86400)  # +16 days for real values
    start_date_real = datetime.utcfromtimestamp(adjusted_real_start_timestamp).strftime('%Y%m%d')

    # Construct API URLs
    F107url_getpredict = f"{get_F10point7}?starttime={start_date_predict}&sid=0.6115449414235199"
    F107url_getyesterdayreal = f"{get_F10point7}?starttime={start_date_real}&sid=0.6115449414235199"
    Apurl_getpredict = f"{get_ApIndex}?starttime={start_date_predict}&sid=0.28182909407741774"
    Apurl_getyesterdayreal = f"{get_ApIndex}?starttime={start_date_real}&sid=0.28182909407741774"
    Kpurl = f"{get_KpIndex}?starttime={start_date}&endtime={end_date}&sid=0.575286767183163"

    try:
        # Fetch real and predicted F10.7 values
        F107_real = fetch_f107_index(F107url_getyesterdayreal)
        F107_predict = fetch_f107_index(F107url_getpredict)

        # Extract and merge F10.7 values
        F107_xaxis_real = json.loads(F107_real["xaxis"])
        F107_real_values = json.loads(F107_real["realvalue"])
        F107_xaxis_pred = json.loads(F107_predict["xaxis"])
        F107_predicted_values = json.loads(F107_predict["futurevalue"])

        F107_merged = []
        for i in range(len(F107_xaxis_real)):
            date = F107_xaxis_real[i]
            real_value = F107_real_values[i] if F107_real_values[i] != "null" else None

            yesterday_index = i - 1 if i > 0 else None
            yesterday_real = (
                F107_real_values[yesterday_index] if yesterday_index is not None and F107_real_values[yesterday_index] != "null"
                else None
            )

            try:
                pred_index = F107_xaxis_pred.index(date)
                predicted_value = F107_predicted_values[pred_index] if F107_predicted_values[pred_index] != "null" else None
            except ValueError:
                predicted_value = None

            merged_value = real_value if real_value is not None else yesterday_real if yesterday_real is not None else predicted_value
            F107_merged.append(merged_value)

        F10point7_value = {
            "xaxis": json.dumps(F107_xaxis_real),
            "value": json.dumps(F107_merged)
        }

        # Fetch real and predicted ApIndex values
        Ap_real = fetch_ap_index(Apurl_getyesterdayreal)
        Ap_predict = fetch_ap_index(Apurl_getpredict)

        # Extract and merge ApIndex values
        Ap_xaxis_real = json.loads(Ap_real["xaxis"])
        Ap_real_values = json.loads(Ap_real["realvalue"])
        Ap_xaxis_pred = json.loads(Ap_predict["xaxis"])
        Ap_predicted_values = json.loads(Ap_predict["futurevalue"])

        Ap_merged = []
        for i in range(len(Ap_xaxis_real)):
            date = Ap_xaxis_real[i]
            real_value = Ap_real_values[i] if Ap_real_values[i] != "null" else None

            yesterday_index = i - 1 if i > 0 else None
            yesterday_real = (
                Ap_real_values[yesterday_index] if yesterday_index is not None and Ap_real_values[yesterday_index] != "null"
                else None
            )

            try:
                pred_index = Ap_xaxis_pred.index(date)
                predicted_value = Ap_predicted_values[pred_index] if Ap_predicted_values[pred_index] != "null" else None
            except ValueError:
                predicted_value = None

            merged_value = real_value if real_value is not None else yesterday_real if yesterday_real is not None else predicted_value
            Ap_merged.append(merged_value)

        ApIndex_value = {
            "xaxis": json.dumps(Ap_xaxis_real),
            "value": json.dumps(Ap_merged)
        }

        # Fetch and process Kp values
        Kp_value = fetch_kp_index(Kpurl)
        Kp_observe = json.loads(Kp_value["observe"])

        Kp_value_nearest = Kp_observe[-1][2] if Kp_observe else "null"
        Kp_value_max = max([int(entry[2]) for entry in Kp_observe if entry[2].isdigit()], default="null")

        Kp_final = {
            "nearest": Kp_value_nearest,
            "max": Kp_value_max
        }

        return {
            "F107": F10point7_value,
            "ApIndex": ApIndex_value,
            "KpIndex": Kp_final
        }

    except Exception as e:
        print(f"Critical failure in space_weather_forecast: {str(e)}")
        return "sepc down"
