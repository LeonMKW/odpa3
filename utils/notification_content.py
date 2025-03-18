import time
from datetime import datetime
import json
import pytz
from utils.dailyreport_utils import sei_dingtalk_news
from utils.od_utils import satellite_codes
import requests


def OBC_cumulative_reset_content(cumulative_reset_doc):
    satellitecode = cumulative_reset_doc['_satelliteCode']
    timefound = cumulative_reset_doc['time_found']
    timeend = cumulative_reset_doc['time_end']

    # Define Asia/Shanghai timezone
    shanghai_tz = pytz.timezone('Asia/Shanghai')

    # Convert float timestamp to datetime object
    timefound_datetime = datetime.fromtimestamp(timefound, shanghai_tz)
    timeend_datetime = datetime.fromtimestamp(timeend, shanghai_tz)
    # Get formatted time string
    timefound_str = timefound_datetime.strftime("%Y-%m-%d %H:%M:%S")
    timeend_str = timeend_datetime.strftime("%Y-%m-%d %H:%M:%S")

    cumulative_count = cumulative_reset_doc['cumulative_count']
    # Get current timestamp (13 digits)
    current_timestamp = int(time.time() * 1000)

    # Get current time in the desired format
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    body = f'''{{
        "type": "telemetry_data",
        "code": "Satellite_Reset_Count",
        "objectType": "satellite",
        "objectId": "1",
        "objectName": "{satellitecode}",
        "ruleName": "",
        "eventTime": {current_timestamp},
        "params": {{
            "eventObjectType": "satellite",
            "eventObjectId": "1",
            "eventObjectName": "{satellitecode}",
            "param": {{
                "resetCount": {cumulative_count},
                "timefound": "{timefound_str}",
                "timeend": "{timeend_str}"
            }},
            "eventTimeStr": "{current_time_str}",
            "eventTime": {current_timestamp},
            "eventCode": "Satellite_Reset_Count",
            "eventName": "累计复位计数",
            "eventDesc": "",
            "eventLevel": "INFO"
        }}
    }}'''
    return body


def od_precision_content(orbit_precision_summary, imgurl):
    # orbit_precision_summary.pop('a', None)
    # orbit_precision_summary.pop('e', None)
    # orbit_precision_summary.pop('i', None)
    # orbit_precision_summary.pop('dw', None)
    # orbit_precision_summary.pop('xw', None)
    # orbit_precision_summary.pop('M', None)
    # orbit_precision_summary.pop('thrust', None)
    # orbit_precision_summary.pop('isValid', None)
    # orbit_precision_summary.pop('timestamp', None)
    keys_to_remove = ['a', 'e', 'i', 'dw', 'xw', 'M', 'thrust', 'isValid', 'timestamp']
    for key in keys_to_remove:
        orbit_precision_summary.pop(key, None)

    # Round float values to 3 decimal places
    keys_to_round = ['CD', 'residual', 'mse', 'hour_error', 'max_error', '3hr_err', '6hr_err', '12hr_err', '18hr_err']
    for key in keys_to_round:
        if key in orbit_precision_summary and isinstance(orbit_precision_summary[key], float):
            orbit_precision_summary[key] = round(orbit_precision_summary[key], 3)
    satellitecode = orbit_precision_summary['spacecraft']
    # Renaming the keys in the original dictionary
    orbit_precision_summary["err3h"] = orbit_precision_summary.pop("3hr_err")
    orbit_precision_summary["err6h"] = orbit_precision_summary.pop("6hr_err")
    orbit_precision_summary["err12h"] = orbit_precision_summary.pop("12hr_err")
    orbit_precision_summary["err18h"] = orbit_precision_summary.pop("18hr_err")

    # Get current timestamp (13 digits)
    current_timestamp = int(time.time() * 1000)
    # epochTimeUTC = orbit_precision_summary['epochTimeUTC']
    orbit_precision_summary_json = json.dumps(orbit_precision_summary)

    ops = str(orbit_precision_summary_json).replace("{", "").replace("}", "")

    # Get current time in the desired format
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    body = f'''{{
    "type": "telemetry_data",
    "code": "Satellite_Orbital_Accuracy_Update",
    "objectType": "satellite",
    "objectId": "1",
    "objectName": "{satellitecode}",
    "ruleName": "",
    "eventTime": {current_timestamp},
    "params": {{
        {ops},
        "img": "{imgurl}"
        }}
    }}'''
    return body


def spiderling_daily_report_content(imgurl):
    # Get current timestamp (13 digits)
    current_timestamp = int(time.time() * 1000)
    current_date = time.strftime("%Y-%m-%d")
    body = f'''{{
    "type": "telemetry_data",
    "code": "satellite_report_update",
    "objectType": "report",
    "objectId": "1",
    "objectName": "小蜘蛛网飞控日报",
    "ruleName": "",
    "eventTime": {current_timestamp},
    "params": {{
        "currentdate": "{current_date}",
        "name": "银河航天小蜘蛛网飞控日报",
        "img": "{imgurl}"
        }}
    }}'''
    return body


def space_weather_report_content(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex, satID_list,
                                 mean_6element_url, get_calc_result_url,
                                 post_token_url,
                                 post_token_user_name,
                                 post_token_password,
                                 gnss_config, notificaiton_url, notice_code):

    try:
        current_timestamp = int(time.time()) * 1000  # Get current timestamp in **milliseconds** (13 digits)

        if not tf1:
            tf1 = current_timestamp - (24 * 60 * 60 * 1000)  # Use current timestamp

        if not tf2:
            tf2 = current_timestamp  # 24 hours before current timestamp

        # **Convert to integers (in case they're strings)**
        tf1, tf2 = int(tf1), int(tf2)

        # Get space environment data and satellite data
        space_env_data, satellite_data, ma, ad = sei_dingtalk_news(tf1, tf2, get_F10point7, get_ApIndex, get_KpIndex,
                                                                   satID_list, mean_6element_url, get_calc_result_url)

        # Get current date (YYYY-MM-DD) and formatted for xaxis lookup (MM-DD)
        current_timestamp = int(time.time())
        current_date_xaxis = time.strftime("%m-%d", time.gmtime(current_timestamp))
        previous_date_xaxis = time.strftime("%m-%d", time.gmtime(current_timestamp - 86400))  # Yesterday
        next_date_xaxis = time.strftime("%m-%d", time.gmtime(current_timestamp + 86400))  # Tomorrow

        # Extract F10.7 values (merged real + predicted values)
        F107_xaxis = json.loads(space_env_data["F107"]["xaxis"])
        F107_values = json.loads(space_env_data["F107"]["value"])

        def get_valid_value(xaxis_list, value_list, date, fallback_date):
            """Returns the value for a given date, falling back to the previous date if needed."""
            try:
                index = xaxis_list.index(date)
                value = value_list[index]
                if value != "null":
                    return value
                else:
                    prev_index = xaxis_list.index(fallback_date)
                    return value_list[prev_index] if value_list[prev_index] != "null" else "暂未更新"
            except ValueError:
                return "暂未更新"

        F107_today = get_valid_value(F107_xaxis, F107_values, current_date_xaxis, previous_date_xaxis)
        F107_tomorrow = get_valid_value(F107_xaxis, F107_values, next_date_xaxis, current_date_xaxis)

        # Extract ApIndex values (merged real + predicted values)
        Ap_xaxis = json.loads(space_env_data["ApIndex"]["xaxis"])
        Ap_values = json.loads(space_env_data["ApIndex"]["value"])

        Ap_today = get_valid_value(Ap_xaxis, Ap_values, current_date_xaxis, previous_date_xaxis)
        Ap_tomorrow = get_valid_value(Ap_xaxis, Ap_values, next_date_xaxis, current_date_xaxis)

        # Extract KpIndex values
        Kp_value_nearest = space_env_data["KpIndex"]["nearest"]
        Kp_value_nearest_time = space_env_data["KpIndex"]["nearest_time"]
        Kp_value_max = space_env_data["KpIndex"]["max"]
        Kp_value_max_time = space_env_data["KpIndex"]["max_time"]

        # **Generate `past12hours` String**
        past12hoursF107 = f"太阳活动水平"
        if F107_today != "暂未更新":
            if float(F107_today) < 70:
                past12hoursF107 += "非常低"
            elif 70 <= float(F107_today) < 100:
                past12hoursF107 += "低"
            elif 100 <= float(F107_today) < 150:
                past12hoursF107 += "中等"
            elif 150 <= float(F107_today) < 200:
                past12hoursF107 += "较高"
            elif 200 <= float(F107_today) < 240:
                past12hoursF107 += "高"
            else:
                past12hoursF107 += "极高"
            past12hoursF107 += f" (F10.7值={F107_today})"
        else:
            past12hoursF107 += "暂未更新"

        past12hoursKp = f"短时"
        if Kp_value_max != "地磁暴活动暂未更新":
            if float(Kp_value_max) <= 1:
                past12hoursKp += "地磁暴活动强度整体平静"
            elif 2 < float(Kp_value_max) <= 3:
                past12hoursKp += "地磁暴活动强度整体稍有扰动"
            elif 3 < float(Kp_value_max) <= 4:
                past12hoursKp += "地磁暴活动强度整体活跃"
            elif 4 < float(Kp_value_max) <= 5:
                past12hoursKp += "地磁暴活动出现小地磁暴"
            elif 5 < float(Kp_value_max) <= 6:
                past12hoursKp += "地磁暴活动出现中等地磁暴"
            elif 6 < float(Kp_value_max) <= 7:
                past12hoursKp += "地磁暴活动出现强烈地磁暴"
            elif 7 < float(Kp_value_max) <= 8:
                past12hoursKp += "地磁暴活动出现严重地磁暴"
            else:
                past12hoursKp += "地磁暴活动达到极端地磁暴级别"
            past12hoursKp += f"(最高Kp指数={Kp_value_max},观测于北京时间{Kp_value_max_time}。最近Kp指数={Kp_value_nearest},观测于北京时间{Kp_value_nearest_time})"
        else:
            past12hoursKp += "地磁暴活动暂未更新"

        past12hoursAp = f"地磁扰动"
        if Ap_today != "暂未更新":
            if float(Ap_today) <= 7:
                past12hoursAp += "整体平静"
            elif 7 < float(Ap_today) <= 16:
                past12hoursAp += "整体轻度扰动"
            elif 16 < float(Ap_today) <= 30:
                past12hoursAp += "整体活跃"
            elif 30 < float(Ap_today) <= 50:
                past12hoursAp += "达到整体小地磁暴级别"
            elif 50 < float(Ap_today) <= 100:
                past12hoursAp += "达到整体大地磁暴级别"
            else:
                past12hoursAp += "达到整体极端地磁暴级别"
            past12hoursAp += f" (Ap指数={Ap_today})"
        else:
            past12hoursAp += "暂未更新"

        # **Generate `future12hours` String**
        future12hoursF107 = f"太阳活动水平"
        if F107_tomorrow != "暂无预报":
            if float(F107_tomorrow) < 70:
                future12hoursF107 += "非常低"
            elif 70 <= float(F107_tomorrow) < 100:
                future12hoursF107 += "低"
            elif 100 <= float(F107_tomorrow) < 150:
                future12hoursF107 += "中等"
            elif 150 <= float(F107_tomorrow) < 200:
                future12hoursF107 += "较高"
            elif 200 <= float(F107_tomorrow) < 240:
                future12hoursF107 += "高"
            else:
                future12hoursF107 += "极高"
            future12hoursF107 += f" (F10.7值={F107_tomorrow})"
        else:
            future12hoursF107 += "暂无预报"

        future12hoursAp = f"地磁扰动"
        if Ap_tomorrow != "暂无预报":
            if float(Ap_tomorrow) <= 7:
                future12hoursAp += "整体平静"
            elif 7 < float(Ap_tomorrow) <= 16:
                future12hoursAp += "整体轻度扰动"
            elif 16 < float(Ap_tomorrow) <= 30:
                future12hoursAp += "整体活跃"
            elif 30 < float(Ap_tomorrow) <= 50:
                future12hoursAp += "可能达到整体小地磁暴级别"
            elif 50 < float(Ap_tomorrow) <= 100:
                future12hoursAp += "可能达到整体大地磁暴级别"
            else:
                future12hoursAp += "可能达到整体极端地磁暴级别"
            future12hoursAp += f" (Ap指数={Ap_tomorrow})"
        else:
            future12hoursAp += "暂无预报"

        # **F10.7 Advisory**
        advisory_f107 = ""
        if F107_tomorrow != "暂无预报":
            f107_value = float(F107_tomorrow)
            if f107_value >= 200:
                advisory_f107 = "未来太阳活动高"
            elif 170 <= f107_value < 200:
                advisory_f107 = "未来太阳活动较高"
            elif 150 <= f107_value < 170:
                advisory_f107 = "未来太阳活动中等"
            else:
                advisory_f107 = "未来太阳活动较低"

        # **ApIndex Advisory**
        advisory_ap = ""
        if Ap_tomorrow != "暂无预报":
            ap_value = float(Ap_tomorrow)
            if ap_value > 30:
                advisory_ap = "地磁活动达到地磁暴级别"
            elif 20 < ap_value <= 30:
                advisory_ap = "地磁活动有较强扰动"
            elif 15 < ap_value <= 20:
                advisory_ap = "地磁活动有中度扰动"
            elif 10 < ap_value <= 15:
                advisory_ap = "地磁活动有轻度扰动"
            elif ap_value < 10:
                advisory_ap = "地磁活动较低"

        # **General Advisory**
        advisory_general = ""
        if f107_value != "暂无预报" or ap_value != "暂无预报":
            if f107_value > 170 or ap_value > 20:
                advisory_general = "需要密切关注卫星运行状态和轨道衰减情况"
            elif 150 < f107_value <= 170 or 10 < ap_value <= 20:
                advisory_general = "请关注卫星运行状态和轨道衰减情况"
            else:
                advisory_general = "可以放松一下啦"

        # **Combine the Three Advisory Messages**
        advisory_messages = [msg for msg in [advisory_f107, advisory_ap, advisory_general] if msg]  # Remove empty strings
        advisory = "，".join(advisory_messages) + "。" if advisory_messages else "未来空间环境整体平静。"

        # **Mean Altitude and Altitude Change**
        altitude_data = {entry["spacecraftId"]: entry["altitude"] for entry in ma}
        altitude_change_data = {entry["spacecraftId"]: entry["altitude_change"] for entry in ad}

        satIDss = satID_list.split(",")
        satellite_property_list = satellite_codes(post_token_url,
                                                  post_token_user_name,
                                                  post_token_password, gnss_config, satIDs=satIDss)

        satellite_code_map = {sat["id"]: sat["code"] for sat in satellite_property_list}

        # Define UTC and Shanghai timezones
        utc_tz = pytz.utc
        shanghai_tz = pytz.timezone('Asia/Shanghai')

        # **Extract Satellite Data**
        extracted_satellite_data = [
            {
                "spacecraftId": sat["spacecraftId"],
                "code": satellite_code_map.get(sat["spacecraftId"], "未知卫星"),  # Add code mapping
                "epochTimeUTC": datetime.strptime(sat["epochTimeUTC"], "%Y-%m-%dT%H:%M:%S.%fZ")
                    .replace(tzinfo=utc_tz)  # Ensure it's in UTC
                    .astimezone(shanghai_tz)  # Convert to Shanghai timezone
                    .strftime("%Y-%m-%d %H:%M:%S"),  # Format as string
                "mse": round(sat["mse"], 2),
                "ephemeris_error": round(sat["ephemeris_error"], 2),
                "difference": round(sat["difference"], 2),
                "mean_altitude": round(altitude_data.get(sat["spacecraftId"], "暂无数据") / 1000, 3),
                "altitude_change": round(altitude_change_data.get(sat["spacecraftId"], "暂无数据"), 2),
            }
            for sat in satellite_data
        ]

        # Define Asia/Shanghai timezone
        shanghai_tz = pytz.timezone('Asia/Shanghai')
        # Convert float timestamp to datetime object
        time_reported_datetime = datetime.fromtimestamp(current_timestamp, shanghai_tz)
        # Get formatted time string
        time_report_str = time_reported_datetime.strftime("%Y-%m-%d %H:%M:%S")

        # Get the hour
        hour = time_reported_datetime.hour

        # Determine the time of day
        if 0 <= hour < 12:
            timeofday = "早报"
        elif 12 <= hour < 24:
            timeofday = "晚报"
        else:
            timeofday = "日报"

        # Prepare the payload
        payload = {
            "System": "odpa3",
            "NoticeCode": notice_code,
            "Param": {
                "space_env_data": {
                    "past12hoursF107": past12hoursF107,
                    "past12hoursKp": past12hoursKp,
                    "past12hoursAp": past12hoursAp,
                    "future12hoursF107": future12hoursF107,
                    "future12hoursAp": future12hoursAp,
                    "F107_today": F107_today,
                    "F107_tomorrow": F107_tomorrow,
                    "Ap_today": Ap_today,
                    "Ap_tomorrow": Ap_tomorrow,
                    "Kp_value_nearest": Kp_value_nearest,
                    "Kp_value_max": Kp_value_max,
                    "Kp_value_max_time": Kp_value_max_time,
                    "advisory": advisory  # May contain non-ASCII characters like "太阳活动水平"
                },
                "satellite_data": extracted_satellite_data,
                "eventTimeStr": str(time_report_str),
                "timeofday": timeofday
            }
        }
        # print(json.dumps(payload))

        # **Send the POST Request**
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(notificaiton_url, json=payload, headers=headers, timeout=300)

            if response.status_code == 200:
                print("data ssuccessfully sent")
            else:
                print(f"Failed to send data! HTTP Status: {response.status_code}, Response: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"Error while sending request: {e}")

        # **Always return a success message**
        return "orbit and space environment report posted"

    except Exception as e:
        print(f"Unexpected Error in `space_weather_report_content`: {str(e)}")
        return "Error: Failed to generate space environment report"
