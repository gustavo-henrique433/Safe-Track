"""Endpoints administrativos novos, sem modificar os contratos operacionais."""
import csv
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from io import StringIO

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException

from app.config.extensions import db
from app.services.dashboards import queries
from src.database.models import Root, User


dashboards_bp = Blueprint('dashboards', __name__, url_prefix='/api')
ACCESS_FILTERS = {'inicio', 'fim', 'local', 'visitante', 'resultado'}
ACTIVITY_FILTERS = {'inicio', 'fim', 'objeto', 'usuario', 'acao', 'resultado'}
MAX_SQLITE_INTEGER = 2**63 - 1
CSV_LIMIT = 10_000


def root_required(function):
    @wraps(function)
    @jwt_required()
    def protected(*args, **kwargs):
        try:
            if not isinstance(db.session.get(User, get_jwt_identity()), Root):
                return jsonify(message='Acesso negado: somente Root consulta relatórios administrativos.'), 403
            return function(*args, **kwargs)
        except HTTPException as error:
            db.session.rollback()
            return jsonify(message=error.description), error.code
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(message='Não foi possível consultar os dados administrativos.'), 500
    return protected


def check_parameters(allowed):
    if set(request.args) - allowed:
        raise BadRequest('Há filtros não permitidos nesta consulta.')
    if any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise BadRequest('Informe cada filtro uma única vez.')


def parse_boundary(value, name):
    if not value or len(value) > 64:
        raise BadRequest(f'{name}: informe uma data ou data e horário com fuso.')
    try:
        if len(value) == 10:
            instant = datetime.combine(date.fromisoformat(value), datetime.min.time())
            return instant + timedelta(days=1) if name == 'fim' else instant
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            raise ValueError('Fuso ausente')
        return instant.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        raise BadRequest(f'{name}: data inválida ou horário sem fuso.') from None


def positive_integer(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadRequest(f'{name} deve ser um inteiro positivo.') from None
    if not 0 < number <= MAX_SQLITE_INTEGER:
        raise BadRequest(f'{name} está fora do intervalo permitido.')
    return number


def read_filters(activity=False):
    filters = {}
    for name in ('inicio', 'fim'):
        if name in request.args:
            filters[name] = parse_boundary(request.args[name], name)
    if filters.get('inicio') is not None and filters.get('fim') is not None and filters['inicio'] >= filters['fim']:
        raise BadRequest('O início do período deve ser anterior ao fim exclusivo.')
    for name in (('objeto', 'usuario') if activity else ('local', 'visitante')):
        if name in request.args:
            filters[name] = positive_integer(request.args[name], name)
    if 'resultado' in request.args:
        allowed = {'sucesso', 'falha'} if activity else {'Liberado', 'Negado', 'Indefinido'}
        if request.args['resultado'] not in allowed:
            raise BadRequest('Resultado inválido para esta consulta.')
        filters['resultado'] = request.args['resultado']
    if activity and 'acao' in request.args:
        if not request.args['acao'].strip() or len(request.args['acao']) > 100:
            raise BadRequest('Informe uma ação de até 100 caracteres.')
        filters['acao'] = request.args['acao']
    return filters


def describe_filters(filters):
    return {'fuso': 'UTC', 'inicio': queries.iso_utc(filters['inicio']) if 'inicio' in filters else None,
            'fim_exclusivo': queries.iso_utc(filters['fim']) if 'fim' in filters else None,
            **{key: value for key, value in filters.items() if key not in {'inicio', 'fim'}}}


def pagination():
    page = positive_integer(request.args.get('pagina', '1'), 'pagina')
    size = positive_integer(request.args.get('limite', '25'), 'limite')
    if size > 100 or (page - 1) * size > MAX_SQLITE_INTEGER:
        raise BadRequest('Use limite de até 100 e uma página dentro do intervalo permitido.')
    return page, size


@dashboards_bp.route('/dashboards/resumo', methods=['GET'])
@root_required
def summary():
    check_parameters(ACCESS_FILTERS)
    filters = read_filters()
    return jsonify(filtros=describe_filters(filters), **queries.dashboard_summary(filters))


@dashboards_bp.route('/relatorios/acessos', methods=['GET'])
@root_required
def accesses():
    check_parameters(ACCESS_FILTERS | {'pagina', 'limite'})
    filters = read_filters()
    page, size = pagination()
    query = queries.access_query(filters)
    return jsonify(filtros=describe_filters(filters), total=query.count(), pagina=page, limite=size,
                   acessos=queries.access_rows(query, offset=(page - 1) * size, limit=size))


def csv_cell(value):
    if value is None:
        return ''
    text = str(value)
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


@dashboards_bp.route('/relatorios/acessos.csv', methods=['GET'])
@root_required
def access_csv():
    check_parameters(ACCESS_FILTERS)
    filters = read_filters()
    rows = queries.access_rows(queries.access_query(filters), limit=CSV_LIMIT + 1)
    if len(rows) > CSV_LIMIT:
        raise BadRequest('A exportação permite até 10000 registros. Restrinja os filtros do relatório.')
    output = StringIO(newline='')
    writer = csv.writer(output, delimiter=';')
    columns = ('id', 'horario', 'id_rfid', 'id_local', 'local', 'status_tentativa', 'visitante_id', 'visitante_nome')
    writer.writerow(columns)
    writer.writerows([csv_cell(row[key]) for key in columns] for row in rows)
    return Response('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8', headers={
        'Content-Disposition': 'attachment; filename="safe-track-acessos.csv"', 'Cache-Control': 'no-store'})


@dashboards_bp.route('/relatorios/atividades', methods=['GET'])
@root_required
def activities():
    check_parameters(ACTIVITY_FILTERS | {'pagina', 'limite'})
    filters = read_filters(activity=True)
    page, size = pagination()
    query = queries.activity_query(filters)
    return jsonify(filtros=describe_filters(filters), total=query.count(), pagina=page, limite=size,
                   escopo='Histórico patrimonial existente: consultas registradas, sem comprovação de movimentação.',
                   atividades=queries.activity_rows(query, offset=(page - 1) * size, limit=size))
