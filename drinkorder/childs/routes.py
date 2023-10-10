from flask import jsonify, request, Blueprint
import bcrypt
from drinkorder import conn
from drinkorder import psycopg2

from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt

from drinkorder import format_timestamp as ft
from drinkorder import constants
from drinkorder import response_errors


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
    
    # insert table devices
    _json = request.json
    _deviceName = _json['deviceName']

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
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
        resp = jsonify({'message': "Your device doesn't exists in system!!"})
        resp.status_code = 400
        return resp

    deviveID = row[0]
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
        sql_where = (deviveID, webHistoryID)
        cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()





# get user information and change user information
# @childs.route('/userInfo', methods=['GET','PUT'])
# @jwt_required()
# def user_info():
#     userid = get_jwt_identity()
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#     if request.method == 'GET':
#         sql = """
#         SELECT 
#             userid,phonenumber,fullname,rolename,address,email 
#         FROM users WHERE userid = %s
#         """
#         sql_where = (userid,)
#         cursor.execute(sql,sql_where)
#         row = cursor.fetchone()
#         user = {'userid':row['userid'],'phonenumber':row['phonenumber'],
#                 'fullname':row['fullname'],'rolename':row['rolename'],
#                 'address':row['address'],'email':row['email']}
#         cursor.close()
#         if user:
#             resp = jsonify(data=user)
#             resp.status_code = 200
#             return resp
#         else:
#             resp = jsonify({"message": "Not Found!"})
#             resp.status_code = 404
#             return resp
    
#     elif request.method == 'PUT':
#         _json = request.json
#         _fullname = _json['fullname']
#         _address = _json['address']

#         sql = """
#         UPDATE users 
#         SET fullname = %s,
#             address = %s
#         WHERE userid = %s
#         """
#         sql_where = (_fullname,_address,userid)
#         cursor.execute(sql,sql_where)
#         conn.commit()
#         cursor.close()
#         resp = jsonify({"message":"User information updated!"})
#         resp.status_code = 200
#         return resp
    
#     cursor.close()
#     resp = jsonify({"message":"Not Implemented - Server doesn't undertand your request method"})
#     resp.status_code = 501
#     return resp
    


# # user create order
# @childs.route('/order/preparing',methods = ['POST'])
# @jwt_required()
# def createOrder():
#     userid = get_jwt_identity()

#     _json = request.json
#     _order = _json['order']
#     _item = _json['item']
#     # Trường hợp đang lưu vào database mà gặp lỗi thì ta vẫn có thể handle được.
#     try:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         # create order and get orderid
#         sql_create_order = """
#         INSERT INTO 
#             orders(userid,totalprice,address,phonenumber,note,status,orderdate)
#         VALUES(%s,%s,%s,%s,%s,'Preparing',LOCALTIMESTAMP)
#         RETURNING orderid
#         """
#         sql_where = (userid,_order['totalprice'],_order['address'],_order['phonenumber'],_order['note'])
#         cursor.execute(sql_create_order,sql_where)
#         row = cursor.fetchone()
#         orderid = row[0]
#         # conn.commit()

#         # add record to items table and get itemid
#         # loop run, cause we have many item in a request
#         lst_itemid = []
#         for i in _item:
#             # we have to handling add record to items and itemtopping table
#             sql_add_item = """
#             INSERT INTO
#                 items(drinkid,price,itemquantity,sizeid)
#             VALUES(%s,%s,%s,%s)
#             RETURNING itemid
#             """
#             sql_where = (i['drinkid'],i['price'],i['itemquantity'],i['sizeid'])
#             cursor.execute(sql_add_item,sql_where)
#             row = cursor.fetchone()
#             # conn.commit()
#             itemid = row[0]
#             lst_itemid.append(itemid)

#             # insert data to itemtopping table
#             for j in i['toppingid']:
#                 sql_add_itemtopping = """
#                 INSERT INTO
#                     itemtopping(itemid,toppingid)
#                 VALUES(%s,%s)
#                 """
#                 sql_where = (itemid,j)
#                 cursor.execute(sql_add_itemtopping,sql_where)
#                 # conn.commit()

#         # insert data to itemorder
#         for i in lst_itemid:
#             sql_add_itemorder = """
#             INSERT INTO itemorder(orderid,itemid)
#             VALUES(%s,%s)
#             """
#             sql_where = (orderid,i)
#             cursor.execute(sql_add_itemorder,sql_where)
#             # conn.commit()
#         conn.commit()   # thay vì mỗi lần thêm dữ liệu vào một bảng là ta đi commit, thì giờ ta lưu hết vào trong DB rồi mới commit sau.
#         cursor.close()

#         resp = jsonify({"message":"Completed order! Your order are preparing!!!"})
#         resp.status_code = 200
#         return resp
#     except:
#         resp = jsonify({"message":"Internal Server Error"})
#         resp.status_code = 500
#         return resp
    

# # user cancelled order
# @childs.route('/order/cancel/<int:orderid>', methods = ['PUT'])
# @jwt_required()
# def usercancelledOrder(orderid):
#     userid = get_jwt_identity()

#     # check orderid already exists and it have a 'Initialize' or 'Preparing' status 
#     # then system allows for cancel order 
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
#     sql_check_constraint = """
#     SELECT orderid FROM orders
#     WHERE
#         orderid = %s
#         AND
#             userid = %s
#         AND
#             (status = %s OR status = %s)
#     """

#     sql_where = (orderid,userid,'Initialize','Preparing')
#     cursor.execute(sql_check_constraint,sql_where)
#     row = cursor.fetchone()

#     if row:
#         # update order status to 'Cancelled'
#         sql_cancel = """
#         UPDATE orders
#         SET status = %s
#         WHERE orderid = %s
#         """
#         sql_where = ('Cancelled',orderid)
#         cursor.execute(sql_cancel,sql_where)
#         conn.commit()
#         cursor.close()
#         resp = jsonify({"message":"Your order status updated to 'Cancelled'!"})
#         resp.status_code = 200
#         return resp

#     else:
#         cursor.close()
#         resp = jsonify({"message":"Your order cannot cancel"})
#         resp.status_code = 400
#         return resp



# # user confirm the order is 'Completed'
# @childs.route('/order/complete/<int:orderid>',methods=['PUT'])
# @jwt_required()
# def userConfirmCompletedOrder(orderid):
#     userid = get_jwt_identity()

#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#     # check order status is 'Delivering'or not.
#     sql_check_delevering = """
#     SELECT orderid FROM orders
#     WHERE orderid = %s AND userid = %s AND status = 'Delivering' 
#     """
#     sql_where = (orderid,userid)
#     cursor.execute(sql_check_delevering,sql_where)
#     row = cursor.fetchone()

#     if row:
#         sql_completed = """
#         UPDATE orders
#         SET status = 'Completed'
#         WHERE orderid = %s
#         """
#         sql_where = (orderid,)
#         # update order status to 'Completed'
#         cursor.execute(sql_completed,sql_where)
#         conn.commit()
#         cursor.close()
#         resp = jsonify({"message":"Updated order status to 'Completed'!"})
#         resp.status_code = 200
#         return resp
#     else:
#         cursor.close()
#         resp = jsonify({"message":"You're cannot change the order status to 'Completed'!"})
#         resp.status_code = 400
#         return resp



# # user view order history or current 
# @childs.route('/order/<status>', methods = ['GET'])
# @jwt_required()
# def userOrderHistory(status):
#     userid = get_jwt_identity()

#     orderstatus = []
#     if status == 'history':
#         orderstatus=['Completed','Cancelled']
#     elif status == 'current':
#         orderstatus=['Preparing','Delivering']

#     if orderstatus == []:
#         resp = jsonify({"message":"Bad Request!!"})
#         resp.status_code = 400
#         return resp

#     try:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
#         # user get order 'history' or 'current'
#         sql_history = """
#         SELECT 
#             orderid,status,address,orderdate,totalprice
#         FROM orders
#         WHERE 
#             userid = %s 
#                 AND 
#             (status = %s OR status = %s)
#         ORDER BY orderdate DESC
#         """
#         sql_where = (userid,orderstatus[0],orderstatus[1])

#         cursor.execute(sql_history,sql_where)
#         row = cursor.fetchall()
#         data = [{"orderid":i["orderid"],"status":i["status"],"address":i["address"],
#                 "orderdate":ft.format_timestamp(str(i["orderdate"])),"totalprice":float(i["totalprice"])} 
#                 for i in row]
        
#         # get order detail
#         lst_orderid = [i["orderid"] for i in row]
#         all_order_detail = []

#         for i in lst_orderid:
#             sql_order_detail = """
#             SELECT 
#                 drinkname, itemquantity,namesize,nametopping
#             FROM 
#                 itemorder as io
#             INNER JOIN 
#                 items as i
#             ON
#                 io.itemid = i.itemid
#             INNER JOIN 
#                 drinks as d
#             ON
#                 d.drinkid = i.drinkid
#             INNER JOIN
#                 sizes as s
#             ON 
#                 s.sizeid = i.sizeid
#             LEFT JOIN
#                 itemtopping as it
#             ON
#                 it.itemid = i.itemid
#             LEFT JOIN 
#                 toppings as t
#             ON
#                 t.toppingid = it.toppingid
#             WHERE orderid = %s
#             """
#             sql_where = (i,)
#             cursor.execute(sql_order_detail,sql_where)
#             orderdetail = cursor.fetchall()
#             all_order_detail.append(orderdetail)

#         # format all_order_detail
#         all_order_detail_format = []
#         for i in range(len(all_order_detail)):
#             result = ", ".join([f"{sublist[0]} (x{sublist[1]})" for sublist in all_order_detail[i]]) + ", size " + ", ".join(set([sublist[2] for sublist in all_order_detail[i]]))
#             topping = [sublist[3] for sublist in all_order_detail[i] if sublist[3] is not None]
#             if topping:
#                 result += ", topping: " + ", ".join([sublist[3] for sublist in all_order_detail[i] if sublist[3] is not None])
#             all_order_detail_format.append(result)
#         # add order detail
#         for i in range(len(data)):
#             data[i].update({"orderdetail":all_order_detail_format[i]})

#         cursor.close()
#         resp = jsonify(data=data)
#         resp.status_code = 200
#         return resp

#     except:
#         resp = jsonify({"message":"Internal Server Error!!"})
#         resp.status_code = 500
#         return resp

# @childs.route("/v1/childs/web-histories", methods=['POST'])
# @jwt_required()
# def sendWebHistory():
#     userID = get_jwt_identity()
