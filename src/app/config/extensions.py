from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_mqtt import Mqtt
##from celery import Celery


db = SQLAlchemy()
mqtt = Mqtt()

##celery = Celery()
    