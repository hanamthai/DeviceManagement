from flask import jsonify, request, session, Blueprint
import bcrypt
from devicemanage import conn
from devicemanage import psycopg2

from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt
from devicemanage import format_timestamp as ft
from devicemanage import constants
from devicemanage import response_errors

# create an instance of this Blueprint
admins = Blueprint('admins','__name__')


# management

# Create a route to authenticate your admins and return token.
@admins.route('/v1/logins', methods=['POST'])
def login():
    _json = request.json
    # validate the received values
    if 'email' in _json.keys() and 'password' in _json.keys():
        _email = _json['email']
        _password = _json['password']
        # check login exists
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        sql = """
        SELECT 
            users.id,users.email,users.password,users.role_id,users.status
        FROM 
            users 
        WHERE 
            email = %s 
        """
        sql_where = (_email,)
        cursor.execute(sql, sql_where)
        row = cursor.fetchone()
        cursor.close()
        if row:
            password_hash = row['password']
            id = row['id']
            roleID = row['role_id']
            status = row['status']
            if status == constants.StatusInactive:
                resp = jsonify({"message":"Locked - Your account is locked! You can contact with our employee to know reason!"})
                resp.status_code = 423
                return resp
            elif bcrypt.checkpw(_password.encode('utf-8'), password_hash.encode('utf-8')):
                # create token
                roleName = getRoleName(roleID)
                if roleName == None:
                    resp = jsonify({"message":"Your Role not exists in system!!"})
                    resp.status_code = 400
                    return resp
                additional_claims = {"role_id": roleID, "role_name": roleName}
                access_token = create_access_token(identity=id,additional_claims=additional_claims)
                session['access_token'] = access_token
                resp = jsonify(access_token=access_token)
                resp.status_code = 200
                return resp
            else:
                resp = jsonify({'message': 'Bad Request - Wrong password!'})
                resp.status_code = 400
                return resp
        else:
            resp = jsonify({'message': 'Bad Request - Your account does not exist in the system!'})
            resp.status_code = 400
            return resp
    else:
        resp = jsonify({'message': 'Bad Request - Missing input!'})
        resp.status_code = 400
        return resp

def getRoleName(role_id):
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT * FROM roles WHERE id = %s"
    sql_where = (role_id,)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    cursor.close()
    if row == None:
        return None
    else:
        return row["role_name"]

@admins.route('/v1/user-profile', methods=['GET'])
@jwt_required()
def getUserInfo():
    userID = get_jwt_identity()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = "SELECT * FROM users WHERE id = %s"
    sql_where = (userID,)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    if row == None:
        resp = jsonify({'message':'User not found!!'})
        resp.status_code = 400
        return resp
    data = {'id':row['id'],'email':row['email'],'fullName':row['full_name'],'roleID':row['role_id'],'status':row['status']}
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

@admins.route("/v1/admins/create-role", methods=['POST'])
@jwt_required()
def createRole():
    _json = request.json
    _roleName = _json['roleName']

    # check role name has already exists
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = 'SELECT * FROM roles WHERE role_name = %s'
    sql_where = (_roleName,)
    cursor.execute(sql, sql_where)
    row = cursor.fetchone()
    if row != None:
        cursor.close()
        resp = jsonify({'message': 'Bad Request - Role Name already exists!'})
        resp.status_code = 400
        return resp
    else:
        sql = 'INSERT INTO roles(role_name) VALUES(%s)'
        sql_where = (_roleName,)
        cursor.execute(sql, sql_where)
        conn.commit()
        cursor.close()
        return response_errors.Success()

@admins.route("/v1/admins", methods=['GET'])
@jwt_required()
def getInfo():
    data = get_jwt()
    roleName = data['role_name']

    if roleName != 'admin':
        return response_errors.NotAuthenticateAdmin()
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = """
        SELECT * FROM users WHERE role_id = %s 
        """
    sql_where = (constants.RoleIDParent,)
    cursor.execute(sql, sql_where)
    rows = cursor.fetchall()
    cursor.close()
    data = [{"id": row["id"], "fullName": row["full_name"], "email": row["email"], 
             "password": row["password"], "status": row["status"]}for row in rows]
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp

@admins.route("/v1/admins/block/<int:userID>", methods=['POST'])
@jwt_required()
def blockUser(userID):
    data = get_jwt()
    roleName = data['role_name']

    if roleName != constants.RoleNameAdmin:
        return response_errors.NotAuthenticateAdmin()
    
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Get status to switch 
    sql = "SELECT status FROM users WHERE id = %s"
    sql_where = (userID,)
    cursor.execute(sql,sql_where)
    row = cursor.fetchone()
    switchStatus = constants.SwitchStatus[row['status']]
    # Change status
    sql = "UPDATE users SET status = %s WHERE id = %s"
    sql_where = (switchStatus, userID)
    cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@admins.route('/v1/admins/change-password/<int:userID>',methods=['PUT'])
@jwt_required()
def changePassword(userID):
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameAdmin:
        return response_errors.NotAuthenticateAdmin
    
    # validate user
    cursor = conn.cursor(cursor_factory= psycopg2.extras.DictCursor)
    sql_check_user_exists = "SELECT * FROM users WHERE id = %s"
    sql_where = (userID,)
    cursor.execute(sql_check_user_exists, sql_where)
    row = cursor.fetchone()
    if row == None:
        resp = jsonify({'message': "This account doesn't exists in system!!"})
        resp.status_code = 400
        return resp

    _json = request.json
    _oldPassword = _json['oldPassword']
    _newPassword = _json['newPassword']
    # Confirm old password
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

# ## admin updates order status to 'Delivering'
# @admins.route('/admin/order/update/<int:orderid>',methods=['PUT'])
# @jwt_required()
# def orderStatusUpdate(orderid):
#     info = get_jwt()
#     rolename = info['rolename']
    
#     if rolename == 'admin':
#         # check order status is 'Preparing'or not.
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         sql_check_preparing = """
#         SELECT orderid FROM orders
#         WHERE orderid = %s AND status = %s
#         """
#         sql_where = (orderid,'Preparing')
#         cursor.execute(sql_check_preparing,sql_where)
#         row = cursor.fetchone()
#         if row:
#             sql = """
#             UPDATE orders
#             SET status = 'Delivering'
#             WHERE orderid = %s
#             """
#             sql_where = (orderid,)
#             cursor.execute(sql,sql_where)
#             conn.commit()
#             cursor.close()
#             resp = jsonify({"message":"Updated order status to 'Delivering'!"})
#             resp.status_code = 200
#             return resp
#         else:
#             cursor.close()
#             resp = jsonify({"message":"You're cannot change the order status to 'Delivering'!"})
#             resp.status_code = 400
#             return resp
#     else:
#         resp = jsonify({"message":"Unauthorized - You are not authorized!"})
#         resp.status_code = 401
#         return resp

# ## get customer info
# @admins.route('/admin/customer/info',methods=['GET'])
# @jwt_required()
# def getCustomerInfo():
#     data = get_jwt()
#     rolename = data['rolename']

#     if rolename == 'admin':
#         sql = """
#         SELECT userid,phonenumber,fullname,address,email,status FROM users
#         WHERE rolename = 'user'
#         ORDER BY userid
#         """
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         cursor.execute(sql)
#         info = cursor.fetchall()
#         customerInfo = [{'userid':i['userid'],'phonenumber':i['phonenumber'],
#                          'fullname':i['fullname'],'address':i['address'],'email':i['email'],
#                          'status':i['status']} for i in info]
#         cursor.close()
#         resp = jsonify(data=customerInfo)
#         resp.status_code = 200
#         return resp
#     else:
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp


# ## Lock and unlock customer accounts
# @admins.route('/admin/customer/status/<int:userid>', methods = ['PUT'])
# @jwt_required()
# def changeCustomerStatus(userid):
#     data = get_jwt()
#     rolename = data['rolename']

#     if rolename == 'admin':
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         # if the user status is active then i will change it to inactive and ngược lại
#         sql_check_status = """
#         SELECT status FROM users
#         WHERE userid = %s
#         """
#         sql_where = (userid,)
#         cursor.execute(sql_check_status,sql_where)
#         userStatus = cursor.fetchone()[0]

#         _status = ''
#         if userStatus == 'active':
#             _status = 'inactive'
#         elif userStatus == 'inactive':
#             _status = 'active'

#         # change user status
#         sql_change_status = """
#         UPDATE users
#         SET status = %s
#         WHERE userid = %s
#         """
#         sql_where = (_status,userid)
#         cursor.execute(sql_change_status,sql_where)
#         conn.commit()
#         cursor.close()
#         resp = jsonify({'message':'Changed customer account status!!'})
#         resp.status_code = 200
#         return resp

#     else:
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp


# ## Admin: CURD drink (get all drink and drink detail already available APIs)

# ## Create drinks
# @admins.route('/admin/drink/create', methods = ['POST'])
# @jwt_required()
# def createDrink():
#     data = get_jwt()
#     rolename = data['rolename']
    
#     if rolename == 'admin':
#         _json = request.json
#         _drinkname = _json['drinkname']
#         _drinkimage = _json['drinkimage']
#         _description = _json['description']
#         _categoryid = _json['categoryid']
#         _sizeArr = _json['size']
#         _toppingArr = _json['topping']

#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         # add info drink
#         sql_create_drink = """
#         INSERT INTO 
#             drinks(drinkname,drinkimage,description,categoryid,status)
#         VALUES
#             (%s,%s,%s,%s,%s)
#         RETURNING
#             drinkid
#         """
#         sql_where = (_drinkname,_drinkimage,_description,_categoryid,'Available')
        
#         cursor.execute(sql_create_drink,sql_where)
#         row = cursor.fetchone()
#         drinkid = row[0]

#         # add info size
#         if _sizeArr != []:
#             for i in _sizeArr:
#                 sql_add_size = """
#                 INSERT INTO sizes(namesize,price,drinkid) VALUES(%s,%s,%s)
#                 """
#                 sql_where = (i['namesize'],i['price'],drinkid)
#                 cursor.execute(sql_add_size,sql_where)
#         else:
#             resp = jsonify({'message':"Missing input - You have to add size of drink!!"})
#             resp.status_code = 400
#             return resp

#         # add info topping(if any)
#         if _toppingArr != []:
#             # add info topping to toppings table
#             lst_toppingid = []
#             for i in _toppingArr:
#                 sql_add_topping = """
#                 INSERT INTO toppings(nametopping,price) VALUES(%s,%s)
#                 RETURNING toppingid
#                 """
#                 sql_where = (i['nametopping'],i['price'])
#                 cursor.execute(sql_add_topping,sql_where)
#                 toppingid = cursor.fetchone()
#                 lst_toppingid.append(toppingid[0])
            
#             # add toppingid to drinktopping table
#             for i in lst_toppingid:
#                 sql_drinktopping = """
#                 INSERT INTO drinktopping(drinkid,toppingid) VALUES(%s,%s)
#                 """
#                 sql_where = (drinkid,i)
#                 cursor.execute(sql_drinktopping,sql_where)
        
#         # commit it to DB
#         conn.commit()
#         cursor.close()
#         resp = jsonify({'message':"Add drink success!!"})
#         resp.status_code = 200
#         return resp
    
#     else:
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp

# ## Update and detete drink
# @admins.route('/admin/drink/<int:drinkid>', methods = ['PUT', 'DELETE'])
# @jwt_required()
# def admimGetAllDrink(drinkid):
#     data = get_jwt()
#     rolename = data['rolename']

#     if rolename == 'admin':
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         if request.method == 'PUT':
#             _json = request.json
#             _drinkid = _json['drinkid']
#             _drinkname = _json['drinkname']
#             _drinkimage = _json['drinkimage']
#             _description = _json['description']
#             _categoryid = _json['categoryid']
#             _sizeArr = _json['size']
#             _toppingArr = _json['topping']
            
#             # change drink info
#             sql_change_drink = """
#             UPDATE
#                 drinks
#             SET
#                 drinkname = %s,drinkimage = %s, description = %s, categoryid = %s
#             WHERE drinkid = %s
#             """
#             sql_where = (_drinkname,_drinkimage,_description,_categoryid,_drinkid)
#             cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#             cursor.execute(sql_change_drink,sql_where)
            
#             # change size of drink
#             if _sizeArr != []:
#                 # If the request body has sizeid means that it already exists in the system
#                 # otherwise it doesn't exists and we have to create it in DB
#                 for i in _sizeArr:
#                     # there are sizeid (we just change it)
#                     if 'sizeid' in i:
#                         _sizeid = i['sizeid']
#                         _namesize = i['namesize']
#                         _price = i['price']

#                         sql_change_size = """
#                         UPDATE
#                             sizes
#                         SET
#                             namesize = %s, price = %s
#                         WHERE
#                             sizeid = %s
#                         """
#                         sql_where = (_namesize,_price,_sizeid)
#                         cursor.execute(sql_change_size,sql_where)
#                     # there are no sizeid (we have to create it)
#                     else:
#                         _namesize = i['namesize']
#                         _price = i['price']

#                         sql_create_size = """
#                         INSERT INTO
#                             sizes(namesize,price,drinkid)
#                         VALUES(%s,%s,%s)
#                         """
#                         sql_where = (_namesize,_price,_drinkid)
#                         cursor.execute(sql_create_size,sql_where)
#             else:
#                 resp = jsonify({'message':"Missing input - You have to add size of drink!!"})
#                 resp.status_code = 400
#                 return resp
            
#             # change topping of drink (if any)
#             if _toppingArr != []:
#                 # If the request body has toppingid means that it already exists in the system
#                 # otherwise it doesn't exists and we have to create it in DB
#                 for i in _toppingArr:
#                     # there are topping (we just change it)
#                     if "toppingid" in i:
#                         _toppingid = i['toppingid']
#                         _nametopping = i['nametopping']
#                         _price = i['price']

#                         sql_change_topping = """
#                         UPDATE
#                             toppings
#                         SET
#                             nametopping = %s, price = %s
#                         WHERE
#                             toppingid = %s
#                         """
#                         sql_where = (_nametopping,_price,_toppingid)
#                         cursor.execute(sql_change_topping,sql_where)
#                     # there are no toppingid (we have to create it)
#                     else:
#                         _nametopping = i['nametopping']
#                         _price = i['price']
#                         # we have create topping in toppings table
#                         # get toppingid and save it in drinktopping table
#                         sql_create_topping = """
#                         INSERT INTO
#                             toppings(nametopping,price)
#                         VALUES(%s,%s)
#                         RETURNING toppingid
#                         """
#                         sql_where = (_nametopping,_price)
#                         cursor.execute(sql_create_topping,sql_where)
#                         row = cursor.fetchone()
#                         toppingid = row[0]
#                         # save toppingid to drinktopping table
#                         sql_add_drinktopping = """
#                         INSERT INTO
#                             drinktopping(drinkid,toppingid)
#                         VALUES(%s,%s)
#                         """
#                         sql_where = (_drinkid,toppingid)
#                         cursor.execute(sql_add_drinktopping,sql_where)

#             conn.commit()
#             cursor.close()
#             resp = jsonify({'message':"Update success!"})
#             resp.status_code = 200
#             return resp

#         elif request.method == 'DELETE':
#             sql_detete_drink = """
#             UPDATE drinks
#             SET status = 'Unvailable'
#             WHERE drinkid = %s
#             """
#             sql_where = (drinkid,)
#             cursor.execute(sql_detete_drink,sql_where)
#             conn.commit()
#             cursor.close()

#             resp = jsonify({'message':"Delete Successfully!!"})
#             resp.status_code = 200
#             return resp
#         else:
#             resp = jsonify({'message':"Not Implemented!!"})
#             resp.status_code = 501
#             return resp
#     else:
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp


# ## admin view order history or current 
# @admins.route('/admin/order/<status>', methods = ['GET'])
# @jwt_required()
# def adminOrderHistory(status):
#     data = get_jwt()
#     rolename = data['rolename']

#     if rolename != 'admin':
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp

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
        
#         # admin get order 'history' or 'current'
#         sql_history = """
#         SELECT 
#             orderid,status,address,orderdate,totalprice
#         FROM orders
#         WHERE 
#             (status = %s OR status = %s)
#         ORDER BY orderdate DESC
#         """
#         sql_where = (orderstatus[0],orderstatus[1])

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


# ## admin cancelled order
# @admins.route('/admin/order/cancel/<int:orderid>', methods = ['PUT'])
# @jwt_required()
# def adminCancelledOrder(orderid):
#     data = get_jwt()
#     rolename = data['rolename']

#     if rolename != 'admin':
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp
    
#     # check orderid already exists and it have a 'Preparing' status 
#     # then system allows for cancel order 
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
#     sql_check_constraint = """
#     SELECT orderid FROM orders
#     WHERE
#         orderid = %s
#         AND
#         status = %s
#     """

#     sql_where = (orderid,'Preparing')
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
#         resp = jsonify({"message":"Order status updated to 'Cancelled'!"})
#         resp.status_code = 200
#         return resp

#     else:
#         cursor.close()
#         resp = jsonify({"message":"Order cannot cancel"})
#         resp.status_code = 400
#         return resp

# ## revenue statistics by day or month or year
# @admins.route('/admin/revenue', methods=['GET'])
# @jwt_required()
# def getRevenue():
#     data = get_jwt()
#     rolename = data['rolename']

#     if rolename == 'admin':
#         date = request.args.get('date')
#         flag = request.args.get('flag')

#         revenue = 0
#         revenue_detail = []
#         row = [] # contain raw data when i execute sql

#         # format date 'dd-mm-yy' to 'yy-mm-dd'
#         date_format = date[6:10] + '-' + date[3:5] + '-' + date[0:2]
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

#         sql_revenue = """
#         SELECT 
#             orderid, totalprice, orderdate
#         FROM
#             orders
#         WHERE 
#             CAST(orderdate as TEXT) 
#                 LIKE 
#             CONCAT(%s,%s) 
#                 AND 
#             status = 'Completed'
#         ORDER BY orderdate ASC;
#         """

#         if flag == 'today':
#             # get total revenue
#             sql_where = (date_format,'%')
#             cursor.execute(sql_revenue,sql_where)
#             row = cursor.fetchall()
                
#         elif flag == 'month':
#             sql_where = (date_format[0:7],'%')
#             cursor.execute(sql_revenue,sql_where)
#             row = cursor.fetchall()

#         elif flag == 'year':
#             sql_where = (date_format[0:4],'%')
#             cursor.execute(sql_revenue,sql_where)
#             row = cursor.fetchall()
        
#         else:
#             cursor.close()
#             resp = jsonify({"message":"Invalid parameter passed!!"})
#             resp.status_code = 400
#             return resp
        
#         # total revenue and revenue detail
#         if row != None:
#             for i in row:
#                 revenue += int(i['totalprice'])
#             revenue_detail = [{'orderid':i['orderid'],'orderdate':ft.format_timestamp(str(i['orderdate'])),
#                                 'totalprice':i['totalprice']} for i in row]

#         cursor.close()
#         resp = jsonify(data = {'revenue':revenue,'revenueDetail':revenue_detail})
#         resp.status_code = 200
#         return resp
#     else:
#         resp = jsonify({'message':"Unauthorized - You are not authorized!!"})
#         resp.status_code = 401
#         return resp
