# -*- coding: UTF-8 -*-
import os
import sys
import requests
from flask import Flask, Response, request, jsonify, render_template
from utils.factory import create_app
import logging
import json
from bson import ObjectId
from flask_cors import CORS
from utils import db

from utils.space_weather_forecast import space_weather_forecast
from task.od_automation_tasks import orbit_precision_analysis_auto_task
from utils.dailyreport_utils import sei_dingtalk_news
# collision_avoidance_precision_analysis_auto_task
from utils.notification_content import space_weather_report_content, space_weather_info_only, \
    space_weather_info_with_summary, space_weather_orbit_pdf_report, space_weather_report_raw, \
    space_weather_orbit_pdf_report_alicloud

from utils.inner_stomsphere_weather_forecast import fetch_antennas_lat_lon, get_weather_forecast_data
from utils.notification_content_weather_forecast import generate_weather_forecast_report, \
    inner_atmosphere_weather_forecast_report_alicloud

import warnings

warnings.filterwarnings('ignore')


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)


PYTHON_ENV = os.environ.get('PYTHON_ENV')
if PYTHON_ENV is None:
    print("Config input error:", PYTHON_ENV)
    sys.exit()
app = create_app(config_name=PYTHON_ENV.upper())
app.app_context().push()
logger = logging.getLogger(__name__)

# 加载influx
influxdb_input = db.Influxdb(app.config['INFLUXDB_USER'], app.config['INFLUXDB_PASSWD'],
                             app.config['INFLUXDB_DB_INPUT'])

client_input = influxdb_input.connect(app.config['INFLUXDB_HOST'],
                                      app.config['INFLUXDB_PORT'])

influxdb_orbdata = db.Influxdb(app.config['INFLUXDB_USER'], app.config['INFLUXDB_PASSWD'],
                               app.config['INFLUXDB_DB_ORBITDATA'])

client_orbdata = influxdb_orbdata.connect(app.config['INFLUXDB_HOST'],
                                          app.config['INFLUXDB_PORT'])

# orbit_service = app.config['ORBIT_SERVICE']
mete_data_service = app.config['METE_DATA']
# orbit_propagation = app.config['ORBIT_PROPAGATION']
# orbit_maneuver = app.config['ORBIT_MANEUVER']

# 加载mongodb
mongo = db.Mongo(app.config['MONGO_HOSTS'],
                 app.config['MONGO_AUTH_SOURCE'],
                 app.config['MONGO_INITDB_ROOT_USERNAME'],
                 app.config['MONGO_INITDB_ROOT_PASSWORD'])

# 加载通知服务
note_url = app.config['NOTIFICATION_URL']

# 加载轨道外推计算接口
orbit_prop_url = app.config['ORBIT_PROPAGATION']

# 加载轨控活动查询
orbit_maneuver_url = app.config['ORBIT_MANEUVER']

# 连阿里云OSS
OSS2 = db.OSS2(app.config['OSS2_ENDPOINT'],
               app.config['OSS2_ACCESS'],
               app.config['OSS2_SECRET'])

# 查信关站任务
gateway_tasks_url = app.config['APPLICATION_TASK']

# 航天器信息上报列表查询
post_satellite_report_search = app.config['POST_SATELLITE_REPORT_SEARCH']

# 航天器上报轨道外推下载链接
get_satellite_file_download = app.config['GET_SATELLITE_FILE_DOWNLOAD']

# getting HTTP POST repsonse for AUTH TOKEN
post_token_url = app.config['POST_TOKEN_URL']
post_token_user_name = app.config['POST_TOKEN_USERNAME']
post_token_password = app.config['POST_TOKEN_PASSWORD']

# getting GNSS info
gnss_config = app.config['GNSS_CONFIG']

# gettting ephemeris info
get_ephemeris = app.config["GET_EPHEMERIS"]

# getting some cool shit
get_F10point7 = app.config['GET_F10POINT7']

# getting more cool stuff
get_ApIndex = app.config['GET_APINDEX']
get_KpIndex = app.config['GET_KPINDEX']

# mean_6elements
mean_6element_url = app.config['MEAN_6ELEMENT']
# calc_results
get_calc_result_url = app.config['GET_CALC_RESULT']

# push notification
notification_url = app.config['NOTIFICATION_URL']

# weather forecast data
weather_forecast_url = app.config['WEATHER_FORECAST_URL']
weather_forecast_key = app.config['WEATHER__FORECAST_KEY']

# gateway station code
gateway_station_code_url = app.config['GATEWAY_STATION_CODE_URL']

# gateway station location
gateway_station_location_url = app.config['GATEWAY_STATION_LOCATION_URL']

app = Flask(__name__)
CORS(app)

db.init_val()


@app.route("/")
def hello_world():
    return 'hello world'


@app.route('/status', methods=['POST'])
def progress_bar():
    response = db.progress
    return response
    # return Response(response=response,
    #                 status=200,
    #                 mimetype='application/json')


# excute odpa task //自动计算系列
@app.route('/odpa', methods=['POST'])
def odpa():
    data = request.json
    if data is None or data == {}:
        return Response(response=json.dumps({"Error": "Please provide connection information"}),
                        status=400,
                        mimetype='application/json')

    response = orbit_precision_analysis_auto_task(
        post_token_url,
        post_token_user_name,
        post_token_password,
        gnss_config=gnss_config,
        get_ephemeris=get_ephemeris,
        get_F10point7=get_F10point7,
        _influxdb=influxdb_input, client=client_input,
        orbit_prop_url=orbit_prop_url,
        satID_list=data['satIDs']
    )
    return jsonify(response), 200


# 空间环境信息获取 //空间环境系列
@app.route('/sei-dingtalk-news', methods=['POST'])
def seireport():
    data = request.json
    if not data or "start" not in data or "end" not in data or "satIDs" not in data:
        return jsonify({"Error": "Please provide 'start', 'end', and 'satIDs'"}), 400

    response = space_weather_report_content(
        tf1=data['start'],
        tf2=data['end'],
        get_F10point7=get_F10point7,
        get_ApIndex=get_ApIndex,
        get_KpIndex=get_KpIndex,
        satID_list=data['satIDs'],
        mean_6element_url=mean_6element_url,
        get_calc_result_url=get_calc_result_url,
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gnss_config=gnss_config,
        notificaiton_url=notification_url,
        notice_code=data['notice_code']
    )

    return jsonify({"message": response}), 200


@app.route('/sei-orbit-report', methods=['POST'])
def sei_orbit_pdfreport():
    data = request.json

    if not data or "start" not in data or "end" not in data or "satIDs" not in data:
        return jsonify({"Error": "Please provide 'start', 'end', and 'satIDs'"}), 400

    response = space_weather_orbit_pdf_report(
        tf1=data['start'],
        tf2=data['end'],
        get_F10point7=get_F10point7,
        get_ApIndex=get_ApIndex,
        get_KpIndex=get_KpIndex,
        satID_list=data['satIDs'],
        mean_6element_url=mean_6element_url,
        get_calc_result_url=get_calc_result_url,
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gnss_config=gnss_config
    )

    return jsonify({"message": response}), 200


@app.route('/sei-orbit-report-alicloud', methods=['POST'])
def sei_orbit_pdfreport_alicloud():
    data = request.json

    if not data or "start" not in data or "end" not in data or "satIDs" not in data:
        return jsonify({"Error": "Please provide 'start', 'end', and 'satIDs'"}), 400

    response = space_weather_orbit_pdf_report_alicloud(
        tf1=data['start'],
        tf2=data['end'],
        get_F10point7=get_F10point7,
        get_ApIndex=get_ApIndex,
        get_KpIndex=get_KpIndex,
        satID_list=data['satIDs'],
        mean_6element_url=mean_6element_url,
        get_calc_result_url=get_calc_result_url,
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gnss_config=gnss_config,
        OSS2=OSS2,
        notification_url=notification_url
    )

    return jsonify({"message": response}), 200


@app.route('/space-environment-info-with-no-summary', methods=['POST'])
def space_environment_info_no_summary():
    data = request.json
    if not data or "start" not in data or "end" not in data:
        return jsonify({"Error": "Please provide 'start', 'end'"}), 400

    response = space_weather_info_only(
        tf1=data['start'],
        tf2=data['end'],
        get_F10point7=get_F10point7,
        get_ApIndex=get_ApIndex,
        get_KpIndex=get_KpIndex
    )

    return jsonify({"message": response}), 200


@app.route('/space-environment-info-with-summary', methods=['POST'])
def space_environment_info_with_summary():
    data = request.json
    if not data or "start" not in data or "end" not in data:
        return jsonify({"Error": "Please provide 'start', 'end'"}), 400

    response = space_weather_info_with_summary(
        tf1=data['start'],
        tf2=data['end'],
        get_F10point7=get_F10point7,
        get_ApIndex=get_ApIndex,
        get_KpIndex=get_KpIndex
    )

    return jsonify({"message": response}), 200


@app.route('/space-environment-data-raw', methods=['POST'])
def space_enviroment_data_raw():
    data = request.json
    if not data or "start" not in data or "end" not in data:
        return jsonify({"Error": "Please provide 'start', 'end'"}), 400

    response = space_weather_report_raw(
        tf1=data['start'],
        tf2=data['end'],
        get_F10point7=get_F10point7,
        get_ApIndex=get_ApIndex,
        get_KpIndex=get_KpIndex
    )

    return jsonify({"message": response}), 200


# gettting location
@app.route('/gateway-location', methods=['POST'])
def gateway_location():
    data = request.json
    if not data or "keyword" not in data:
        return jsonify({"Error": "Please provide 'keyword'"}), 400

    response = fetch_antennas_lat_lon(
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gateway_station_code_url=gateway_station_code_url,
        gateway_station_location_url=gateway_station_location_url,
        keyword=data['keyword']
    )

    return jsonify({"message": response}), 200


# 天气信息获取
@app.route('/weather-forecast-data', methods=['POST'])
def weather_forecast_data():
    data = request.json
    if not data or "start" not in data or "end" not in data:
        return jsonify({"Error": "Please provide 'start', 'end'"}), 400

    response = get_weather_forecast_data(
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gateway_station_code_url=gateway_station_code_url,
        gateway_station_location_url=gateway_station_location_url,
        weather_forecast_url=weather_forecast_url,
        weather_forecast_key=weather_forecast_key,
        gateway_tasks_url=gateway_tasks_url,
        tf1=data['start'],
        tf2=data['end'],
        gateway_station_name=data['gateway_station_name']
    )

    return jsonify({"message": response}), 200


# 天气预报报告本地
@app.route('/weather-forecast-report', methods=['POST'])
def weather_forecast_report():
    data = request.json
    if not data or "start" not in data or "end" not in data:
        return jsonify({"Error": "Please provide 'start', 'end'"}), 400

    response = generate_weather_forecast_report(
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gateway_station_code_url=gateway_station_code_url,
        gateway_station_location_url=gateway_station_location_url,
        weather_forecast_url=weather_forecast_url,
        weather_forecast_key=weather_forecast_key,
        gateway_tasks_url=gateway_tasks_url,
        tf1=data['start'],
        tf2=data['end'],
        gateway_station_name=data['gateway_station_name']
    )

    return jsonify({"message": response}), 200


# 天气预报报告阿里云推送
@app.route('/weather-forecast-report-alicloud', methods=['POST'])
def weather_forecast_report_pdf_alicloud():
    data = request.json
    if not data or "start" not in data or "end" not in data:
        return jsonify({"Error": "Please provide 'start', 'end'"}), 400

    response = inner_atmosphere_weather_forecast_report_alicloud(
        post_token_url=post_token_url,
        post_token_user_name=post_token_user_name,
        post_token_password=post_token_password,
        gateway_station_code_url=gateway_station_code_url,
        gateway_station_location_url=gateway_station_location_url,
        weather_forecast_url=weather_forecast_url,
        weather_forecast_key=weather_forecast_key,
        gateway_tasks_url=gateway_tasks_url,
        tf1=data['start'],
        tf2=data['end'],
        gateway_station_name=data['gateway_station_name'],
        OSS2=OSS2,
        notification_url=notification_url
    )

    return jsonify({"message": response}), 200


@app.route('/index', methods=['GET'])
def index():
    print(f"-------------------service staring on {request.remote_addr}------------------")
    return render_template('index.html')


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7888))
    app.run(host='0.0.0.0', port=port, debug=True)
