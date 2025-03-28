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


# **Fix the sorting function**
def parse_kp_time(time_str):
    """Handles '24:00' case by converting it to '00:00' of the next day."""
    date_part, time_part = time_str.split(" ")
    if time_part == "24:00":
        # Convert '24:00' to '00:00' of the next day
        date_obj = datetime.strptime(date_part, "%Y-%m-%d") + timedelta(days=1)
        return datetime.strptime(date_obj.strftime("%Y-%m-%d") + " 00:00", "%Y-%m-%d %H:%M")
    else:
        # Normal case
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M")


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

        Kp_observe = json.loads(Kp_value["observe"])

        # **Find the max Kp value**
        Kp_values = [int(entry[2]) for entry in Kp_observe if entry[2].isdigit()]
        Kp_value_max = max(Kp_values, default="null")

        # **Get all occurrences of max Kp value**
        max_occurrences = [entry for entry in Kp_observe if int(entry[2]) == Kp_value_max]

        # **Modify the sorting function**
        if max_occurrences:
            max_occurrences_sorted = sorted(max_occurrences, key=lambda x: parse_kp_time(x[1]))
            Kp_value_max_time = max_occurrences_sorted[-1][1]  # Get latest max occurrence
        else:
            Kp_value_max_time = "null"

        # **Find the nearest Kp value**
        Kp_value_nearest = Kp_observe[-1][2] if Kp_observe else "null"

        # **Final Output**
        Kp_final = {
            "nearest": Kp_value_nearest,
            "nearest_time": Kp_observe[-1][1] if Kp_observe else "null",
            "max": Kp_value_max,
            "max_time": Kp_value_max_time  # Time of max Kp occurrence
        }

        return {
            "F107": F10point7_value,
            "ApIndex": ApIndex_value,
            "KpIndex": Kp_final
        }

    except Exception as e:
        print(f"Critical failure in space_weather_forecast: {str(e)}")
        return "sepc down"


# def space_weather_data_raw(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex):
#
#     # Convert tf1 and tf2 to YYYYMMDD format
#     start_date = datetime.utcfromtimestamp(int(tf1) / 1000).strftime('%Y%m%d')
#     end_date = datetime.utcfromtimestamp(int(tf2) / 1000).strftime('%Y%m%d')
#
#     adjusted_predict_start_timestamp = (int(tf1) / 1000)
#     start_date_predict = datetime.utcfromtimestamp(adjusted_predict_start_timestamp).strftime('%Y%m%d')
#
#     adjusted_real_start_timestamp = (int(tf1) / 1000) + (16 * 86400)
#     start_date_real = datetime.utcfromtimestamp(adjusted_real_start_timestamp).strftime('%Y%m%d')
#
#     # Construct API URLs
#     F107url_getpredict = f"{get_F10point7}?starttime={start_date_predict}&sid=0.6115449414235199"
#     F107url_getyesterdayreal = f"{get_F10point7}?starttime={start_date_real}&sid=0.6115449414235199"
#     Apurl_getpredict = f"{get_ApIndex}?starttime={start_date_predict}&sid=0.28182909407741774"
#     Apurl_getyesterdayreal = f"{get_ApIndex}?starttime={start_date_real}&sid=0.28182909407741774"
#     Kpurl = f"{get_KpIndex}?starttime={start_date}&endtime={end_date}&sid=0.575286767183163"
#     print(F107url_getpredict)
#     print(F107url_getyesterdayreal)
#     print(Apurl_getpredict)
#     print(Apurl_getyesterdayreal)
#     print(Kpurl)
#
#     try:
#         # Fetch real and predicted F10.7 values
#         F107_real = fetch_f107_index(F107url_getyesterdayreal)
#         F107_predict = fetch_f107_index(F107url_getpredict)
#
#         # Extract and merge F10.7 values
#         F107_xaxis_real = json.loads(F107_real["xaxis"])
#         F107_real_values = json.loads(F107_real["realvalue"])
#         F107_xaxis_pred = json.loads(F107_predict["xaxis"])
#         F107_predicted_values = json.loads(F107_predict["futurevalue"])
#
#         F107_merged = []
#         for i in range(len(F107_xaxis_real)):
#             date = F107_xaxis_real[i]
#             real_value = F107_real_values[i] if F107_real_values[i] != "null" else None
#
#             yesterday_index = i - 1 if i > 0 else None
#             yesterday_real = (
#                 F107_real_values[yesterday_index] if yesterday_index is not None and F107_real_values[yesterday_index] != "null"
#                 else None
#             )
#
#             try:
#                 pred_index = F107_xaxis_pred.index(date)
#                 predicted_value = F107_predicted_values[pred_index] if F107_predicted_values[pred_index] != "null" else None
#             except ValueError:
#                 predicted_value = None
#
#             merged_value = real_value if real_value is not None else yesterday_real if yesterday_real is not None else predicted_value
#             F107_merged.append(merged_value)
#
#         F10point7_value = {
#             "xaxis": json.dumps(F107_xaxis_real),
#             "value": json.dumps(F107_merged)
#         }
#
#         # Fetch real and predicted ApIndex values
#         Ap_real = fetch_ap_index(Apurl_getyesterdayreal)
#         Ap_predict = fetch_ap_index(Apurl_getpredict)
#
#         # Merge ApIndex values
#         Ap_xaxis_real = json.loads(Ap_real["xaxis"])
#         Ap_real_values = json.loads(Ap_real["realvalue"])
#         Ap_predicted_values = json.loads(Ap_predict["futurevalue"])
#
#         Ap_merged = []
#         for i, date in enumerate(Ap_xaxis_real):
#             real_value = Ap_real_values[i] if Ap_real_values[i] != "null" else None
#             pred_value = Ap_predicted_values[i] if i < len(Ap_predicted_values) and Ap_predicted_values[i] != "null" else None
#             merged_value = real_value if real_value is not None else pred_value
#             Ap_merged.append(merged_value)
#
#         ApIndex_value = {
#             "xaxis": json.dumps(Ap_xaxis_real),
#             "value": json.dumps(Ap_merged)
#         }
#
#         # Fetch Kp values
#         Kp_value = fetch_kp_index(Kpurl)
#         Kp_observe = json.loads(Kp_value["observe"])
#
#         # Prepare complete Kp data
#         Kp_complete = [{"time": entry[1], "value": entry[2]} for entry in Kp_observe]
#
#         return {
#             "F107": F10point7_value,
#             "ApIndex": ApIndex_value,
#             "KpIndex": Kp_complete
#         }
#
#     except Exception as e:
#         print(f"Critical failure in space_weather_forecast: {str(e)}")
#         return "sepc down"

def space_weather_data_raw(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex):
    """
    Returns separate observed (real) and predicted data for F10.7 and Ap, plus full Kp list.
    No merging logic -- the user decides how to combine or pivot them.
    """
    try:
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

        # 1) F10.7 Observed (Real)
        F107_obs = fetch_f107_index(F107url_getyesterdayreal)
        # Observed = { "xaxis": str, "realvalue": str, "futurevalue": str } => We'll store realvalue in 'observed'
        # Example: { "xaxis":"[...]", "realvalue":"[...]", "futurevalue":"[...]" }

        # 2) F10.7 Predicted
        F107_pred = fetch_f107_index(F107url_getpredict)
        # We'll store 'futurevalue' in 'predicted'

        # 3) Ap Observed (Real)
        Ap_obs = fetch_ap_index(Apurl_getyesterdayreal)

        # 4) Ap Predicted
        Ap_pred = fetch_ap_index(Apurl_getpredict)

        # 5) Kp All
        Kp_value = fetch_kp_index(Kpurl)
        Kp_observe = json.loads(Kp_value["observe"])  # e.g. [ [...], [...], ... ]
        # Convert to list of dict
        Kp_list = [{"time": entry[1], "value": entry[2]} for entry in Kp_observe]

        return {
            "F107": {
                "observed": {
                    "xaxis": F107_obs["xaxis"],
                    "value": F107_obs["realvalue"]  # or "futurevalue" as "maybe partial observed"
                },
                "predicted": {
                    "xaxis": F107_pred["xaxis"],
                    "value": F107_pred["futurevalue"]
                }
            },
            "ApIndex": {
                "observed": {
                    "xaxis": Ap_obs["xaxis"],
                    "value": Ap_obs["realvalue"]
                },
                "predicted": {
                    "xaxis": Ap_pred["xaxis"],
                    "value": Ap_pred["futurevalue"]
                }
            },
            "KpIndex": Kp_list
        }

    except Exception as e:
        print(f"Error in space_weather_data_raw: {e}")
        return "sepc down"
