from task.od_algorithm import orbit_precision_calculation_step1, \
    orbit_precision_calculation_step2_1
from utils.od_utils import satellite_properties
from datetime import datetime, timedelta
import pytz
import logging
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

        # Ensure correct timestamp conversion (WITHOUT -8 hours adjustment)
        tf1_timestamp = int(datetime.strptime(epoch_time_utc, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc).timestamp())
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
            ephemeris_with_err['timestamp'] = tf1_timestamp  # Store UTC timestamp directly
            mongo.update_one_data(data=ephemeris_with_err, collection='ephemeris_pa', composite_key=ephemeris_query)
        else:
            logging.info(f"Ephemeris ID {ephemeris_id} does not exist in 'ephemeris_pa'. Creating a new record.")
            ephemeris_with_err['timestamp'] = tf1_timestamp  # Store UTC timestamp directly
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

        # Add Beijing time separately, for **reference only**, not for database storage
        utc = pytz.utc
        beijing = pytz.timezone('Asia/Shanghai')
        timestamp_utc = datetime.strptime(ephemeris_with_err['epochTimeUTC'], '%Y-%m-%dT%H:%M:%S.%fZ')
        utc_dt = utc.localize(timestamp_utc)  # Localize UTC time
        beijing_dt = utc_dt.astimezone(beijing)  # Convert to Beijing time
        ephemeris_with_err['beijing_time'] = beijing_dt.strftime('%Y-%m-%d %H:%M:%S')

        # Log results
        logging.info(f"{satIDs} odpa pipeline complete")

    return "odpa_task_end"

