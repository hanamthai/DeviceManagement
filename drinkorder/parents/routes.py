from flask import jsonify, request, session, url_for, Blueprint
import bcrypt
from flask_mail import Message

from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import get_jwt
from flask_jwt_extended import create_access_token
from flask_jwt_extended import create_refresh_token
from flask_jwt_extended import jwt_required

from drinkorder import mail
from drinkorder import conn
from drinkorder import psycopg2
from drinkorder import timedelta
from drinkorder import constants
from drinkorder import response_errors

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

    childIDs = []
    for row in rows:
        childIDs.append(row[0])
    
    sql = "SELECT * FROM users WHERE id = ANY(%s)"
    sql_where = (childIDs,)
    cursor.execute(sql,sql_where)
    rows = cursor.fetchall()
    cursor.close()
    data = [{"id": row["id"], "fullName": row["full_name"], "email": row["email"], 
             "password": row["password"], "status": row["status"]}for row in rows]
    resp = jsonify(data=data)
    resp.status_code = 200
    return resp
    

@parents.route("/v1/parents/web-history/<int:childID>/<int:days>", methods=['GET'])
@jwt_required()
def getWebHistory(childID, days):
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
    # get timestamp now and compare with create_at of table web_histories
    return "skip"

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


# # send email to reset password
# def sendEmail(userid,_email):
#     token = create_access_token(identity=userid,expires_delta=timedelta(minutes=5))
#     html_content = f""" 
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <link rel="stylesheet" type="text/css" hs-webfonts="true" href="https://fonts.googleapis.com/css?family=Lato|Lato:i,b,bi">
#         <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <style type="text/css">
#           h1{{font-size:56px}}
#           p{{font-weight:100}}
#           td{{vertical-align:top}}
#           #email{{margin:auto;width:600px;background-color:#fff}}
#         </style>
#     </head>
#     <body bgcolor="#F5F8FA" style="width: 100%; font-family: "Helvetica Neue", Helvetica, sans-serif; font-size:18px;">
#     <div id="email">
#         <table role="presentation" width="100%">
#             <tr>
#                 <td bgcolor="#F6AC31" align="center" style="color: white;">
#                     <h1> Ứng Dụng<br> Đặt Đồ Uống!</h1>
#                 </td>
#         </table>
#         <table role="presentation" border="0" cellpadding="0" cellspacing="10px" style="padding: 30px 30px 30px 60px;">
#             <tr>
#                 <td>
#                     <h2>
#                         Để đặt lại mật khẩu trong ứng dụng đặt đồ uống online. Hãy nhấn vào link dưới đây:
#                         <a href={url_for("parents.verifyTokenEmail",jwt=token,_external=True)}>
#                             <br>Bấm vào đây!
#                         </a>
#                     </h2>
#                     <p>
#                         Nếu bạn không phải là người gửi yêu cầu đổi mật khẩu. Hãy bỏ qua mail thông báo này.
#                     </p>
#                 </td>
#             </tr>
#         </table>
#     </div>
#     </body>
#     </html>
#     """
#     msg = Message('YÊU CẦU ĐẶT LẠI MẬT KHẨU', sender='noreply@gmail.com', recipients=[_email], html=html_content)
#     mail.send(msg)

# #{{HOST}}/resetPassword?email=<Your email>
# @parents.route('/resetPassword',methods = ['POST'])
# def resetPassword():
#     _email = request.args.get('email')
    
#     # check email request has contained in the database
#     cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#     sql_check_email = """
#     SELECT userid FROM users
#     WHERE email = %s
#     """
#     sql_where = (_email,)
#     cursor.execute(sql_check_email,sql_where)
#     row = cursor.fetchone()
#     cursor.close()
    
#     if row:
#         userid = row['userid']
#         sendEmail(userid,_email)
#         resp = jsonify({"message":"Hệ thống đã gửi cho bạn mail thông báo thay đổi mật khẩu. Hãy vào mail để kiểm tra!"})
#         resp.status_code = 200
#         return resp
#     else:
#         resp = jsonify({"message":"Not Found - Email doesn't exists in system!"})
#         resp.status_code = 404
#         return resp



# #{{HOST}}/resetPassword/token?jwt=<Your token>
# @parents.route('/resetPassword/token',methods=['PUT','GET'])
# @jwt_required(locations="query_string")
# def verifyTokenEmail():
#     userid = get_jwt_identity()
#     if userid:
#         # hash password '123'
#         _password = '123'
#         hashed = bcrypt.hashpw(_password.encode('utf-8'), bcrypt.gensalt())
#         _password_hash = hashed.decode('utf-8')

#         # update password into database
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         sql_change_password_default = """
#         UPDATE users
#         SET password = %s
#         WHERE userid = %s
#         """
#         sql_where = (_password_hash,userid)
#         cursor.execute(sql_change_password_default,sql_where)
#         conn.commit()
#         cursor.close()

#         resp = jsonify({"message":"Your password changed to '123'!!!"})
#         resp.status_code = 200
#         return resp
#     else:
#         resp = jsonify({"message":"Not Found - Account doesn't exists"})
#         resp.status_code = 404
#         return resp
