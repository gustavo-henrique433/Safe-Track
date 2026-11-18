"""Indicadores de leitura; não cria tabelas nem produz eventos operacionais."""
from datetime import datetime, timezone

from sqlalchemy import case, func, or_

from app.config.extensions import db
from src.database.models import (
    Historico_patrimonio, Local, Object, RFID, Registro_Acesso, User,
    Visitante, VisitanteAcesso,
)


DAILY_LIMIT = 366


def iso_utc(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


def period_query(query, column, filters):
    if filters.get('inicio') is not None:
        query = query.filter(column >= filters['inicio'])
    if filters.get('fim') is not None:
        query = query.filter(column < filters['fim'])
    return query


def undefined_result():
    return or_(Registro_Acesso.status_tentativa.is_(None),
               Registro_Acesso.status_tentativa.notin_(['Liberado', 'Negado']))


def access_query(filters):
    query = Registro_Acesso.query.outerjoin(
        VisitanteAcesso, VisitanteAcesso.registro_id == Registro_Acesso.id)
    query = period_query(query, Registro_Acesso.horario, filters)
    if filters.get('local') is not None:
        query = query.filter(Registro_Acesso.id_local == filters['local'])
    if filters.get('visitante') is not None:
        query = query.filter(VisitanteAcesso.visitante_id == filters['visitante'])
    if filters.get('resultado') == 'Indefinido':
        query = query.filter(undefined_result())
    elif filters.get('resultado') is not None:
        query = query.filter(Registro_Acesso.status_tentativa == filters['resultado'])
    return query


def activity_query(filters):
    query = period_query(Historico_patrimonio.query, Historico_patrimonio.horario, filters)
    for parameter, column in [('objeto', Historico_patrimonio.id_objeto),
                              ('usuario', Historico_patrimonio.id_usuario),
                              ('acao', Historico_patrimonio.acao),
                              ('resultado', Historico_patrimonio.status_tentativa)]:
        if filters.get(parameter) is not None:
            query = query.filter(column == filters[parameter])
    return query


def access_rows(query, offset=0, limit=25):
    rows = query.outerjoin(Local, Local.id == Registro_Acesso.id_local).outerjoin(
        User, User.id == VisitanteAcesso.visitante_id).with_entities(
            Registro_Acesso, Local.endereco, VisitanteAcesso.visitante_id, User.nome
        ).order_by(Registro_Acesso.horario.desc(), Registro_Acesso.id.desc()).offset(offset).limit(limit).all()
    return [{'id': record.id, 'id_rfid': record.id_rfid, 'id_local': record.id_local,
             'local': location, 'horario': iso_utc(record.horario),
             'status_tentativa': record.status_tentativa,
             'visitante_id': visitor_id, 'visitante_nome': visitor_name}
            for record, location, visitor_id, visitor_name in rows]


def activity_rows(query, offset=0, limit=25):
    rows = query.outerjoin(Object, Object.id == Historico_patrimonio.id_objeto).with_entities(
        Historico_patrimonio, Object.nome
    ).order_by(Historico_patrimonio.horario.desc(), Historico_patrimonio.id.desc()).offset(offset).limit(limit).all()
    return [{'id': record.id, 'id_objeto': record.id_objeto, 'objeto': object_name,
             'id_usuario': record.id_usuario, 'acao': record.acao,
             'horario': iso_utc(record.horario), 'status_tentativa': record.status_tentativa}
            for record, object_name in rows]


def result_columns():
    return [func.count(Registro_Acesso.id),
            func.coalesce(func.sum(case((Registro_Acesso.status_tentativa == 'Liberado', 1), else_=0)), 0),
            func.coalesce(func.sum(case((Registro_Acesso.status_tentativa == 'Negado', 1), else_=0)), 0),
            func.coalesce(func.sum(case((undefined_result(), 1), else_=0)), 0)]


def result_counts(values):
    return dict(zip(('total', 'autorizados', 'negados', 'indefinidos'), values))


def visitor_counts(now):
    enabled = Visitante.status_conta.is_(True)
    values = db.session.query(
        func.count(Visitante.id),
        func.coalesce(func.sum(case((enabled & (Visitante.inicio <= now) & (Visitante.expiracao > now), 1), else_=0)), 0),
        func.coalesce(func.sum(case((enabled & (Visitante.inicio > now), 1), else_=0)), 0),
        func.coalesce(func.sum(case((enabled & (Visitante.expiracao <= now), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Visitante.status_conta.is_(False), 1), else_=0)), 0),
    ).select_from(Visitante).one()
    return dict(zip(('cadastrados', 'ativos', 'agendados', 'expirados', 'revogados'), values))


def dashboard_summary(filters):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = access_query(filters)
    counts = result_counts(query.with_entities(*result_columns()).one())
    day = func.date(Registro_Acesso.horario)
    daily = query.with_entities(day, *result_columns()).group_by(day).order_by(day.desc()).limit(DAILY_LIMIT + 1).all()
    ranking = query.filter(Registro_Acesso.status_tentativa == 'Liberado').outerjoin(
        Local, Local.id == Registro_Acesso.id_local).with_entities(
            Registro_Acesso.id_local, Local.endereco, func.count(Registro_Acesso.id).label('total')
        ).group_by(Registro_Acesso.id_local, Local.endereco).order_by(
            func.count(Registro_Acesso.id).desc(), Registro_Acesso.id_local).limit(10).all()
    # O histórico patrimonial não registra o local; só o período é aplicável aqui.
    activities = activity_query({key: filters.get(key) for key in ('inicio', 'fim')})
    return {
        'gerado_em': iso_utc(now),
        'cadastros': {'objetos': Object.query.count(), 'tags_rfid': RFID.query.count(), 'locais': Local.query.count()},
        'visitantes': visitor_counts(now),
        'acessos': counts,
        'evolucao_diaria': {
            'dias': [{'data': row[0], **result_counts(row[1:])} for row in reversed(daily[:DAILY_LIMIT])],
            'limite_dias_com_registros': DAILY_LIMIT, 'ha_dias_anteriores': len(daily) > DAILY_LIMIT,
        },
        'salas_mais_acessadas': [{'id_local': local_id, 'local': name, 'autorizados': total}
                                for local_id, name, total in ranking],
        'ultimos_acessos': access_rows(query, limit=10),
        'ultimas_atividades_patrimoniais': activity_rows(activities, limit=10),
        'escopo': {
            'cadastros_e_visitantes': 'Situação atual; os filtros de acesso não se aplicam a esses totais.',
            'acessos': 'Tentativas efetivamente gravadas em registro_acesso; horários em UTC.',
            'salas_mais_acessadas': 'Até 10 locais por tentativas Liberado, respeitando os filtros de acesso.',
            'evolucao_diaria': 'Até 366 dias com eventos em UTC; dias sem registros não são preenchidos.',
            'atividades_patrimoniais': 'Histórico existente, filtrado somente pelo período; registra consultas, sem comprovar movimentações.',
            'identificacao': 'Visitante somente pelo vínculo gravado na tentativa; nomes e endereços são os cadastros atuais.',
        },
        'indisponiveis': [
            {'indicador': 'requisicoes_http', 'valor': None,
             'motivo': 'Não há contador persistente confiável de requisições HTTP no banco.'},
            {'indicador': 'retiradas_e_movimentacoes_de_objetos', 'valor': None,
             'motivo': 'Consultas e leituras RFID não comprovam retiradas, devoluções ou movimentações.'},
        ],
    }
