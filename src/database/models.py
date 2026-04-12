from app.config.extensions import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    __tablename__='users'
    id = db.Column(db.Integer, primary_key=True)
    nome =  db.Column(db.String(100), nullable=False)
    email  = db.Column(db.String(100), unique=True ,nullable=False)
    senha =  db.Column(db.String(50), nullable=False)
    type_user = db.Column(db.String(20), nullable = False)

    __mapper_args__ = {
        'polymorphic_identity': 'users',
        'polymorphic_on': 'type_user'
    }

class Root(User):
    __tablename__= 'roots'
    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    senha_root = db.Column(db.String(100), nullable =False)
    nivel_permissao = db.Column(db.String(50), nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'roots',
    }

class RFID(db.Model):
    __tablename__ = 'rfid'
    id = db.Column(db.Integer, primary_key = True)
    uid = db.Column(db.String, unique=True, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    ##date = db.Column(db.DateTime, nullable=False)





