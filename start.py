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
    space_weather_info_with_summary, space_weather_orbit_pdf_report, space_weather_report_raw

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

# 连OSS
OSS2 = db.OSS2(app.config['OSS2_ENDPOINT'],
               app.config['OSS2_ACCESS'],
               app.config['OSS2_SECRET'])

# 查信关站任务
# gateway_url = app.config['APPLICATION_TASK']
# gateway_auth = app.config['APPLICATION_AUTHORIZATION']

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


# OSS2 = OSS2,
# note_url = note_url,

# # excute collision avoidance PA//自动计算系列
# @app.route('/capa', methods=['POST'])
# def capa():
#     data = request.json
#     if data is None or data == {}:
#         return Response(response=json.dumps({"Error": "Please provide connection information"}),
#                         status=400,
#                         mimetype='application/json')
#
#     response = collision_avoidance_precision_analysis_auto_task(metedataservice_url=mete_data_service,
#                                                                 orbitserviceurl=orbit_service,
#                                                                 _influxdb=influxdb_input, client=client_input,
#                                                                 mariadb=mariadbsetup,
#                                                                 note_url=note_url,
#                                                                 orbit_prop_url=orbit_prop_url,
#                                                                 OSS2=OSS2,
#                                                                 satID_list=data['satIDs']
#                                                                 )
#     return jsonify(response), 200

# @app.route('/obh', methods=['POST'])
# def all_obh():
#     data = request.json
#     if data is None or data == {}:
#         return Response(response=json.dumps({"Error": "Please provide connection information"}),
#                         status=400,
#                         mimetype='application/json')
#
#     response = get_obh(
#         post_token_url,
#         post_token_user_name,
#         post_token_password,
#         mete_data_service=mete_data_service,
#         influxdb_orbdata=influxdb_orbdata,
#         client_orbdata=client_orbdata,
#         satID=data['satID'],  # Accept multiple satellite IDs
#         start=data['start'],
#         end=data['end']
#     )
#
#     return Response(response=response,
#                     status=200,
#                     mimetype='application/json')


# try
# @app.route('/try', methods=['POST'])
# def od_temp():
#     data = request.json
#     if data is None or data == {}:
#         return Response(response=json.dumps({"Error": "Please provide connection information"}),
#                         status=400,
#                         mimetype='application/json')
#
#     response = propagating_2nd_predictive_ephemeris(
#         post_token_url,
#         post_token_user_name,
#         post_token_password,
#         mete_data_service=mete_data_service,
#         post_satellite_report_search_url=post_satellite_report_search,
#         get_satellite_file_download_url=get_satellite_file_download,
#         satelliteId=data['satelliteId'],
#         reportTypes=data['reportTypes'],
#         beginTime=data['beginTime'],
#         endTime=data['endTime'],
#         states=data['states'],
#         _influxdb=influxdb_input,
#         client=client_input,
#         orbit_prop_url=orbit_prop_url,
#         propagation_hours=data['propagation_hours'],
#     )
#
#     return Response(response=response,
#                     status=200,
#                     mimetype='application/json')


@app.route('/index', methods=['GET'])
def index():
    print(f"-------------------service staring on {request.remote_addr}------------------")
    return render_template('index.html')


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7888))
    app.run(host='0.0.0.0', port=port, debug=True)
    # daily_report_spiderling(orbitservice_url='http://orbit-service-inf.prod.yhroot.com/graphql',
    #                         mete_data_service='http://mete-data-service.prod.yhroot.com/graphql',
    #                         influxdb_input=influxdb_input,
    #                         client_input=client_input,
    #                         influxdb_action=influxdb_action,
    #                         client_action=client_action,
    #                         influxdb_chronograf=influxdb_chronograf,
    #                         client_chronograf=client_chronograf,
    #                         satID='6,7',
    #                         date='2024-01-30',
    #                         start='',
    #                         end='')
    # satellite_properties('http://mete-data-service.prod.yhroot.com/graphql', satIDs='2')
    # od_tmcode('http://mete-data-service.prod.yhroot.com/graphql', satIDs='2')
    # gnss_get_last('http://mete-data-service.prod.yhroot.com/graphql',
    #               influxdb_input, client_input, satIDs='2')
    # ephemeris_acquire(metedataservice_url='http://mete-data-service.prod.yhroot.com/graphql',
    #     orbitserviceurl='http://orbit-service-inf.prod.yhroot.com/graphql',
    #               startAt="2024-03-25T15:06:59.000Z",
    #               endAt="2024-03-26T05:38:23.000Z",
    #               satIDs="4")
    # orbit_precision_calculation_step1(metedataservice_url='http://mete-data-service.prod.yhroot.com/graphql',
    #                                   orbitserviceurl='http://orbit-service-inf.prod.yhroot.com/graphql',
    #                                   _influxdb=influxdb_input, client=client_input, satIDs="4")

    # orbit_precision_analysis_auto_task(metedataservice_url='http://mete-data-service.prod.yhroot.com/graphql',
    #                                    orbitserviceurl='http://orbit-service-inf.prod.yhroot.com/graphql',
    #                                    orbit_prop_url=orbit_prop_url,
    #                                    _influxdb=influxdb_input, client=client_input, satID_list="6",
    #                                    mariadb=mariadbsetup,
    #                                    note_url=note_url,
    #                                    OSS2=OSS2)

    # satellite_status_data_auto_task('http://mete-data-service.prod.yhroot.com/graphql', influxdb_input, client_input,
    #                                 satIDs='13',
    #                                 date='2024-04-25', start='', end='')
    # OBCreset_influx('http://mete-data-service.prod.yhroot.com/graphql', influxdb_input, client_input, satID='3',
    #                 tf1='', tf2='')
    # write_reset_count('http://mete-data-service.prod.yhroot.com/graphql', influxdb_input, client_input, satID='4',
    #                   tf1='2024-05-06T00:00:00.000Z', tf2='2024-05-06T06:40:00.000Z')
    # write_switch_count('http://mete-data-service.prod.yhroot.com/graphql', influxdb_input, client_input, satID='4',
    #                   tf1='2024-05-06T00:00:00.000Z', tf2='2024-05-06T06:40:00.000Z')
    # check_repeating_records('http://mete-data-service.prod.yhroot.com/graphql', satID='4',
    #                   tf1='2024-05-06T00:00:00.000Z', tf2='2024-05-06T06:40:00.000Z')
    # OBCreset_mongo_records('http://mete-data-service.prod.yhroot.com/graphql', satID='4',
    #                        tf1='2024-04-24T12:05:16.000Z',
    #                        tf2='2024-04-24T23:07:23.000Z')
    # write_cumulative_data('http://mete-data-service.prod.yhroot.com/graphql', satID='4',
    #                       tf1='2024-04-24T10:00:16.000Z', tf2='2024-04-24T23:07:23.000Z')

    # calculate_cumulative_reset('http://mete-data-service.prod.yhroot.com/graphql', satID='4',
    #                            tf1='', tf2='',
    #                            note_url=note_url)
    # OBCswitch_data('http://mete-data-service.prod.yhroot.com/graphql', satID='3', tf1='', tf2='')
    # hist_interval('http://orbit-service-inf.prod.yhroot.com/graphql',
    #               'http://mete-data-service.prod.yhroot.com/graphql',
    #               influxdb_input, client_input,
    #               "2024-03-25T15:06:59.000Z",
    #               "2024-03-27T15:38:23.000Z",
    #               '6')
    # gnss_interval('http://orbit-service-inf.prod.yhroot.com/graphql',
    #               'http://mete-data-service.prod.yhroot.com/graphql',
    #               influxdb_input, client_input,
    #               "2024-03-28T00:06:59.000Z",
    #               "2024-03-28T03:38:23.000Z",
    #               '12')

    # results_dict = experimental_uplock('http://orbit-service-inf.prod.yhroot.com/graphql',
    #                                    'http://mete-data-service.prod.yhroot.com/graphql',
    #                                    influxdb_input, client_input,
    #                                    "2024-03-22T04:39:30.000Z",
    #                                    "2024-03-22T07:11:51.000Z", '12')

    # results_dict = experimental_telemetry('http://orbit-service-inf.prod.yhroot.com/graphql',
    #                                       'http://mete-data-service.prod.yhroot.com/graphql',
    #                                       influxdb_input, client_input,
    #                                       "2024-03-22T04:39:30.000Z",
    #                                       "2024-03-22T07:11:51.000Z", '12')
    #
    # json.dumps(results_dict)
