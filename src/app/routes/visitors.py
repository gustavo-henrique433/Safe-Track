"""Administração do perfil visitante, usando o JWT e os modelos existentes."""
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import BadRequest, Conflict, HTTPException, NotFound
from werkzeug.security import generate_password_hash

from app.config.extensions import db
from src.database.models import Local, Object, RFID, Registro_Acesso, Root, User, Visitante, VisitanteAcesso, PermissaoAcesso


visitors_bp = Blueprint('visitantes', __name__, url_prefix='/visitantes')


def root_required(function):
    """A mesma verificação de perfil Root, restrita aos endpoints novos."""
    @wraps(function)
    @jwt_required()
    def protected(*args, **kwargs):
        try:
            actor = db.session.get(User, get_jwt_identity())
            if not isinstance(actor, Root):
                return jsonify(message='Acesso negado: somente Root administra visitantes.'), 403
            return function(*args, **kwargs)
        except HTTPException as error:
            db.session.rollback()
            return jsonify(message=error.description), error.code
        except IntegrityError:
            db.session.rollback()
            return jsonify(message='Há conflito nos dados do visitante; nenhum dado foi gravado.'), 409
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(message='Não foi possível processar a operação de visitante.'), 500
    return protected


def read_body(allowed):
    data = request.get_json(silent=True) if request.is_json else None
    if not isinstance(data, dict) or not data:
        raise BadRequest('Informe um objeto JSON não vazio.')
    if set(data) - allowed:
        raise BadRequest('Há campos não permitidos na operação de visitante.')
    return data


def parse_instant(value, name):
    if not isinstance(value, str) or len(value) > 64:
        raise BadRequest(f'{name}: informe data e horário ISO 8601 com fuso.')
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            raise ValueError('Fuso ausente')
        return instant.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        raise BadRequest(f'{name}: data/horário inválido ou sem fuso.') from None


def iso_utc(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


def serialize_visitor(visitor):
    return {'id': visitor.id, 'nome': visitor.nome, 'email': visitor.email,
            'tipo_user': visitor.tipo_user, 'credencial_rfid': visitor.credencial_rfid,
            'inicio': iso_utc(visitor.inicio), 'expiracao': iso_utc(visitor.expiracao),
            'status': visitor.situacao(),
            'locais': [{'id': place.id, 'endereco': place.endereco} for place in visitor.locais]}


def find_visitor(visitor_id):
    visitor = Visitante.query.filter_by(id=visitor_id).first()
    if visitor is None:
        raise NotFound('Visitante não encontrado.')
    return visitor


def authorization_fields(data, visitor=None):
    uid = data.get('credencial_rfid', visitor.credencial_rfid if visitor else None)
    # Mantém o tipo e o vínculo herdados quando a UID não está sendo alterada.
    if visitor is None or 'credencial_rfid' in data:
        if not isinstance(uid, str) or not uid.strip() or len(uid) > 128:
            raise BadRequest('Informe uma credencial RFID textual válida.')
        if db.session.get(RFID, uid) is None:
            raise NotFound('Tag RFID não cadastrada.')
        owner = User.query.filter_by(credencial_rfid=uid).first()
        if Object.query.filter_by(id_rfid=uid).first() or (owner and (visitor is None or owner.id != visitor.id)):
            raise Conflict('Tag já associada a outro usuário ou objeto.')
    start = parse_instant(data['inicio'], 'inicio') if 'inicio' in data else (visitor.inicio if visitor else None)
    end = parse_instant(data['expiracao'], 'expiracao') if 'expiracao' in data else (visitor.expiracao if visitor else None)
    if start is None or end is None or start >= end:
        raise BadRequest('O início deve ser anterior à expiração.')
    ids = data.get('locais', [place.id for place in visitor.locais] if visitor else None)
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
        raise BadRequest('Informe de 1 a 100 locais autorizados.')
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in ids):
        raise BadRequest('Os locais devem ser identificadores inteiros positivos.')
    if len(ids) != len(set(ids)):
        raise BadRequest('Há locais autorizados repetidos.')
    places = Local.query.filter(Local.id.in_(ids)).order_by(Local.id).all()
    if len(places) != len(ids):
        raise NotFound('Há locais autorizados que não estão cadastrados.')
    return {'credencial_rfid': uid, 'inicio': start, 'expiracao': end, 'locais': places}


def positive_integer(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadRequest(f'{name} deve ser um inteiro positivo.') from None
    if number <= 0:
        raise BadRequest(f'{name} deve ser um inteiro positivo.')
    return number


def pagination():
    page = positive_integer(request.args.get('pagina', '1'), 'pagina')
    size = positive_integer(request.args.get('limite', '25'), 'limite')
    if size > 100:
        raise BadRequest('O limite máximo é 100 registros por página.')
    return page, size


def update_visitor_places(visitor, places):
    """Uma fonte ativa; mantém a vigência das permissões que continuam atribuídas."""
    selected = {place.id: place for place in places}
    current = {permission.local_id: permission for permission in visitor.permissoes}
    for local_id, permission in current.items():
        permission.revogada = local_id not in selected
    for local_id in selected.keys() - current.keys():
        visitor.permissoes.append(PermissaoAcesso(local_id=local_id, revogada=False))


@visitors_bp.route('', methods=['POST'])
@root_required
def create_visitor():
    data = read_body({'nome', 'email', 'senha', 'credencial_rfid', 'inicio', 'expiracao', 'locais'})
    for name, limit in (('nome', 100), ('email', 100), ('senha', 256)):
        value = data.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise BadRequest(f'{name}: informe um texto não vazio de até {limit} caracteres.')
    if '@' not in data['email']:
        raise BadRequest('Informe um e-mail de login válido.')
    if User.query.filter_by(email=data['email']).first():
        raise Conflict('E-mail já cadastrado.')
    fields = authorization_fields(data)
    places = fields.pop('locais')
    visitor = Visitante(nome=data['nome'], email=data['email'], senha=generate_password_hash(data['senha']),
                        tipo_user='visitante', **fields)
    db.session.add(visitor)
    update_visitor_places(visitor, places)
    db.session.commit()
    return jsonify(message='Visitante cadastrado com sucesso.', visitante=serialize_visitor(visitor)), 201


@visitors_bp.route('', methods=['GET'])
@root_required
def list_visitors():
    page, size = pagination()
    query = Visitante.query
    status = request.args.get('status')
    if status:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        filters = {
            'ativo': (Visitante.status_conta.is_(True), Visitante.inicio <= now, Visitante.expiracao > now),
            'agendado': (Visitante.status_conta.is_(True), Visitante.inicio > now),
            'expirado': (Visitante.status_conta.is_(True), Visitante.expiracao <= now),
            'revogado': (Visitante.status_conta.is_(False),),
        }
        if status not in filters:
            raise BadRequest('Situação de visitante inválida.')
        query = query.filter(*filters[status])
    total = query.count()
    visitors = query.order_by(Visitante.id).offset((page - 1) * size).limit(size).all()
    return jsonify(visitantes=[serialize_visitor(visitor) for visitor in visitors], total=total, pagina=page, limite=size)


@visitors_bp.route('/<int:visitor_id>', methods=['GET'])
@root_required
def get_visitor(visitor_id):
    return jsonify(visitante=serialize_visitor(find_visitor(visitor_id)))


@visitors_bp.route('/<int:visitor_id>', methods=['PUT'])
@root_required
def update_visitor(visitor_id):
    visitor = find_visitor(visitor_id)
    data = read_body({'credencial_rfid', 'inicio', 'expiracao', 'locais'})
    fields = authorization_fields(data, visitor)
    places = fields.pop('locais')
    for name, value in fields.items():
        setattr(visitor, name, value)
    if 'locais' in data:
        update_visitor_places(visitor, places)
    db.session.commit()
    return jsonify(visitante=serialize_visitor(visitor))


@visitors_bp.route('/<int:visitor_id>/revogar', methods=['POST'])
@root_required
def revoke_visitor(visitor_id):
    visitor = find_visitor(visitor_id)
    if visitor.status_conta:
        visitor.status_conta = False
        db.session.commit()
    return jsonify(message='Credencial de visitante revogada.', visitante=serialize_visitor(visitor))


@visitors_bp.route('/<int:visitor_id>/acessos', methods=['GET'])
@root_required
def visitor_accesses(visitor_id):
    visitor = find_visitor(visitor_id)
    page, size = pagination()
    query = Registro_Acesso.query.join(VisitanteAcesso, VisitanteAcesso.registro_id == Registro_Acesso.id) \
        .filter(VisitanteAcesso.visitante_id == visitor.id)
    start = parse_instant(request.args['inicio'], 'inicio') if request.args.get('inicio') else None
    end = parse_instant(request.args['fim'], 'fim') if request.args.get('fim') else None
    if start and end and start >= end:
        raise BadRequest('O início do filtro deve ser anterior ao fim.')
    if start:
        query = query.filter(Registro_Acesso.horario >= start)
    if end:
        query = query.filter(Registro_Acesso.horario < end)
    if request.args.get('local'):
        query = query.filter(Registro_Acesso.id_local == positive_integer(request.args['local'], 'local'))
    if request.args.get('resultado'):
        if request.args['resultado'] not in {'Liberado', 'Negado'}:
            raise BadRequest('Resultado de acesso inválido.')
        query = query.filter(Registro_Acesso.status_tentativa == request.args['resultado'])
    total = query.count()
    rows = query.order_by(Registro_Acesso.horario.desc(), Registro_Acesso.id.desc()).offset((page - 1) * size).limit(size).all()
    return jsonify(visitante_id=visitor.id, total=total, pagina=page, limite=size, acessos=[
        {'id': row.id, 'id_rfid': row.id_rfid, 'id_local': row.id_local,
         'horario': iso_utc(row.horario), 'status_tentativa': row.status_tentativa} for row in rows])
