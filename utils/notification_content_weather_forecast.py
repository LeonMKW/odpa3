import time
from datetime import datetime
import json
import pytz
from utils.dailyreport_utils import sei_dingtalk_news, space_environment_only
from utils.space_weather_forecast import space_weather_data_raw
from utils.od_utils import satellite_codes
import requests
import os
from utils.inner_stomsphere_weather_forecast import get_weather_forecast_data
from utils.inner_atomsphere_report_generate import create_weather_forecast_pdf


def generate_weather_forecast_report(
        post_token_url,
        post_token_user_name,
        post_token_password,
        gateway_station_code_url,
        gateway_station_location_url,
        weather_forecast_url,
        weather_forecast_key,
        gateway_tasks_url,
        tf1,
        tf2,
        gateway_station_name,
        future_how_many_days
):
    """
    1. Query & transform weather data for each station.
    2. Generate a PDF report summarizing data.
    3. Save the PDF locally to ./data.
    4. Return a success message + local path.
    """

    # 1) Retrieve raw forecast data
    weather_data = get_weather_forecast_data(
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gateway_station_code_url=gateway_station_code_url,
        gateway_station_location_url=gateway_station_location_url,
        weather_forecast_url=weather_forecast_url,
        weather_forecast_key=weather_forecast_key,
        gateway_tasks_url=gateway_tasks_url,
        tf1=tf1,
        tf2=tf2,
        gateway_station_name=gateway_station_name,
        future_how_many_days=future_how_many_days
    )

    # 3) Build a PDF locally
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, "data")
    os.makedirs(output_folder, exist_ok=True)

    # create a filename based on the current time
    filename_local = f"weather_forecast_report_{int(time.time())}.pdf"
    filepath_local = os.path.join(output_folder, filename_local)

    # generate the PDF
    create_weather_forecast_pdf(filepath_local, weather_data)

    return {
        "message": "Weather Forecast Report generated",
        "pdf_local_path": filepath_local
    }


def inner_atmosphere_weather_forecast_report_alicloud(
        post_token_url,
        post_token_user_name,
        post_token_password,
        gateway_station_code_url,
        gateway_station_location_url,
        weather_forecast_url,
        weather_forecast_key,
        gateway_tasks_url,
        tf1,
        tf2,
        gateway_station_name,
        OSS2,
        notification_url,
        future_how_many_days
):
    # 1) Gather all weather data
    weather_data = get_weather_forecast_data(
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gateway_station_code_url=gateway_station_code_url,
        gateway_station_location_url=gateway_station_location_url,
        weather_forecast_url=weather_forecast_url,
        weather_forecast_key=weather_forecast_key,
        gateway_tasks_url=gateway_tasks_url,
        tf1=tf1,
        tf2=tf2,
        gateway_station_name=gateway_station_name,
        future_how_many_days=future_how_many_days
    )

    # 2) Prepare output folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    output_folder = os.path.join(project_root, "data")
    os.makedirs(output_folder, exist_ok=True)

    # 3) Generate local PDF name and path
    local_filename = f"inner_atmo_weather_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    local_path = os.path.join(output_folder, local_filename)

    # 4) Build the PDF using your custom function
    create_weather_forecast_pdf(local_path, weather_data)

    # 5) Upload PDF to OSS
    oss_key_pdf = f"pdf-reports/{local_filename}"
    OSS2.upload_file(oss_key_pdf, local_path)
    report_url = OSS2.make_url(oss_key_pdf)

    # Remove local file if desired
    os.remove(local_path)

    # 6) Collect alerts from weather_data
    wind_alerts_agg = []         # all wind alerts from alerts
    rain_alerts_agg = []         # all rain alerts from alerts
    wind_during_task_agg = []    # all wind alerts during task
    rain_during_task_agg = []    # all rain alerts during task

    for station_code, station_data in weather_data.items():
        alerts_dict = station_data.get("alerts", {})
        wind_list = alerts_dict.get("wind", [])
        rain_list = alerts_dict.get("rain", [])
        wind_alerts_agg.extend(wind_list)
        rain_alerts_agg.extend(rain_list)

        wdt = station_data.get("wind_during_task", [])
        rdt = station_data.get("rain_during_task", [])
        for w_item in wdt:
            # Expected w_item is a dict with "time" and "message"
            wind_during_task_agg.append(f"{station_code} => {w_item['time']}: {w_item['message']}")
        for r_item in rdt:
            rain_during_task_agg.append(f"{station_code} => {r_item['time']}: {r_item['message']}")

    # Provide default "无预警" if any aggregated list is empty.
    wind_alerts_param = wind_alerts_agg if wind_alerts_agg else "无预警"
    rain_alerts_param = rain_alerts_agg if rain_alerts_agg else "无预警"
    wind_during_task_param = wind_during_task_agg if wind_during_task_agg else "无预警"
    rain_during_task_param = rain_during_task_agg if rain_during_task_agg else "无预警"

    # 7) Determine the current time in Asia/Shanghai and deduce time-of-day info
    current_timestamp = int(time.time())
    shanghai_tz = pytz.timezone('Asia/Shanghai')
    time_reported_datetime = datetime.fromtimestamp(current_timestamp, shanghai_tz)
    time_report_str = time_reported_datetime.strftime("%Y-%m-%d %H:%M:%S")
    hour = time_reported_datetime.hour

    if 0 <= hour < 12:
        timeofday = "早报"
        timeofdayoneword = "早上"
    elif 12 <= hour < 24:
        timeofday = "晚报"
        timeofdayoneword = "晚上"
    else:
        timeofday = "日报"
        timeofdayoneword = ""

    # 8) Prepare DingTalk-like payload with additional alert and time fields
    payload = {
        "System": "odpa3",
        "NoticeCode": "gs_weather_forecast_pdf",
        "type": "action_card",
        "Param": {
            "reportlink": report_url,
            "wind_alerts": wind_alerts_param,
            "rain_alerts": rain_alerts_param,
            "wind_during_task": wind_during_task_param,
            "rain_during_task": rain_during_task_param,
            "time_report": time_report_str,
            "timeofday": timeofday,
            "timeofdayoneword": timeofdayoneword
        }
    }

    # 9) Send the notification
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(notification_url, json=payload, headers=headers, timeout=300)
        if response.status_code == 200:
            print("DingTalk (action_card) notification posted successfully.")
        else:
            print(f"Failed to post notification! Status={response.status_code}, Resp={response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending DingTalk notification: {e}")

    return f"PDF created and uploaded => {report_url}"
