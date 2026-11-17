from app.config.extensions import db
from flask_login import UserMixin
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__='users'
    id = db.Column(db.Integer, primary_key=True)
    nome =  db.Column(db.String(100), nullable=False)
    email  = db.Column(db.String(100), unique=True ,nullable=False)
    senha =  db.Column(db.String(50), nullable=False)
    tipo_user = db.Column(db.String(20), nullable = False)
    credencial_rfid = db.Column(db.Integer, db.ForeignKey('rfid.uid'),unique = True, nullable = True) ##Adicionei esse novo campo
    status_conta = db.Column(db.Boolean, default =True, nullable = False) ##Status da conta de usuario

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
    local_relacionado = db.relationship('Local', backref='objetos')
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

class Registro_Acesso(db.Model):
    __tablename__ = 'registro_acesso'
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    id_rfid = db.Column(db.String, db.ForeignKey('rfid.uid'), nullable = True)
    id_local = db.Column(db.Integer, db.ForeignKey('local.id'), nullable = False)
    horario = db.Column(db.DateTime, default=datetime.utcnow, nullable = False)
    status_tentativa = db.Column(db.String(20))

class Historico_patrimonio(db.Model):
    __tablename__ = 'historico_patrimonio'
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    id_objeto =  db.Column(db.Integer, db.ForeignKey('object.id'), nullable = True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('users.id'), nullable = True)
    acao = db.Column(db.String, nullable = False)
    horario = db.Column(db.DateTime, default=datetime.utcnow, nullable = False)
    status_tentativa = db.Column(db.String(20))

class Esp32_registro(db.Model):
    __tablename__ = 'esp32_registro'
    mac = db.Column(db.String, primary_key = True)
    local = db.Column(db.Integer, db.ForeignKey('local.id'), nullable = True)
    














