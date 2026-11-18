from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.config.extensions import db
from src.database.models import User, Root, RFID, Registro_Acesso, Local, Visitante, VisitanteAcesso, PermissaoAcesso
from datetime import datetime, timezone
from functools import wraps
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

control_door_bp  = Blueprint('control_door', __name__)
BLOCKLIST = set()

@control_door_bp.route('/acessar_porta', methods = ['POST'])
def abrir_porta():
    
    data = request.get_json()

    if not data:
        return jsonify({'message': 'Formato de dado invalido !!'}), 400

    uid_solicitante = data.get('uid_solicitante')    
    id_local = data.get('local')

    try:
        local_encontrado = Local.query.filter_by(id=id_local).first()
        if not local_encontrado:
            return jsonify({'message': 'Equipamento de acesso nao reconhecido.'}), 404
        valid_uid = isinstance(uid_solicitante, (str, int)) and not isinstance(uid_solicitante, bool) and bool(str(uid_solicitante).strip())
        pessoa = User.query.filter_by(credencial_rfid=uid_solicitante).first() if valid_uid else None
        tag = RFID.query.filter_by(uid=uid_solicitante).first() if valid_uid else None
        visitante = pessoa if isinstance(pessoa, Visitante) else None
        credencial_acesso = pessoa if tag is not None and pessoa is not None and pessoa.pode_acessar(local_encontrado.id) else None

        if not credencial_acesso:
            registro_falha = Registro_Acesso(
                id_rfid=uid_solicitante,
                id_local=local_encontrado.id,
                status_tentativa="Negado"
            )
            db.session.add(registro_falha)
            if visitante is not None:
                db.session.flush()
                db.session.add(VisitanteAcesso(registro_id=registro_falha.id, visitante_id=visitante.id))
            db.session.commit()
            
            return jsonify({'message': 'Acesso negado', 'abrir': False}), 403

        registro_sucesso = Registro_Acesso(
            id_rfid=uid_solicitante,
            id_local=local_encontrado.id,
            status_tentativa="Liberado"
        )
        db.session.add(registro_sucesso)
        if visitante is not None:
            db.session.flush()
            db.session.add(VisitanteAcesso(registro_id=registro_sucesso.id, visitante_id=visitante.id))
        db.session.commit()
        
        return jsonify({
            'message': f'Abrindo porta para {credencial_acesso.nome}',
            'abrir': True
        }), 200    

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro interno no servidor ao registrar acesso.'}), 500


def permission_admin(function):
    """Verificação Root existente, aplicada somente às operações novas."""
    @wraps(function)
    @jwt_required()
    def protected(*args, **kwargs):
        try:
            if not isinstance(db.session.get(User, get_jwt_identity()), Root):
                return jsonify(message='Acesso negado: somente Root administra permissões.'), 403
            return function(*args, **kwargs)
        except HTTPException as error:
            db.session.rollback()
            return jsonify(message=error.description), error.code
        except IntegrityError:
            db.session.rollback()
            return jsonify(message='Há conflito na permissão; nenhum dado foi gravado.'), 409
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(message='Não foi possível processar as permissões de acesso.'), 500
    return protected


def permission_person(person_id):
    person = db.session.get(User, person_id)
    if person is None:
        raise NotFound('Pessoa não encontrada.')
    return person


def permission_local(local_id):
    place = db.session.get(Local, local_id)
    if place is None:
        raise NotFound('Local não encontrado.')
    return place


def permission_date(value, name):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise BadRequest(f'{name}: informe data e horário ISO 8601 com fuso, ou null.')
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            raise ValueError('Fuso ausente')
        return instant.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        raise BadRequest(f'{name}: data inválida ou sem fuso.') from None


def permission_iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z') if value is not None else None


def registered_credential():
    # Compara as colunas herdadas sem converter/regravar UIDs ou perder zeros.
    return db.session.query(RFID.uid).filter(RFID.uid == User.credencial_rfid).exists()


def serialize_person(person, now):
    registered = person.credencial_rfid is not None and db.session.query(User.id).filter(
        User.id == person.id, registered_credential()).first() is not None
    if not person.status_conta:
        status = 'revogado' if isinstance(person, Visitante) else 'inativo'
    elif not registered:
        status = 'sem_credencial'
    else:
        status = person.situacao(now) if isinstance(person, Visitante) else 'ativo'
    return {'id': person.id, 'nome': person.nome, 'tipo_user': person.tipo_user,
            'credencial_rfid': person.credencial_rfid, 'status_credencial': status,
            'inicio_credencial': permission_iso(person.inicio) if isinstance(person, Visitante) else None,
            'expiracao_credencial': permission_iso(person.expiracao) if isinstance(person, Visitante) else None}


def serialize_permission(permission, now):
    person = serialize_person(permission.pessoa, now)
    return {'pessoa': person, 'local': {'id': permission.local_id, 'endereco': permission.local.endereco},
            'inicio': permission_iso(permission.inicio), 'expiracao': permission_iso(permission.expiracao),
            'revogada': permission.revogada, 'situacao': permission.situacao(now),
            'acesso_efetivo': person['status_credencial'] == 'ativo' and permission.vigente(now)}


def permission_pagination(allowed):
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise BadRequest('Há filtros desconhecidos ou repetidos.')
    try:
        page = int(request.args.get('pagina', '1'))
        size = int(request.args.get('limite', '25'))
    except (ValueError, TypeError):
        raise BadRequest('Página e limite devem ser inteiros positivos.') from None
    if not 1 <= page <= 2**63 - 1 or not 1 <= size <= 100 or (page - 1) * size > 2**63 - 1:
        raise BadRequest('Página inválida ou limite fora do intervalo de 1 a 100.')
    return page, size


@control_door_bp.route('/pessoas/<int:pessoa_id>/permissoes', methods=['GET'])
@permission_admin
def person_permissions(pessoa_id):
    person = permission_person(pessoa_id)
    page, size = permission_pagination({'pagina', 'limite'})
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = PermissaoAcesso.query.filter_by(pessoa_id=person.id)
    rows = query.order_by(PermissaoAcesso.local_id).offset((page - 1) * size).limit(size).all()
    return jsonify(pessoa=serialize_person(person, now), total=query.count(), pagina=page, limite=size,
                   permissoes=[serialize_permission(row, now) for row in rows])


@control_door_bp.route('/pessoas/<int:pessoa_id>/permissoes/<int:local_id>', methods=['PUT'])
@permission_admin
def put_permission(pessoa_id, local_id):
    person = permission_person(pessoa_id)
    place = permission_local(local_id)
    data = request.get_json(silent=True) if request.is_json else None
    if not isinstance(data, dict) or not data or set(data) - {'inicio', 'expiracao', 'revogada'}:
        raise BadRequest('Informe um JSON não vazio somente com inicio, expiracao e revogada.')
    if 'revogada' in data and not isinstance(data['revogada'], bool):
        raise BadRequest('revogada deve ser verdadeiro ou falso.')
    permission = db.session.get(PermissaoAcesso, (person.id, place.id))
    created = permission is None
    start = permission_date(data['inicio'], 'inicio') if 'inicio' in data else (permission.inicio if permission else None)
    end = permission_date(data['expiracao'], 'expiracao') if 'expiracao' in data else (permission.expiracao if permission else None)
    if start is not None and end is not None and start >= end:
        raise BadRequest('O início deve ser anterior à expiração.')
    if created:
        permission = PermissaoAcesso(pessoa_id=person.id, local_id=place.id, revogada=False)
        db.session.add(permission)
    permission.inicio, permission.expiracao = start, end
    if 'revogada' in data:
        permission.revogada = data['revogada']
    db.session.commit()
    return jsonify(permissao=serialize_permission(permission, datetime.now(timezone.utc).replace(tzinfo=None))), 201 if created else 200


@control_door_bp.route('/pessoas/<int:pessoa_id>/permissoes/<int:local_id>/revogar', methods=['POST'])
@permission_admin
def revoke_permission(pessoa_id, local_id):
    permission_person(pessoa_id)
    permission_local(local_id)
    permission = db.session.get(PermissaoAcesso, (pessoa_id, local_id))
    if permission is None:
        raise NotFound('Permissão não encontrada.')
    if not permission.revogada:
        permission.revogada = True
        db.session.commit()
    return jsonify(permissao=serialize_permission(permission, datetime.now(timezone.utc).replace(tzinfo=None)))


@control_door_bp.route('/locais/<int:local_id>/autorizacoes', methods=['GET'])
@permission_admin
def local_permissions(local_id):
    place = permission_local(local_id)
    page, size = permission_pagination({'pagina', 'limite', 'situacao'})
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    state = request.args.get('situacao')
    if state is not None and state not in {'todas', 'vigente', 'agendada', 'expirada', 'revogada'}:
        raise BadRequest('Situação de permissão inválida.')
    enabled = PermissaoAcesso.revogada.is_(False)
    current = and_(enabled, or_(PermissaoAcesso.inicio.is_(None), PermissaoAcesso.inicio <= now),
                   or_(PermissaoAcesso.expiracao.is_(None), PermissaoAcesso.expiracao > now))
    query = PermissaoAcesso.query.filter_by(local_id=place.id)
    if state is None:
        visitors = Visitante.__table__
        query = query.join(User.__table__, User.id == PermissaoAcesso.pessoa_id).outerjoin(visitors, visitors.c.id == User.id).filter(
            current, User.status_conta.is_(True), User.credencial_rfid.is_not(None), registered_credential(),
            or_(User.tipo_user != 'visitante', and_(visitors.c.inicio <= now, visitors.c.expiracao > now)))
    elif state != 'todas':
        expressions = {'vigente': current, 'revogada': PermissaoAcesso.revogada.is_(True),
            'agendada': and_(enabled, PermissaoAcesso.inicio > now),
            'expirada': and_(enabled, PermissaoAcesso.expiracao <= now)}
        query = query.filter(expressions[state])
    total = query.count()
    rows = query.order_by(PermissaoAcesso.pessoa_id).offset((page - 1) * size).limit(size).all()
    return jsonify(local={'id': place.id, 'endereco': place.endereco}, total=total, pagina=page, limite=size,
                   autorizacoes=[serialize_permission(row, now) for row in rows])
