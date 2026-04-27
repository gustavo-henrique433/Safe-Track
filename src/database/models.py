from app.config.extensions import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    __tablename__='users'
    id = db.Column(db.Integer, primary_key=True)
    nome =  db.Column(db.String(100), nullable=False)
    email  = db.Column(db.String(100), unique=True ,nullable=False)
    senha =  db.Column(db.String(50), nullable=False)
    tipo_user = db.Column(db.String(20), nullable = False)

    __mapper_args__ = {
        'polymorphic_identity': 'users',
        'polymorphic_on': 'tipo_user'
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
    uid = db.Column(db.String, primary_key = True)
    date = db.Column(db.String(50), nullable=False)
    ##date = db.Column(db.DateTime, nullable=False)


class Object(db.Model):
    __tablename__ = 'object'
    id = db.Column(db.Integer, primary_key = True)
    id_rfid = db.Column(db.String, db.ForeignKey('rfid.uid'), unique = True ,nullable = False)
    id_lugar = db.Column(db.Integer, db.ForeignKey('local.id'))
    nome = db.Column(db.String, nullable  = False)
    descricao = db.Column(db.Text, nullable = False)
    especificacoes = db.Column(db.Text, nullable = False)
    url_imagem = db.Column(db.String(255))

class Local(db.Model): 
    __tablename__ = 'local'
    id = db.Column(db.Integer, primary_key= True)
    endereco = db.Column(db.String(250), nullable = False)    
    descricao = db.Column(db.Text, nullable = False)
    responsavel = db.Column(db.String(150), nullable = False)











