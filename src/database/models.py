from app.config.extensions import db
from flask_login import UserMixin
from datetime import datetime, timezone


class User(db.Model, UserMixin):
    __tablename__='users'
    id = db.Column(db.Integer, primary_key=True)
    nome =  db.Column(db.String(100), nullable=False)
    email  = db.Column(db.String(100), unique=True ,nullable=False)
    senha =  db.Column(db.String(50), nullable=False)
    tipo_user = db.Column(db.String(20), nullable = False)
    credencial_rfid = db.Column(db.Integer, db.ForeignKey('rfid.uid'),unique = True, nullable = True) ##Adicionei esse novo campo
    status_conta = db.Column(db.Boolean, default =True, nullable = False) ##Status da conta de usuario
    permissoes = db.relationship('PermissaoAcesso', back_populates='pessoa', lazy='select')

    __mapper_args__ = {
        'polymorphic_identity': 'users',
        'polymorphic_on': 'tipo_user'
    }

    def pode_acessar(self, local_id, agora=None):
        agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
        return self.status_conta and any(
            permissao.local_id == local_id and permissao.vigente(agora)
            for permissao in self.permissoes)

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


visitante_locais = db.Table(
    'visitante_locais',
    db.Column('visitante_id', db.Integer, db.ForeignKey('visitantes.id'), primary_key=True),
    db.Column('local_id', db.Integer, db.ForeignKey('local.id'), primary_key=True),
)


class Visitante(User):
    __tablename__ = 'visitantes'
    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    inicio = db.Column(db.DateTime, nullable=False)
    expiracao = db.Column(db.DateTime, nullable=False)
    locais = db.relationship('Local', secondary='permissoes_acesso',
        primaryjoin='and_(Visitante.id == PermissaoAcesso.pessoa_id, PermissaoAcesso.revogada.is_(False))',
        secondaryjoin='Local.id == PermissaoAcesso.local_id', viewonly=True,
        lazy='selectin', order_by='Local.id')
    __table_args__ = (db.CheckConstraint('inicio < expiracao', name='ck_visitante_periodo'),)
    __mapper_args__ = {'polymorphic_identity': 'visitante'}

    def situacao(self, agora=None):
        if not self.status_conta:
            return 'revogado'
        agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
        if agora < self.inicio:
            return 'agendado'
        if agora >= self.expiracao:
            return 'expirado'
        return 'ativo'

    def pode_acessar(self, local_id, agora=None):
        agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
        return self.situacao(agora) == 'ativo' and super().pode_acessar(local_id, agora)


class PermissaoAcesso(db.Model):
    __tablename__ = 'permissoes_acesso'
    pessoa_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    local_id = db.Column(db.Integer, db.ForeignKey('local.id'), primary_key=True)
    inicio = db.Column(db.DateTime, nullable=True)
    expiracao = db.Column(db.DateTime, nullable=True)
    revogada = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    pessoa = db.relationship('User', back_populates='permissoes')
    local = db.relationship('Local')
    __table_args__ = (
        db.CheckConstraint('inicio IS NULL OR expiracao IS NULL OR inicio < expiracao', name='ck_permissao_periodo'),
        db.CheckConstraint('revogada IN (0, 1)', name='ck_permissao_revogada'),
    )

    def situacao(self, agora=None):
        if self.revogada:
            return 'revogada'
        agora = agora or datetime.now(timezone.utc).replace(tzinfo=None)
        if self.inicio is not None and agora < self.inicio:
            return 'agendada'
        if self.expiracao is not None and agora >= self.expiracao:
            return 'expirada'
        return 'vigente'

    def vigente(self, agora=None):
        return self.situacao(agora) == 'vigente'


class VisitanteAcesso(db.Model):
    __tablename__ = 'visitante_acessos'
    registro_id = db.Column(db.Integer, db.ForeignKey('registro_acesso.id'), primary_key=True)
    visitante_id = db.Column(db.Integer, db.ForeignKey('visitantes.id'), nullable=False, index=True)
    














