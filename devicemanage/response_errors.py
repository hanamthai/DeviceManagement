from flask import jsonify

def NotAuthenticateAdmin():
    resp = jsonify({'message':"Unauthorized - You are not authorized - Only admin allowed!!"})
    resp.status_code = 401
    return resp

def NotAuthenticateParent():
    resp = jsonify({'message':"Unauthorized - You are not authorized - Only parent allowed!!"})
    resp.status_code = 401
    return resp

def NotAuthenticateChild():
    resp = jsonify({'message':"Unauthorized - You are not authorized - Only child allowed!!"})
    resp.status_code = 401
    return resp

def Success():
    resp = jsonify({'message': "Success!!"})
    resp.status_code = 200
    return resp

def EmailExists():
    resp = jsonify({'message': 'Bad Request - Your email already exists!'})
    resp.status_code = 400
    return resp

def NotData():
    resp = jsonify(data=[])
    resp.status_code = 200
    return resp