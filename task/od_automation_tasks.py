from task.od_algorithm import orbit_precision_calculation_step1, \
    orbit_precision_calculation_step2_1
from utils.od_utils import satellite_properties
from utils.flightcontrol_utils import tm_table
from datetime import datetime, timedelta
import pytz
# from utils.plot_methods import plot_od_precision
import matplotlib.pyplot as plt
import requests
import json
from utils.notification_content import od_precision_content
import logging
import os
from utils.core_algorithm import calculate_orbit_period
from utils.db import get_mongo


def orbit_precision_analysis_auto_task(post_token_url,
                                       post_token_user_name,
                                       post_token_password,
                                       gnss_config,
                                       get_ephemeris,
                                       get_F10point7,
                                       _influxdb, client,
                                       orbit_prop_url,
                                       satID_list):
    mongo = get_mongo()  # Get the MongoDB instance
    satIDss = satID_list.split(",")  # Convert comma-separated string to a list of satellite IDs

    for satIDs in satIDss:
        # Fetch satellite properties
        satellite_property = satellite_properties(post_token_url,
                                                  post_token_user_name,
                                                  post_token_password, gnss_config, satIDs)

        # Step 1: Fetch ephemeris
        ephemeris = orbit_precision_calculation_step1(post_token_url,
                                                      post_token_user_name,
                                                      post_token_password,
                                                      _influxdb, client, satIDs,
                                                      gnss_config, get_ephemeris)

        # Extract ephemeris_id and timestamp
        ephemeris_id = ephemeris.get('id')
        epoch_time_utc = ephemeris['epochTimeUTC']
        tf1_timestamp = int(datetime.strptime(epoch_time_utc, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp())  # Convert to timestamp
        tf2_timestamp = tf1_timestamp + 12 * 3600  # Add 12 hours

        # Step 2: Perform orbit precision calculation and get the merged JSON
        merged_json, ephemeris_with_err = orbit_precision_calculation_step2_1(post_token_url,
                                                                              post_token_user_name,
                                                                              post_token_password, _influxdb, client,
                                                                              satellite_property,
                                                                              ephemeris,
                                                                              get_F10point7=get_F10point7,
                                                                              orbit_prop_url=orbit_prop_url)

        # Check in MongoDB for the ephemeris_id in the last 12 hours (ephemeris_pa collection)
        ephemeris_query = {
            'id': ephemeris_id,
            'timestamp': {'$gte': tf1_timestamp, '$lte': tf2_timestamp}
        }
        existing_ephemeris = mongo.find_one_data(ephemeris_query, 'ephemeris_pa')

        if existing_ephemeris:
            logging.info(f"Ephemeris ID {ephemeris_id} already exists in 'ephemeris_pa'. Updating the record.")
            ephemeris_with_err['timestamp'] = tf1_timestamp  # Add timestamp to ensure consistency
            mongo.update_one_data(data=ephemeris_with_err, collection='ephemeris_pa', composite_key=ephemeris_query)
        else:
            logging.info(f"Ephemeris ID {ephemeris_id} does not exist in 'ephemeris_pa'. Creating a new record.")
            ephemeris_with_err['timestamp'] = tf1_timestamp  # Add timestamp to the record
            mongo.write_one_data(data=ephemeris_with_err, collection='ephemeris_pa')

        # Prepare merged_json for MongoDB
        propagation_record = {
            "ephemeris_id": ephemeris_id,
            "satellite_code": satellite_property['satelliteCode'],
            "timestamp": tf1_timestamp,  # Start time of the propagation
            "merged_data": merged_json,  # Store the JSON data for plotting
            "createdAt": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "updatedAt": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }

        # Check for existing propagation record in propagation_pa collection
        propagation_query = {
            "ephemeris_id": ephemeris_id,
            "timestamp": tf1_timestamp
        }
        existing_propagation = mongo.find_one_data(propagation_query, 'propagation_pa')

        if existing_propagation:
            logging.info(
                f"Propagation data for Ephemeris ID {ephemeris_id} already exists in 'propagation_pa'. Updating the "
                f"record.")
            mongo.update_one_data(data=propagation_record, collection='propagation_pa', composite_key=propagation_query)
        else:
            logging.info(
                f"Propagation data for Ephemeris ID {ephemeris_id} does not exist in 'propagation_pa'. Creating a new "
                f"record.")
            mongo.write_one_data(data=propagation_record, collection='propagation_pa')

        # Add Beijing time to ephemeris
        utc = pytz.timezone('UTC')
        beijing = pytz.timezone('Asia/Shanghai')
        timestamp_utc = datetime.strptime(ephemeris_with_err['epochTimeUTC'], '%Y-%m-%dT%H:%M:%S.%fZ')
        utc_dt = utc.localize(timestamp_utc)  # Localize UTC time
        beijing_dt = utc_dt.astimezone(beijing)  # Convert to Beijing time
        ephemeris_with_err['beijing_time'] = beijing_dt.strftime('%Y-%m-%d %H:%M:%S')

        # Log results
        logging.info(f"{satIDs} odpa pipeline complete")
        # logging.info(f"Updated ephemeris with errors: {ephemeris_with_err}")

    return "odpa_task_end"


# def collision_avoidance_precision_analysis_auto_task(metedataservice_url,
#                                                      orbitserviceurl,
#                                                      _influxdb, client,
#                                                      orbit_prop_url,
#                                                      mariadb,
#                                                      satID_list,
#                                                      note_url,
#                                                      OSS2):
#     satIDss = satID_list.split(",")  # Convert comma-separated string to a list of satellite IDs
#
#     for satIDs in satIDss:
#         tm = tm_table(metedataservice_url, satIDs)
#         tmversion = tm[satIDs]['tm_version']
#         satellite_od_dict = satellite_properties(metedataservice_url, satIDs)
#         # print(satellite_od_dict)
#         satgnssconfig_df = od_tmcode(metedataservice_url, satIDs)
#         # print(satgnssconfig_df)
#
#         db = mariadb
#         conn = db.get_connection()
#         cur = conn.cursor()
#
#         # step1 http post
#
#         ephemeris_dict = orbit_precision_calculation_step1(metedataservice_url, orbitserviceurl, _influxdb, client,
#                                                            satIDs)
#
#         ephemeris_id = ephemeris_dict['id'][0]
#
#         # step 2, if row ephemeris_id > 0, already exists, go to next satID, else calculate merged_df,
#         # orbit_precision_evaluate and continue to step 3
#         try:
#             cur.execute("SELECT COUNT(*) FROM orbit_precision_summary WHERE id = ?", (ephemeris_id,))
#             row = cur.fetchone()
#             count = row[0]
#             if count > 0:
#                 logging.info(f"Ephemeris ID {ephemeris_id} exists in 'orbit_precision_summary' table.")
#             else:
#                 logging.info(
#                     f"{ephemeris_id} starting evaluation...")
#
#                 merged_df, orbit_precision_summary = orbit_precision_calculation_step2_1(satellite_od_dict,
#                                                                                          ephemeris_dict,
#                                                                                          _influxdb, client,
#                                                                                          satIDs,
#                                                                                          orbit_prop_url,
#                                                                                          satgnssconfig_df,
#                                                                                          tmversion)
#                 # print(orbit_precision_summary.to_string())
#                 # print(merged_df.dtypes)
#                 merged_df['ephemeris_id'] = merged_df['ephemeris_id'].astype('int')
#                 # print(merged_df.to_string())
#                 # print(merged_df.dtypes)
#
#                 utc = pytz.timezone('UTC')
#                 beijing = pytz.timezone('Asia/Shanghai')
#                 timestamp_utc = datetime.strptime(orbit_precision_summary['epochTimeUTC'][0],
#                                                   '%Y-%m-%dT%H:%M:%S.%fZ')
#                 # Localize UTC time
#                 utc_dt = utc.localize(timestamp_utc)
#
#                 # Convert to Beijing time
#                 beijing_dt = utc_dt.astimezone(beijing)
#
#                 # Format the datetime object as a string
#                 orbit_precision_summary['beijing_time'] = beijing_dt.strftime('%Y-%m-%d %H:%M:%S')
#                 orbit_precision_summary['id'] = int(orbit_precision_summary['id'].iloc[0])
#                 orbit_precision_summary['timestamp'] = int(orbit_precision_summary['timestamp'].iloc[0])
#                 orbit_precision_summary['thrust'] = float(orbit_precision_summary['thrust'].iloc[0])
#
#                 # print(merged_df.to_string())
#                 orbit_precision_summary = orbit_precision_summary.to_dict(orient='records')[0]
#                 # orbit_precision_summary = {key: str(value) for key, value in orbit_precision_summary.items()}
#                 orbit_precision_summary.pop('createdAt', None)
#                 orbit_precision_summary.pop('updatedAt', None)
#                 orbit_precision_summary.pop('epochTime', None)
#                 # logging.info(orbit_precision_summary)
#                 # value_types = check_dict_value_types(orbit_precision_summary)
#                 #
#                 #
#                 # # Print the result
#                 # for key, value_type in value_types.items():
#                 #     print(f"Key: {key}, Value Type: {value_type}")
#
#                 # step 3_0 oss operation, time series modelling
#                 try:
#                     # plot the plot and save the plot to OSS2
#                     M = OSS2
#                     period = int(calculate_orbit_period(orbit_precision_summary['a'] / 10000))
#
#                     trend_values = plot_od_precision(merged_df, ossendpoint=M.endpoint, ossaccess=M.access,
#                                                      osssecret=M.secret,
#                                                      period=period)
#                     orbit_precision_summary['3hr_err'] = trend_values[0]
#                     orbit_precision_summary['6hr_err'] = trend_values[1]
#                     orbit_precision_summary['12hr_err'] = trend_values[2]
#                     orbit_precision_summary['18hr_err'] = trend_values[3]
#                     fid = orbit_precision_summary['id']
#
#                     # delete local storage
#                     path = f'data/{fid}.png'
#
#                     try:
#                         os.remove(path)
#                         print(f"File {path} has been deleted successfully.")
#                     except Exception as e:
#                         print(f"Error: {e}")
#
#                     # Write summary to orbit_precision_summary table
#                     insert_sql = f"""INSERT INTO orbit_precision_summary
#                         (a,e,i,dw,xw,M,CD,remark,gnssCount,residual,type,epochTimeUTC,id,thrust,isValid,spacecraft,
#                         timestamp,mse,hour_error,max_error,beijing_time,3hr_err,6hr_err,12hr_err,18hr_err)
#                         VALUES (
#                             "{orbit_precision_summary['a']}",
#                             "{orbit_precision_summary['e']}",
#                             "{orbit_precision_summary['i']}",
#                             "{orbit_precision_summary['dw']}",
#                             "{orbit_precision_summary['xw']}",
#                             "{orbit_precision_summary['M']}",
#                             "{orbit_precision_summary['CD']}",
#                             "{orbit_precision_summary['remark']}",
#                             "{orbit_precision_summary['gnssCount']}",
#                             "{orbit_precision_summary['residual']}",
#                             "{orbit_precision_summary['type']}",
#                             "{orbit_precision_summary['epochTimeUTC']}",
#                             "{orbit_precision_summary['id']}",
#                             "{orbit_precision_summary['thrust']}",
#                             "{orbit_precision_summary['isValid']}",
#                             "{orbit_precision_summary['spacecraft']}",
#                             "{orbit_precision_summary['timestamp']}",
#                             "{orbit_precision_summary['mse']}",
#                             "{orbit_precision_summary['hour_error']}",
#                             "{orbit_precision_summary['max_error']}",
#                             "{orbit_precision_summary['beijing_time']}",
#                             "{orbit_precision_summary['3hr_err']}",
#                             "{orbit_precision_summary['6hr_err']}",
#                             "{orbit_precision_summary['12hr_err']}",
#                             "{orbit_precision_summary['18hr_err']}"
#                         )"""
#                     cur.execute(insert_sql)
#                     # print(merged_df.to_string())
#                     # print(merged_df.dtypes)
#
#                     # Write all points to orbit_precision_data table
#                     for index, row in merged_df.iterrows():
#                         ephemeris_id_int = int(row['ephemeris_id'])
#                         query = f"""INSERT INTO orbit_precision_data
#                                         (theoretical_x,theoretical_y,theoretical_z,timestamp,x,y,z,x_diff,y_diff,z_diff,theoretical_distance2,actual_distance2,error,ephemeris_id)
#                                         VALUES (
#                                             "{row['theoretical_x']}",
#                                             "{row['theoretical_y']}",
#                                             "{row['theoretical_z']}",
#                                             "{row['timestamp']}",
#                                             "{row['x']}",
#                                             "{row['y']}",
#                                             "{row['z']}",
#                                             "{row['x_diff']}",
#                                             "{row['y_diff']}",
#                                             "{row['z_diff']}",
#                                             "{row['theoretical_distance2']}",
#                                             "{row['actual_distance2']}",
#                                             "{row['error']}",
#                                             "{ephemeris_id_int}"
#                                         )"""
#
#                         cur.execute(query)
#
#                     # Commit the changes to the database
#                     conn.commit()
#
#                 except mariadb.Error as e:
#                     logging.info(f"Error: {e}")
#
#                 # step 3_2 push notification
#                 imgurl = OSS2.make_url(f"flight-control-analysis/data/{ephemeris_id}.png")
#                 content = od_precision_content(orbit_precision_summary, imgurl=imgurl)
#                 response = requests.post(note_url, json=json.loads(content), timeout=300)
#
#                 # Check response status
#                 if response.status_code == 200:
#                     logging.info("OD_precision posted successfully.")
#                     # print(response.text)
#                 else:
#                     logging.info(f"Failed to post content. Status code: {response.status_code}")
#                     logging.info(response.text)
#
#         except mariadb.Error as e:
#             logging.info(f"Error: {e}")
#
#         try:
#             # detele all data earlier than 7 days
#             delete_query = "DELETE FROM orbit_precision_data WHERE FROM_UNIXTIME(timestamp) < (NOW() - INTERVAL 7 DAY)"
#             cur.execute(delete_query)
#
#             # Commit the changes to the database
#             conn.commit()
#
#         except mariadb.Error as e:
#             logging.info(f"Error: {e}")
#
#         # Close cursor and connection
#         cur.close()
#         conn.close()
#     return "odpa_task_end"
