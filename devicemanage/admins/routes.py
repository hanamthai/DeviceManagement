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
            users.id,users.full_name,users.email,users.password,users.role_id,users.status
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
            fullname = row['full_name']
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
                resp = jsonify(access_token=access_token,full_name=fullname,role_id=roleID)
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
    if row == None:
        return response_errors.UserNotExists()
    switchStatus = constants.SwitchStatus[row['status']]
    # Change status
    sql = "UPDATE users SET status = %s WHERE id = %s"
    sql_where = (switchStatus, userID)
    cursor.execute(sql, sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@admins.route('/v1/admins/change-info/<int:userID>',methods=['POST'])
@jwt_required()
def changePassword(userID):
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameAdmin:
        return response_errors.NotAuthenticateAdmin()
    
    # validate user
    cursor = conn.cursor(cursor_factory= psycopg2.extras.DictCursor)
    sql_check_user_exists = "SELECT * FROM users WHERE id = %s"
    sql_where = (userID,)
    cursor.execute(sql_check_user_exists, sql_where)
    row = cursor.fetchone()
    if row == None:
        return response_errors.UserNotExists()

    _json = request.json
    _fullName = _json['fullName']
    _password = _json['password']
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # handle have param password and without password
    if _password == "":
        # without password
        sql = """
            UPDATE users
            SET full_name = %s
            WHERE id = %s
        """
        sql_where = (_fullName,userID)
        cursor.execute(sql,sql_where)
        conn.commit()
        cursor.close()
        return response_errors.Success()   
    # with password
    # hash password
    hashed = bcrypt.hashpw(_password.encode('utf-8'),bcrypt.gensalt())
    _newPassword = hashed.decode('utf-8')
    sql = """
        UPDATE users
        SET full_name = %s, password = %s
        WHERE id = %s
    """
    sql_where = (_fullName, _newPassword, userID)
    cursor.execute(sql,sql_where)
    conn.commit()
    cursor.close()
    return response_errors.Success()

@admins.route('/v1/admins/change-password',methods=['PUT'])
@jwt_required()
def changePasswordAdmin():
    userID = get_jwt_identity()
    header = get_jwt()
    roleName = header['role_name']

    if roleName != constants.RoleNameAdmin:
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