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
    gateway_station_name
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
        gateway_station_name=gateway_station_name
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
