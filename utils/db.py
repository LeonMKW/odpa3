# -*- coding: UTF-8 -*-

import pymongo
from influxdb import InfluxDBClient
import logging
from bson import ObjectId
import logging
import mariadb
import sys
import oss2
import pandas as pd
import json


class Influxdb(object):
    """
    influxdb数据库操作
    """

    def __init__(self, _user, _pwd, _dbname):
        self._user = _user
        self._pwd = _pwd
        self._dbname = _dbname

    def connect(self, _host, _port):
        client = InfluxDBClient(_host, _port, self._user, self._pwd, self._dbname)
        return client

    def get_all(self, _client, measurement, fields, filters=None, limit=1000000):
        query_str = 'select _satelliteCode,' + ','.join([x for x in fields]) \
                    + ' from \"' + measurement + '\" ' + filters \
                    + ' limit ' + str(limit)
        # print(query_str)
        result = _client.query(query_str)
        if len(result) == 0:
            return {}
        points = list(result.get_points())
        return points

    def get_distinct_alt(self, _client, start_time, end_time, satellitecode, limit=1):
        # Query to get data within the time range
        query_str = f'SELECT "alt", "_satelliteCode" FROM "alt" WHERE "_satelliteCode" = \'{satellitecode}\' AND time >= \'{start_time}\' AND time <= \'{end_time}\' ORDER BY time DESC LIMIT {limit}'
        result = _client.query(query_str)

        points = list(result.get_points())

        # If no data found within the range, get the closest available data before the start time
        if len(points) == 0:
            nearest_query = f'SELECT "alt", "_satelliteCode" FROM "alt" WHERE "_satelliteCode" = \'{satellitecode}\' AND time < \'{start_time}\' ORDER BY time DESC LIMIT 1'
            result = _client.query(nearest_query)
            points = list(result.get_points())

        return points

def check_str_is_cn(str_all):
    """检查字符串中是否有中文字符"""
    for s in str_all:
        if '\u4e00' <= s <= '\u9fa5':
            return True
    return False


def init_val():
    global progress
    progress = {'progress': 0, 'total': 0}


def pbar():
    global progress
    progress = {}
    return progress


def set_value(key, value):
    # global progress
    progress[key] = value


# mongo = None


def get_mongo():
    return mongo


class Mongo(object):

    def __init__(self, hosts, _mongo_auth_source, _mongo_initdb_root_usename, _mongo_initdb_root_password):
        self._MONGO_HOSTS = hosts
        self._MONGO_AUTH_SOURCE = _mongo_auth_source
        self._MONGO_INITDB_ROOT_USERNAME = _mongo_initdb_root_usename
        self._MONGO_INITDB_ROOT_PASSWORD = _mongo_initdb_root_password
        self.client = pymongo.MongoClient(
            host=self._MONGO_HOSTS,
            serverSelectionTimeoutMS=3000,  # 3 second timeout
            authSource=str(self._MONGO_AUTH_SOURCE),
            username=str(self._MONGO_INITDB_ROOT_USERNAME),
            password=str(self._MONGO_INITDB_ROOT_PASSWORD)
        )
        global mongo
        mongo = self

    def get_connection(self):
        return self.client

    # READ
    def find_one_data(self, query, collection):
        result = self.client['orbit_analysis'][str(collection)].find_one(query)
        return result

    def get_doc_by_satid_tf(self, collection, satid, ts1, ts2):
        query = {
            "spacecraftId": satid,
            "timestamp": {
                "$gte": ts1,
                "$lte": ts2
            }
        }
        response = self.client['orbit_analysis'][collection].find(query)
        return response

    def get_largest_end_time_doc(self, collection, satid):
        query = {
            "spacecraftId": satid
        }
        response = self.client['orbit_analysis'][collection].find(query).sort("timestamp", -1).limit(1)
        return response

    def get_doc_closest_but_not_greater(self, collection, satid, target_ts):
        query = {
            "spacecraftId": satid,
            "timestamp": {
                "$lt": target_ts
            }
        }
        response = self.client['orbit_analysis'][collection].find(query).sort("timestamp", -1).limit(1)
        return response

    def get_doc_closest_but_not_less(self, collection, satid, target_ts):
        query = {
            "spacecraftId": str(satid),
            "timestamp": {"$gte": target_ts}
        }

        response = self.client['orbit_analysis'][collection].find(query).sort("timestamp", 1).limit(1)
        return response if response else None

    # WRITE
    def write_one_data(self, data, collection):
        result = self.client['orbit_analysis'][str(collection)].insert_one(data)
        return result

    # UPDATE
    def update_one_data(self, data, collection, composite_key):
        result = self.client['orbit_analysis'][str(collection)].update_one(composite_key, {"$set": data}, upsert=True)
        return result


class OSS2:
    def __init__(self, _endpoint, _access, _secret):
        self.endpoint = _endpoint
        self.access = _access
        self.secret = _secret

    def get_oss_client(self):
        """
        Establish a connection to the Aliyun OSS server.
        Returns an OSS client object.
        """
        auth = oss2.Auth(self.access, self.secret)
        client = oss2.Bucket(auth, self.endpoint, 'odprecision')  # Replace 'bucket_name' with your actual bucket name
        return client

    def upload_file(self, key, filename):
        """上传一个本地文件到OSS的普通文件。

        :param str key: 上传到OSS的文件名
        :param str filename: 本地文件名，需要有可读权限

        :param headers: 用户指定的HTTP头部。可以指定Content-Type、Content-MD5、x-oss-meta-开头的头部等
        :type headers: 可以是dict，建议是oss2.CaseInsensitiveDict

        :param progress_callback: 用户指定的进度回调函数。参考 :ref:`progress_callback`

        :return: :class:`PutObjectResult <oss2.models.PutObjectResult>`
        """

        client = self.get_oss_client()
        client.put_object_from_file(key, filename)

        logging.info(f"{filename} successfully uploaded as object {key} to bucket odprecision")

    def make_url(self, image_name):
        client = self.get_oss_client()
        imgurl = client.sign_url('GET', image_name, 2592000000)
        # print(imgurl)
        return imgurl
