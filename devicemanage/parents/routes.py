from flask import jsonify, request, session, url_for, Blueprint
import bcrypt
from flask_mail import Message
from datetime import datetime, timedelta

from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import get_jwt
from flask_jwt_extended import create_access_token
from flask_jwt_extended import create_refresh_token
from flask_jwt_extended import jwt_required

from devicemanage import mail
from devicemanage import conn
from devicemanage import psycopg2
from devicemanage import timedelta
from devicemanage import constants
from devicemanage import response_errors
from devicemanage import format_timestamp as ft

# create an instance of this Blueprint
parents = Blueprint('parents','__name__')


@parents.route('/v1/parents/change-password',methods=['PUT'])
@jwt_required()
def changePassword():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()

    _json = request.json
    _oldPassword = _json['oldPassword']
    _newPassword = _json['newPassword']
    # Confirm old password
    cursor = conn.cursor(cursor_factory= psycopg2.extras.DictCursor)
    sql_get_password = """
    SELECT password FROM users
    WHERE id = %s
    """
    sql_where = (userID,)
    cursor.execute(sql_get_password,sql_where)
    row = cursor.fetchone()
    password_hash = row[0]
    if bcrypt.checkpw(_oldPassword.encode('utf-8'),password_hash.encode('utf-8')):
        # hash password
        hashed = bcrypt.hashpw(_newPassword.encode('utf-8'),bcrypt.gensalt())
        _newPassword = hashed.decode('utf-8')
        
        sql_change_password = """
        UPDATE users
        SET password = %s
        WHERE id = %s
        """
        sql_where = (_newPassword,userID)
        cursor.execute(sql_change_password,sql_where)
        conn.commit()
        cursor.close()
        resp = jsonify({"message":"Your password changed !!!"})
        resp.status = 200
        return resp
    else:
        resp = jsonify({"message":"Bad Request - Your old password is wrong"})
        resp.status_code = 400
        return resp
    
# {{HOST}}/v1/parent/register
@parents.route('/v1/parents/register', methods=['POST'])
def register():
    _json = request.json
    _email = _json['email']
    _password = _json['password']
    _fullname = _json['fullname']

    # check email already exists
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT * FROM users WHERE email = %s"
    sql_where = (_email,)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    if row != None:
        cursor.close()
        return response_errors.EmailExists()
    
    # hash password to save into database (khi encode password để hash thì sau đó ta phải decode password để save cái decode password đó vào database)
    hashed = bcrypt.hashpw(_password.encode('utf-8'), bcrypt.gensalt())
    _password = hashed.decode('utf-8')
    # insert recored
    sql = "INSERT INTO users(email,password,full_name,role_id,status) VALUES(%s,%s,%s,%s,%s)"
    sql_where = (_email, _password, _fullname, constants.RoleIDParent, constants.StatusActive)
    cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()
    
# Parent create account for child
@parents.route('/v1/parents/register-child', methods=['POST'])
@jwt_required()
def registerForChild():
    userID = get_jwt_identity()

    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()

    # validate child account
    _json = request.json
    _email = _json['email']
    _password = _json['password']
    _fullname = _json['fullname']

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT * FROM users WHERE email = %s"
    sql_where = (_email,)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    if row != None:
        return response_errors.EmailExists()
    
    # hash password to save into database (khi encode password để hash thì sau đó ta phải decode password để save cái decode password đó vào database)
    hashed = bcrypt.hashpw(_password.encode('utf-8'), bcrypt.gensalt())
    _password = hashed.decode('utf-8')
    # insert table users
    sql = "INSERT INTO users(email,password,full_name,role_id,status) VALUES(%s,%s,%s,%s,%s) RETURNING id"
    sql_where = (_email, _password, _fullname, constants.RoleIDChild, constants.StatusActive)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    childID = row[0]
    # insert table parent_child_relationships
    sql = "INSERT INTO parent_child_relationships(parent_id,child_id) VALUES(%s,%s)"
    sql_where = (userID, childID)
    cursor.execute(sql,sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@parents.route("/v1/parents/child-info", methods=['GET'])
@jwt_required()
def getChildInfo():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    # get childIDs and get every childID info in table users
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT child_id FROM parent_child_relationships WHERE parent_id = %s"
    sql_where = (userID,)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()

    if rows == []:
        return response_errors.NotData()

    childIDs = []
    for row in rows:
        childIDs.append(row[0])
    
    output = []
    for childID in childIDs:
        # get user info and devices of them
        sql = "SELECT * FROM users WHERE id = %s"
        sql_where = (childID,)
        cursor.execute(sql,sql_where)
        row = cursor.fetchone()
        data = {"id": row["id"], "fullName": row["full_name"], "email": row["email"], 
                "password": row["password"], "status": row["status"]}
        # get devices
        sql = "SELECT * from devices WHERE user_id = %s"
        sql_where = (childID,)
        cursor.execute(sql,sql_where)
        rows = cursor.fetchall()
        devices = [{'id': i['id'], 'deviceName': i['device_name']} for i in rows]
        data['devices'] = devices
        output.append(data)

    cursor.close()
    resp = jsonify(data=output)
    resp.status_code = 200
    return resp
    

@parents.route("/v1/parents/web-history/<int:childID>/<int:deviceID>/<int:days>", methods=['GET'])
@jwt_required()
def getWebHistory(childID, deviceID, days):
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    # validate child of parent
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT child_id FROM parent_child_relationships WHERE parent_id = %s AND child_id = %s"
    sql_where = (userID, childID)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchone()
    if rows == None:
        cursor.close()
        resp = jsonify({'message': "Not exist this child in your network!!"})
        resp.status_code = 400
        return resp
    # get web_history_id
    sql = """
        SELECT dwh.web_history_id FROM devices d
        INNER JOIN device_web_histories dwh
        ON d.id = dwh.device_id
        WHERE d.user_id = %s AND d.id = %s
    """
    sql_where = (childID, deviceID)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()

    if rows == []:
        return response_errors.NotData()

    webHistoryIDs = []
    for row in rows:
        webHistoryIDs.append(row[0])
    # get timestamp now and compare with create_at of table web_histories
    now = datetime.now()
    timeAfterDays = now - timedelta(days=days)
    # get web_history base on conditions
    sql = """
        SELECT * FROM web_histories 
        WHERE id = ANY(%s) AND created_at > %s
        ORDER BY created_at DESC
        """
    sql_where = (webHistoryIDs,timeAfterDays)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    data = [{'id': i['id'], 'url': i['url'], 'total_visit': i['total_visit'],
              'created_at': ft.format_timestamp(str(i['created_at']))} for i in rows]
    cursor.close()
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

@parents.route("/v1/parents/top-visit-web/<int:childID>", methods=['GET'])
@jwt_required()
def topVisitWeb(childID):
    #same with get web history
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    # validate child of parent
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT child_id FROM parent_child_relationships WHERE parent_id = %s AND child_id = %s"
    sql_where = (userID, childID)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchone()
    if rows == None:
        cursor.close()
        resp = jsonify({'message': "Not exist this child in your network!!"})
        resp.status_code = 400
        return resp
    # get web_history_id
    sql = """
        SELECT dwh.web_history_id FROM devices d
        INNER JOIN device_web_histories dwh
        ON d.id = dwh.device_id
        WHERE d.user_id = %s
    """
    sql_where = (childID,)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()
    webHistoryIDs = []
    for row in rows:
        webHistoryIDs.append(row[0])
    # get top visit web_history 
    sql = """
        SELECT * FROM web_histories 
        WHERE id = ANY(%s)
        ORDER BY total_visit DESC
        LIMIT 20
        """
    sql_where = (webHistoryIDs,)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    print(rows)
    data = [{'id': i['id'], 'url': i['url'], 'total_visit': i['total_visit'],
              'created_at': ft.format_timestamp(str(i['created_at']))} for i in rows]
    cursor.close()
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

@parents.route("/v1/parents/keyboard-log/<int:childID>/<int:deviceID>/<int:days>", methods=['GET'])
@jwt_required()
def getKeyboardLog(childID, deviceID, days):
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    # validate child of parent
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT child_id FROM parent_child_relationships WHERE parent_id = %s AND child_id = %s"
    sql_where = (userID, childID)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    if row == None:
        cursor.close()
        resp = jsonify({'message': "Not exist this child in your network!!"})
        resp.status_code = 400
        return resp
    # get keyboard_log_id
    sql = """
        SELECT dkl.keyboard_log_id FROM devices d
        INNER JOIN device_keyboard_logs dkl
        ON d.id = dkl.device_id
        WHERE d.user_id = %s AND d.id = %s
    """
    sql_where = (childID, deviceID)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()

    if rows == []:
        return response_errors.NotData()

    keyboardLogIDs = []
    for row in rows:
        keyboardLogIDs.append(row[0])
    # get timestamp now and compare with create_at of table keyboard_logs
    now = datetime.now()
    timeAfterDays = now - timedelta(days=days)
    # get web_history base on conditions
    sql = """
        SELECT * FROM keyboard_logs 
        WHERE id = ANY(%s) AND created_at > %s
        ORDER BY created_at DESC
        """
    sql_where = (keyboardLogIDs,timeAfterDays)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    data = [{'id': i['id'], 'key_stroke': i['key_stroke'], 'total_visit': i['total_visit'],
              'created_at': ft.format_timestamp(str(i['created_at']))} for i in rows]
    cursor.close()
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

@parents.route("/v1/parents/top-keyboard-log/<int:childID>", methods=['GET'])
@jwt_required()
def topKeyboardLog(childID):
    #same with get keyboard log
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    # validate child of parent
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT child_id FROM parent_child_relationships WHERE parent_id = %s AND child_id = %s"
    sql_where = (userID, childID)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchone()
    if rows == None:
        cursor.close()
        resp = jsonify({'message': "Not exist this child in your network!!"})
        resp.status_code = 400
        return resp
    # get keyboard_log_id
    sql = """
        SELECT dkl.keyboard_log_id FROM devices d
        INNER JOIN device_keyboard_logs dkl
        ON d.id = dkl.device_id
        WHERE d.user_id = %s
    """
    sql_where = (childID,)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()
    keyboardLogIDs = []
    for row in rows:
        keyboardLogIDs.append(row[0])
    # get top keyboard_log 
    sql = """
        SELECT * FROM keyboard_logs 
        WHERE id = ANY(%s)
        ORDER BY total_visit DESC
        LIMIT 20
        """
    sql_where = (keyboardLogIDs,)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    print(rows)
    data = [{'id': i['id'], 'key_stroke': i['key_stroke'], 'total_visit': i['total_visit'],
              'created_at': ft.format_timestamp(str(i['created_at']))} for i in rows]
    cursor.close()
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

# 1 child have many device so i have to add blocked website in all this device
@parents.route('/v1/parents/block-website', methods=['POST'])
@jwt_required()
def sendBlockedWebsite():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    
    _json = request.json
    _blockedWebsites = _json["blockedWebsites"]
    _childID = _json['childID']

    # validate parent(userID) has contain childID
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT id FROM parent_child_relationships WHERE parent_id = %s AND child_id = %s"
    sql_where = (userID, _childID)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    if row == None:
        resp = jsonify({'message': "You're not manage this child!!"})
        resp.status_code = 400
        return resp
    
    # find devices of child
    sql = """
        SELECT devices.id FROM users
        INNER JOIN devices
        ON devices.user_id = users.id
        WHERE users.id = %s
        """
    sql_where = (_childID,)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()
    # add block website in all device of child
    for row in rows:
        deviceID = row['id']
        for i in _blockedWebsites:
            # insert table blocked_websites
            sql = "INSERT INTO blocked_websites(url,block_by,is_active) VALUES(%s,%s,%s) RETURNING id"
            sql_where = (i['url'],userID,True)
            cursor.execute(sql, sql_where)
            row = cursor.fetchone()
            blockWebsiteID = row[0]
            # insert table device_blocked_websites
            sql = "INSERT INTO device_blocked_websites(device_id,block_website_id) VALUES(%s,%s)"
            sql_where = (deviceID, blockWebsiteID)
            cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@parents.route('/v1/parents/block-website/<int:childID>', methods=['GET'])
@jwt_required()
def getBlockWebsite(childID):
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']
    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    # validate child of parent
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT child_id FROM parent_child_relationships WHERE parent_id = %s AND child_id = %s"
    sql_where = (userID, childID)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchone()
    if rows == None:
        cursor.close()
        resp = jsonify({'message': "Not exist this child in your network!!"})
        resp.status_code = 400
        return resp
    
    # get deviceIDs of child
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT id, device_name FROM devices WHERE user_id = %s"
    sql_where = (childID,)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()

    if rows == []:
        resp = jsonify({'message': "Your child device doesn't exists in system!!"})
        resp.status_code = 400
        return resp
    
    output = dict()
    for row in rows:
        deviceID = row['id']
        deviceName = row['device_name']
        sql = """
            SELECT bw.id, bw.url, bw.block_by, bw.is_active FROM device_blocked_websites dbw
            INNER JOIN blocked_websites bw
            ON dbw.block_website_id = bw.id
            WHERE dbw.device_id = %s
        """
        sql_where = (deviceID,)
        cursor.execute(sql,sql_where)
        rows = cursor.fetchall()
        data = [{'id': i['id'], 'url': i['url'], 'blockBy': i['block_by'], 'isActive': i['is_active']} for i in rows]
        output[deviceName] = data
    resp = jsonify(data=output)
    cursor.close()
    resp.status_code = 200
    return resp


@parents.route('/v1/parents/block/<int:childID>', methods=['POST'])
@jwt_required()
def blockUser(childID):
    data = get_jwt()
    roleName = data['role_name']
    parentID = get_jwt_identity()

    if roleName != constants.RoleNameParent:
        return response_errors.NotAuthenticateParent()
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # check if id is child of parent
    sql = "select child_id from parent_child_relationships where parent_id = %s"
    sql_where = (parentID,)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()
    childIDs = [row[0] for row in rows]
    if not (childID in childIDs):
        return response_errors.UserNotExists()
    # Get status to switch 
    sql = "SELECT status FROM users WHERE id = %s"
    sql_where = (childID,)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    if row == None:
        return response_errors.UserNotExists()
    switchStatus = constants.SwitchStatus[row['status']]
    # Change status
    sql = "UPDATE users SET status = %s WHERE id = %s"
    sql_where = (switchStatus, childID)
    cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()


# Create a route to authenticate your users and return token.
# @parents.route('/login', methods=['POST'])
# def login():
#     _json = request.json
#     # validate the received values
#     if 'phonenumber' in _json.keys() and 'password' in _json.keys():
#         _phonenumber = _json['phonenumber']
#         _password = _json['password']
#         # check user exists
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

#         sql = "SELECT * FROM users WHERE phonenumber = %s"
#         sql_where = (_phonenumber,)

#         cursor.execute(sql, sql_where)
#         row = cursor.fetchone()
#         cursor.close()
#         if row:
#             password_hash = row['password']
#             userid = row['userid']
#             rolename = row['rolename']
#             status = row['status']
#             if status == 'inactive':
#                 resp = jsonify({"message":"Locked - Your account is locked! You can contact with our employee to know reason!"})
#                 resp.status_code = 423
#                 return resp
#             elif bcrypt.checkpw(_password.encode('utf-8'), password_hash.encode('utf-8')):
#                 # create token and refresh token
#                 additional_claims = {"rolename":rolename}
#                 access_token = create_access_token(identity=userid,additional_claims=additional_claims)
#                 refresh_token = create_refresh_token(identity=userid,additional_claims=additional_claims)
#                 session['access_token'] = access_token
#                 resp = jsonify(access_token=access_token,refresh_token=refresh_token)
#                 resp.status_code = 200
#                 return resp
#             else:
#                 resp = jsonify({'message': 'Bad Request - Wrong password!'})
#                 resp.status_code = 400
#                 return resp
#         else:
#             resp = jsonify({'message': 'Bad Request - Your phone does not exist in the system!'})
#             resp.status_code = 400
#             return resp
#     else:
#         resp = jsonify({'message': 'Bad Request - Missing input!'})
#         resp.status_code = 400
#         return resp


# @parents.route('/refresh', methods=['POST'])
# @jwt_required(refresh=True)
# def refresh():
#     userid = get_jwt_identity
#     additional_claims = get_jwt()
#     access_token = create_access_token(identity=userid, additional_claims=additional_claims)
#     return jsonify(access_token=access_token)


# @parents.route('/logout', methods=['POST'])
# def logout():
#     if 'access_token' in session:
#         session.pop('access_token', None)
#     resp =  jsonify({'message': 'You successfully logged out'})
#     resp.status_code = 200
#     return resp


# @parents.route('/alldrink')
# def home():
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

#     sql = """
#     SELECT
#         drinks.drinkid, drinkname, drinkimage,
#         categoryid, MIN(price), status
#     FROM drinks
#     INNER JOIN sizes
#         ON sizes.drinkid = drinks.drinkid
#     WHERE status = 'Available'
#     GROUP BY drinks.drinkid
#     ORDER BY drinks.drinkid
#     """
#     cursor.execute(sql)
#     row = cursor.fetchall()
#     cursor.close()
#     drinks = [{'drinkid': drink[0], 'drinkname': drink[1], 'drinkimage': drink[2],
#                 'categoryid': drink[3],'price':float(drink[4]) ,'status': drink[5]} for drink in row]
#     if drinks == None:
#         resp = jsonify({'message':"Items not found!!"})
#         resp.status_code = 400
#         return resp
#     else:
#         resp = jsonify(data=drinks)
#         resp.status_code = 200
#         return resp



# # drink detail
# @parents.route('/drink/<int:id>', methods=['GET'])
# def drinkdetail(id):
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

#     sql_drink = "SELECT * FROM drinks WHERE drinkid = %s and status = 'Available'"

#     # Column contains topping's name and price of a drink
#     sql_topping = """
#     select 
#         t.toppingid,nametopping,price 
#     from drinks as d 
#     inner join 
#         drinktopping as dt 
#     on 
#         dt.drinkid = d.drinkid 
#     inner join 
#         toppings as t 
#     on 
#         t.toppingid = dt.toppingid 
#     where d.drinkid = %s
#     """

#     # Column contains size's name and price of a drink
#     sql_size = """ 
#         select 
#             s.sizeid,namesize,price from drinks as d
#         inner join 
#             sizes as s 
#         on s.drinkid = d.drinkid
#         where d.drinkid = %s
#         """

#     sql_where = (id,)
#     # drink
#     cursor.execute(sql_drink, sql_where)
#     drink = cursor.fetchone()
#     if drink == None:
#         cursor.close()
#         resp = jsonify({'message':'Not Found - Item not found!'})
#         resp.status_code = 404
#         return resp
#     _drink = {'drinkid': drink['drinkid'], 'drinkname': drink['drinkname'], 'drinkimage': drink['drinkimage'],
#                    'description': drink['description'],'status': drink['status'],'categoryid':drink['categoryid']}
#     # topping
#     cursor.execute(sql_topping,sql_where)
#     topping = cursor.fetchall()
#     if topping != None:
#         _topping = [{"toppingid": i['toppingid'], "nametopping": i['nametopping'], "price": float(i['price'])} for i in topping]
#     else:
#         _topping = []
#     # size
#     cursor.execute(sql_size,sql_where)
#     size = cursor.fetchall()
#     if size != None:
#         _size = [{"sizeid": j['sizeid'], "namesize": j['namesize'], "price": float(j['price'])} for j in size]
#     else:
#         _size = []
#     cursor.close()
#     resp = jsonify(data={'drink':_drink,'topping':_topping,'size':_size})
#     resp.status_code = 200
#     return resp
        


# # category info
# @parents.route('/drink/category', methods=['GET'])
# def category_info():
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

#     sql = """
#     SELECT * FROM categories
#     """
#     cursor.execute(sql)
#     row = cursor.fetchall()
#     categories = [{'categoryid': category[0], 'categoryname': category[1]} for category in row]
#     cursor.close()
#     if categories:
#         resp = jsonify(categories=categories)
#         resp.status_code = 200
#         return resp
#     else:
#         resp = jsonify({'message':'Not Found!'})
#         resp.status_code = 404
#         return resp


# send email to reset password
def sendEmail(userid,_email):
    token = create_access_token(identity=userid,expires_delta=timedelta(minutes=5))
    html_content = f""" 
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" type="text/css" hs-webfonts="true" href="https://fonts.googleapis.com/css?family=Lato|Lato:i,b,bi">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style type="text/css">
          h1{{font-size:56px}}
          p{{font-weight:100}}
          td{{vertical-align:top}}
          #email{{margin:auto;width:600px;background-color:#fff}}
        </style>
    </head>
    <body bgcolor="#F5F8FA" style="width: 100%; font-family: "Helvetica Neue", Helvetica, sans-serif; font-size:18px;">
    <div id="email">
        <table role="presentation" width="100%">
            <tr>
                <td bgcolor="#F6AC31" align="center" style="color: white;">
                    <h1> Ứng Dụng<br> Đặt Đồ Uống!</h1>
                </td>
        </table>
        <table role="presentation" border="0" cellpadding="0" cellspacing="10px" style="padding: 30px 30px 30px 60px;">
            <tr>
                <td>
                    <h2>
                        Để đặt lại mật khẩu trong ứng dụng đặt đồ uống online. Hãy nhấn vào link dưới đây:
                        <a href={url_for("parents.verifyTokenEmail",jwt=token,_external=True)}>
                            <br>Bấm vào đây!
                        </a>
                    </h2>
                    <p>
                        Nếu bạn không phải là người gửi yêu cầu đổi mật khẩu. Hãy bỏ qua mail thông báo này.
                    </p>
                </td>
            </tr>
        </table>
    </div>
    </body>
    </html>
    """
    msg = Message('YÊU CẦU ĐẶT LẠI MẬT KHẨU', sender='noreply@gmail.com', recipients=[_email], html=html_content)
    mail.send(msg)

#{{HOST}}/v1/parents/resetPassword?email=<Your email>
@parents.route('/v1/parents/resetPassword',methods = ['POST'])
def resetPassword():
    _email = request.args.get('email')
    
    # check email request has contained in the database
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql_check_email = """
    SELECT id FROM users
    WHERE email = %s
    """
    sql_where = (_email,)
    cursor.execute(sql_check_email,sql_where)
    row = cursor.fetchone()
    cursor.close()
    
    if row == None:
        resp = jsonify({"message":"Not Found - Email doesn't exists in system!"})
        resp.status_code = 404
        return resp
    userID = row['id']
    sendEmail(userID,_email)
    resp = jsonify({"message":"Hệ thống đã gửi cho bạn mail thông báo thay đổi mật khẩu. Hãy vào mail để kiểm tra!"})
    resp.status_code = 200
    return resp
        



#{{HOST}}/resetPassword/token?jwt=<Your token>
@parents.route('/resetPassword/token',methods=['PUT','GET'])
@jwt_required(locations="query_string")
def verifyTokenEmail():
    userid = get_jwt_identity()
    if userid:
        # hash password '123'
        _password = '123'
        hashed = bcrypt.hashpw(_password.encode('utf-8'), bcrypt.gensalt())
        _password_hash = hashed.decode('utf-8')

        # update password into database
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql_change_password_default = """
        UPDATE users
        SET password = %s
        WHERE userid = %s
        """
        sql_where = (_password_hash,userid)
        cursor.execute(sql_change_password_default,sql_where)
        conn.commit()
        cursor.close()

        resp = jsonify({"message":"Your password changed to '123'!!!"})
        resp.status_code = 200
        return resp
    else:
        resp = jsonify({"message":"Not Found - Account doesn't exists"})
        resp.status_code = 404
        return resp
