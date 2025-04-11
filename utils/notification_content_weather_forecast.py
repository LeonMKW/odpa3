import time
from datetime import datetime, timedelta
import re
import pytz
from utils.dailyreport_utils import sei_dingtalk_news, space_environment_only
from utils.space_weather_forecast import space_weather_data_raw
from utils.od_utils import satellite_codes
import requests
import os
from utils.inner_stomsphere_weather_forecast import get_weather_forecast_data
from utils.inner_atomsphere_report_generate import create_weather_forecast_pdf


# Helper Functions
def parse_alert_datetime_and_beaufort(alert_string):
    """
    Example:
      "2025-04-11 00:00:00: 阵风级别达到6级(强风)预警"
    Returns (dt_obj, beaufort_scale, msg_part).
    """
    parts = alert_string.split(": ", maxsplit=1)
    if len(parts) < 2:
        return None, None, alert_string  # fallback

    time_part, msg_part = parts[0], parts[1]
    bj_tz = pytz.timezone("Asia/Shanghai")
    dt_obj = datetime.strptime(time_part, "%Y-%m-%d %H:%M:%S")
    dt_obj = bj_tz.localize(dt_obj)

    match = re.search(r'达到(\d+)级', msg_part)
    if match:
        try:
            beaufort_scale = int(match.group(1))
        except ValueError:
            beaufort_scale = None
    else:
        beaufort_scale = None

    return dt_obj, beaufort_scale, msg_part


def group_consecutive_hour_alerts_per_station(alert_strings, station_code):
    """
    For a single station, e.g. alert_strings:
      ["2025-04-11 00:00:00: 阵风级别达到6级(强风)预警",
       "2025-04-11 01:00:00: 阵风级别达到6级(强风)预警",
       ... ]
    Return a single line summarizing consecutive hours, e.g.:
      "GSGW0101 => 2025-04-11 00:00:00 - 2025-04-11 02:00:00, 最高阵风级别达到6级(强风)预警; 2025-04-11 18:00:00 - 2025-04-13 23:00:00, 最高阵风级别达到10级(狂风)预警"

    If no alerts => returns None.
    """
    if not alert_strings:
        return None

    # parse each
    parsed = []
    for alert_str in alert_strings:
        dt_obj, scale, msg = parse_alert_datetime_and_beaufort(alert_str)
        if dt_obj is not None:
            parsed.append((dt_obj, scale, msg))

    if not parsed:
        return None

    parsed.sort(key=lambda x: x[0])
    groups = []
    current_group = [parsed[0]]
    for i in range(1, len(parsed)):
        dt_obj, scale, msg = parsed[i]
        prev_dt, prev_scale, prev_msg = parsed[i-1]
        # if exactly +1 hour
        if dt_obj - prev_dt == timedelta(hours=1):
            current_group.append((dt_obj, scale, msg))
        else:
            groups.append(current_group)
            current_group = [(dt_obj, scale, msg)]
    if current_group:
        groups.append(current_group)

    bj_format = "%Y-%m-%d %H:%M:%S"
    group_strings = []
    for grp in groups:
        start_dt = grp[0][0]
        end_dt = grp[-1][0]
        # find max scale
        max_scale = None
        max_msg = None
        for (dt_obj, scale, msg) in grp:
            if scale is not None and (max_scale is None or scale > max_scale):
                max_scale = scale
                max_msg = msg

        start_str = start_dt.strftime(bj_format)
        end_str = end_dt.strftime(bj_format)

        if len(grp) == 1:
            # single hour
            line = f"{station_code} => {start_str}, {grp[0][2]}"
        else:
            if max_msg:
                line = f"{station_code} => {start_str} - {end_str}, 最高{max_msg}"
            else:
                line = f"{station_code} => {start_str} - {end_str}, {grp[0][2]}"
        group_strings.append(line)

    return "; ".join(group_strings)


def create_tidy_windgust_alerts(weather_data):
    """
    Groups wind gust alerts station-by-station, returning
    a single string with newlines separating station lines.
    Example:
      "阵风预警:
       GSGW0101 => 2025-04-11 00:00:00 - 2025-04-13 23:00:00, 最高阵风级别达到10级(狂风)预警
       BYGW01 => 2025-04-12 04:00:00 - 2025-04-12 05:00:00, 最高阵风级别达到8级(大风)预警"
    """
    lines = []
    for station_code, station_data in weather_data.items():
        windgust_list = station_data.get("alerts", {}).get("windgust", [])
        if not windgust_list:
            continue
        grouped = group_consecutive_hour_alerts_per_station(windgust_list, station_code)
        if grouped:
            lines.append(grouped)

    if not lines:
        return "无预警"

    return f"阵风预警:\n" + "\n".join(lines)


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

    # 2) Prepare output folder ...
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    output_folder = os.path.join(project_root, "data")
    os.makedirs(output_folder, exist_ok=True)

    # 3) Generate local PDF name and path
    local_filename = f"inner_atmo_weather_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    local_path = os.path.join(output_folder, local_filename)

    # 4) Build the PDF
    create_weather_forecast_pdf(local_path, weather_data)

    # 5) Upload PDF to OSS
    oss_key_pdf = f"pdf-reports/{local_filename}"
    OSS2.upload_file(oss_key_pdf, local_path)
    report_url = OSS2.make_url(oss_key_pdf)

    # (Optionally remove local file)
    os.remove(local_path)

    # 6) We can still accumulate windspeed_alerts_agg, rain_alerts_agg, etc. if we want
    windspeed_alerts_agg = []
    rain_alerts_agg = []
    windspeed_during_task_agg = []
    windgust_during_task_agg = []
    rain_during_task_agg = []

    for station_code, station_data in weather_data.items():
        alerts_dict = station_data.get("alerts", {})
        windspeed_list = alerts_dict.get("windspeed", [])
        rain_list = alerts_dict.get("rain", [])

        windspeed_alerts_agg.extend(windspeed_list)
        rain_alerts_agg.extend(rain_list)

        # "during-task" arrays
        wsduring = station_data.get("windspeed_during_task", [])
        wgdt = station_data.get("windgust_during_task", [])
        rdt = station_data.get("rain_during_task", [])

        for ws_item in wsduring:
            windspeed_during_task_agg.append(f"{station_code} => {ws_item['time']}: {ws_item['message']}")
        for wg_item in wgdt:
            windgust_during_task_agg.append(f"{station_code} => {wg_item['time']}: {wg_item['message']}")
        for r_item in rdt:
            rain_during_task_agg.append(f"{station_code} => {r_item['time']}: {r_item['message']}")

    # *** The new place to produce the TIDY wind gust alerts: ***
    wind_gust_alerts_param = create_tidy_windgust_alerts(weather_data)

    # Provide default "无预警" if other aggregated lists are empty
    windspeed_alerts_param = windspeed_alerts_agg if windspeed_alerts_agg else "无预警"
    rain_alerts_param = rain_alerts_agg if rain_alerts_agg else "无预警"
    windspeed_during_task_param = windspeed_during_task_agg if windspeed_during_task_agg else "无预警"
    windgust_during_task_param = windgust_during_task_agg if windgust_during_task_agg else "无预警"
    rain_during_task_param = rain_during_task_agg if rain_during_task_agg else "无预警"

    # 7) Determine time-of-day
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

    # 8) Build final payload
    payload = {
        "System": "odpa3",
        "NoticeCode": "gs_weather_forecast_pdf",
        "type": "action_card",
        "Param": {
            "reportlink": report_url,
            "windspeed_alerts": windspeed_alerts_param,
            "wind_gust_alerts": wind_gust_alerts_param,  # This is the new tidy version
            "rain_alerts": rain_alerts_param,
            "windspeed_during_task": windspeed_during_task_param,
            "windgust_during_task": windgust_during_task_param,
            "rain_during_task": rain_during_task_param,
            "time_report": time_report_str,
            "timeofday": timeofday,
            "timeofdayoneword": timeofdayoneword
        }
    }

    # 9) Post
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

