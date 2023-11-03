from flask import jsonify, request, Blueprint
import bcrypt
from devicemanage import conn
from devicemanage import psycopg2

from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt

from devicemanage import format_timestamp as ft
from devicemanage import constants
from devicemanage import response_errors


# create an instance of this Blueprint
childs = Blueprint('childs','__name__')


@childs.route('/v1/childs/add-device', methods=['POST'])
@jwt_required()
def addDevice():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameChild:
        return response_errors.NotAuthenticateChild()
    
    _json = request.json
    _deviceName = _json['deviceName']
    
    # Check to see if the device is registered
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = """
        SELECT * FROM users
        INNER JOIN devices
        ON users.id = devices.user_id
        WHERE users.id = %s AND devices.device_name = %s
        """
    sql_where = (userID,_deviceName)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    if row != None:
        resp = jsonify({'message':'This device has already been registered!!'})
        resp.status_code = 400
        return resp
    # insert table devices
    sql = "INSERT INTO devices(device_name,user_id) VALUES(%s,%s)"
    sql_where = (_deviceName, userID)
    cursor.execute(sql,sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@childs.route('/v1/childs/web-history', methods=['POST'])
@jwt_required()
def sendWebHistory():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameChild:
        return response_errors.NotAuthenticateChild()
    
    _json = request.json
    _histories = _json["histories"]
    _deviceName = _json['deviceName']

    # validate userID and deviceName
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT id FROM devices WHERE user_id = %s AND device_name = %s"
    sql_where = (userID, _deviceName)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()

    if row == None:
        return response_errors.DeviceNotExists()

    deviceID = row[0]
    for i in _histories:
        # convert _createdAt(webkit_timestamp|1/1/1601) to unix_timestamp (1/1/1970)
        createdAt = ft.date_from_webkit(i['createdAt'])
        # insert table web_histories
        sql = "INSERT INTO web_histories(url,created_at,total_visit) VALUES(%s,%s,%s) RETURNING id"
        sql_where = (i['url'], createdAt,i['totalVisit'])
        cursor.execute(sql, sql_where)
        row = cursor.fetchone()
        webHistoryID = row[0]
        # insert table device_web_histories
        sql = "INSERT INTO device_web_histories(device_id,web_history_id) VALUES(%s,%s)"
        sql_where = (deviceID, webHistoryID)
        cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@childs.route('/v1/childs/keyboard-log', methods=['POST'])
@jwt_required()
def sendKeyboardLog():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameChild:
        return response_errors.NotAuthenticateChild()
    
    _json = request.json
    _keyboardLogs = _json["keyboardLogs"]
    _deviceName = _json['deviceName']

    # validate userID and deviceName
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT id FROM devices WHERE user_id = %s AND device_name = %s"
    sql_where = (userID, _deviceName)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()

    if row == None:
        return response_errors.DeviceNotExists()

    deviceID = row[0]
    for i in _keyboardLogs:
        # convert _createdAt(webkit_timestamp|1/1/1601) to unix_timestamp (1/1/1970)
        createdAt = ft.date_from_webkit(i['createdAt'])
        # insert table keyboard_logs
        sql = "INSERT INTO keyboard_logs(key_stroke,created_at,total_visit) VALUES(%s,%s,%s) RETURNING id"
        sql_where = (i['keyStroke'], createdAt,i['totalVisit'])
        cursor.execute(sql, sql_where)
        row = cursor.fetchone()
        keyboardLogID = row[0]
        # insert table device_keyboard_logs
        sql = "INSERT INTO device_keyboard_logs(device_id,keyboard_log_id) VALUES(%s,%s)"
        sql_where = (deviceID, keyboardLogID)
        cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@childs.route('/v1/childs/block-website', methods=['GET'])
@jwt_required()
def getBlockedWebsite():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    _json = request.json
    _deviceName = _json["deviceName"]

    if roleName != constants.RoleNameChild:
        return response_errors.NotAuthenticateChild()

    # get deviceID
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT id FROM devices WHERE user_id = %s AND device_name = %s"
    sql_where = (userID, _deviceName)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()

    if row == None:
        return response_errors.DeviceNotExists()

    deviceID = row[0]
    sql = """
        SELECT bw.id, bw.url, bw.block_by FROM device_blocked_websites dbw
        INNER JOIN blocked_websites bw
        ON dbw.block_website_id = bw.id
        WHERE dbw.device_id = %s AND bw.is_active = %s
    """
    sql_where = (deviceID,True)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()
    data = [{'id': i['id'], 'url': i['url'], 'blockBy': i['block_by']} for i in rows]
    cursor.close()
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

# get timestamp of chrome to compare with time in history
@childs.route('/v1/childs/web-history/latest-time/<int:deviceID>', methods=['GET'])
@jwt_required()
def getTimestampLatestHistoryWeb(deviceID):
    # validate device
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameChild:
        return response_errors.NotAuthenticateChild()
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = """
        SELECT * FROM devices
        WHERE id = %s AND user_id = %s
    """
    sql_where = (deviceID, userID)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    if row == None:
        return response_errors.DeviceNotExists()
    # get latest timestamp
    sql = """
        SELECT wh.created_at FROM devices d
        LEFT JOIN device_web_histories dwh
        ON d.id = dwh.device_id
        LEFT JOIN web_histories wh
        ON wh.id = dwh.web_history_id
        WHERE d.id = %s
        ORDER BY wh.created_at DESC
        LIMIT 1
    """
    sql_where = (deviceID,)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    cursor.close()
    if row[0] == None:
        # return default of type timestamp
        resp = jsonify({'data': 11644492000})
        resp.status_code = 200
        return resp
    # return latest web history time
    webKitTimestamp = ft.datetime_to_webkit_timestamp(row[0])
    resp = jsonify({'data': webKitTimestamp})
    resp.status_code = 200
    return resp