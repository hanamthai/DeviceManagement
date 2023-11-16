from flask import Flask
from flask_cors import CORS  # pip install -U flask-cors

import psycopg2  # pip install psycopg2
import psycopg2.extras

from flask_jwt_extended import JWTManager

from datetime import timedelta

from flask_mail import Mail

import os
from dotenv import load_dotenv

app = Flask(__name__)

# load environment variables from .env
load_dotenv()

# Setup the Flask-JWT-Extended extension
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
app.config['JWT_TOKEN_LOCATION'] = 'headers'
jwt = JWTManager(app)

# configure the app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10080) # 7 days
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=10080)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=1)
# send email setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

CORS(app)   # Cross-origin resource sharing

# Local
# DB_HOST = "localhost"
# DB_NAME = "Device Manage"
# DB_USER = "postgres"
# DB_PASS = "123"


# Public
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                        password=DB_PASS, host=DB_HOST)

# Avoid circular import
from devicemanage.childs.routes import childs
from devicemanage.admins.routes import admins
from devicemanage.parents.routes import parents

app.register_blueprint(childs)
app.register_blueprint(admins)
app.register_blueprint(parents)