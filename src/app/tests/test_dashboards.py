"""Relatórios com eventos fictícios no mesmo banco isolado da suíte existente."""
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError


ENDPOINTS = ('/api/dashboards/resumo', '/api/relatorios/acessos',
             '/api/relatorios/acessos.csv', '/api/relatorios/atividades')


@pytest.fixture
def analytics_data(database, models, inventory, users, visitor_factory):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    visitors = [
        visitor_factory(inicio=now - timedelta(days=1), expiracao=now + timedelta(days=1)),
        visitor_factory(inicio=now - timedelta(days=2), expiracao=now - timedelta(days=1)),
        visitor_factory(inicio=now + timedelta(days=1), expiracao=now + timedelta(days=2)),
        visitor_factory(inicio=now - timedelta(days=2), expiracao=now - timedelta(days=1), status_conta=False),
    ]
    other_place = models.Local(endereco='Sala secundária', descricao='Teste', responsavel='Equipe fictícia')
    database.session.add(other_place)
    database.session.flush()
    first = inventory['place'].id
    second = other_place.id
    fields = [
        (first, 'Liberado', datetime(2026, 11, 1), inventory['tags'][2].uid),
        (first, 'Negado', datetime(2026, 11, 1, 9), visitors[0].credencial_rfid),
        (second, 'Liberado', datetime(2026, 11, 2, 12), visitors[0].credencial_rfid),
        (second, 'Negado', datetime(2026, 11, 2, 12), None),
        (first, None, datetime(2026, 11, 2, 13), None),
        (second, 'Outro', datetime(2026, 11, 3), None),
        (first, 'Liberado', datetime(2026, 10, 31, 23, 59, 59), inventory['tags'][2].uid),
    ]
    records = [models.Registro_Acesso(id_local=local, status_tentativa=status, horario=when, id_rfid=uid)
               for local, status, when, uid in fields]
    database.session.add_all(records)
    database.session.flush()
    database.session.add_all([
        models.VisitanteAcesso(registro_id=record.id, visitante_id=visitors[0].id) for record in records[1:3]])
    activities = [
        models.Historico_patrimonio(id_objeto=inventory['item'].id, id_usuario=None, acao='buscar_objeto_id',
                                   horario=datetime(2026, 11, 1, 9), status_tentativa='sucesso'),
        models.Historico_patrimonio(id_objeto=None, id_usuario=users['root'].id, acao='buscar_objeto_uid',
                                   horario=datetime(2026, 11, 2, 12), status_tentativa='falha'),
        models.Historico_patrimonio(id_objeto=inventory['item'].id, id_usuario=users['user'].id, acao='buscar_objeto_uid',
                                   horario=datetime(2026, 11, 3), status_tentativa='sucesso'),
    ]
    database.session.add_all(activities)
    database.session.commit()
    return {'records': records, 'visitors': visitors, 'other_place': other_place, 'activities': activities}


@pytest.fixture
def visitor_headers(visitor_factory):
    from flask_jwt_extended import create_access_token
    visitor = visitor_factory()
    return {'Authorization': 'Bearer ' + create_access_token(identity=str(visitor.id))}


@pytest.mark.parametrize('endpoint', ENDPOINTS)
@pytest.mark.parametrize('role,status', [(None, 401), ('user', 403), ('visitante', 403)])
def test_relatorios_exigem_root(client, headers, visitor_headers, endpoint, role, status):
    authorization = visitor_headers if role == 'visitante' else headers[role] if role else {}
    assert client.get(endpoint, headers=authorization).status_code == status


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_token_sem_usuario_cadastrado_nao_acessa_relatorios(client, endpoint):
    from flask_jwt_extended import create_access_token
    token = create_access_token(identity='999999')
    assert client.get(endpoint, headers={'Authorization': 'Bearer ' + token}).status_code == 403


def test_resumo_sem_eventos_diferencia_zero_de_indicador_indisponivel(client, headers):
    response = client.get('/api/dashboards/resumo', headers=headers['root'])
    assert response.status_code == 200
    result = response.json
    assert result['cadastros'] == {'objetos': 0, 'tags_rfid': 0, 'locais': 0}
    assert result['visitantes'] == {'cadastrados': 0, 'ativos': 0, 'agendados': 0, 'expirados': 0, 'revogados': 0}
    assert result['acessos'] == {'total': 0, 'autorizados': 0, 'negados': 0, 'indefinidos': 0}
    assert result['evolucao_diaria']['dias'] == []
    assert result['evolucao_diaria']['ha_dias_anteriores'] is False
    assert result['salas_mais_acessadas'] == result['ultimos_acessos'] == result['ultimas_atividades_patrimoniais'] == []
    assert {item['indicador'] for item in result['indisponiveis']} == {
        'requisicoes_http', 'retiradas_e_movimentacoes_de_objetos'}
    assert all(item['valor'] is None and item['motivo'] for item in result['indisponiveis'])
    assert result['gerado_em'].endswith('Z')


def test_resumo_conta_eventos_e_situacoes_de_visitantes_sem_sobreposicao(client, headers, analytics_data):
    result = client.get('/api/dashboards/resumo', headers=headers['root']).json
    assert result['cadastros'] == {'objetos': 1, 'tags_rfid': 7, 'locais': 2}
    assert result['visitantes'] == {'cadastrados': 4, 'ativos': 1, 'expirados': 1, 'agendados': 1, 'revogados': 1}
    assert result['acessos'] == {'total': 7, 'autorizados': 3, 'negados': 2, 'indefinidos': 2}
    assert result['evolucao_diaria']['dias'] == [
        {'data': '2026-10-31', 'total': 1, 'autorizados': 1, 'negados': 0, 'indefinidos': 0},
        {'data': '2026-11-01', 'total': 2, 'autorizados': 1, 'negados': 1, 'indefinidos': 0},
        {'data': '2026-11-02', 'total': 3, 'autorizados': 1, 'negados': 1, 'indefinidos': 1},
        {'data': '2026-11-03', 'total': 1, 'autorizados': 0, 'negados': 0, 'indefinidos': 1},
    ]
    assert [row['autorizados'] for row in result['salas_mais_acessadas']] == [2, 1]
    assert [row['id'] for row in result['ultimos_acessos']] == [6, 5, 4, 3, 2, 1, 7]
    assert [row['id'] for row in result['ultimas_atividades_patrimoniais']] == [3, 2, 1]


@pytest.mark.parametrize('filters,ids,counts', [
    ({'inicio': '2026-11-01', 'fim': '2026-11-01'}, [2, 1], (2, 1, 1, 0)),
    ({'inicio': '2026-11-01T21:00:00-03:00', 'fim': '2026-11-02T10:00:00-03:00'}, [4, 3], (2, 1, 1, 0)),
    ({'inicio': '2026-11-03'}, [6], (1, 0, 0, 1)),
    ({'fim': '2026-10-31'}, [7], (1, 1, 0, 0)),
    ({'resultado': 'Liberado'}, [3, 1, 7], (3, 3, 0, 0)),
    ({'resultado': 'Negado'}, [4, 2], (2, 0, 2, 0)),
    ({'resultado': 'Indefinido'}, [6, 5], (2, 0, 0, 2)),
    ({'local': '$sala2'}, [6, 4, 3], (3, 1, 1, 1)),
    ({'visitante': '$visitante'}, [3, 2], (2, 1, 1, 0)),
    ({'visitante': '$visitante', 'local': '$sala1', 'resultado': 'Negado'}, [2], (1, 0, 1, 0)),
    ({'local': 99999}, [], (0, 0, 0, 0)),
    ({'visitante': 99999}, [], (0, 0, 0, 0)),
])
def test_filtros_coerentes_no_resumo_json_e_csv(client, headers, analytics_data, inventory, filters, ids, counts):
    replacements = {'$sala1': inventory['place'].id, '$sala2': analytics_data['other_place'].id,
                    '$visitante': analytics_data['visitors'][0].id}
    params = {key: replacements.get(value, value) for key, value in filters.items()}
    report = client.get('/api/relatorios/acessos', query_string=params, headers=headers['root'])
    assert report.status_code == 200
    assert report.json['total'] == len(ids)
    assert [row['id'] for row in report.json['acessos']] == ids
    summary = client.get('/api/dashboards/resumo', query_string=params, headers=headers['root'])
    assert summary.status_code == 200
    assert summary.json['acessos'] == dict(zip(('total', 'autorizados', 'negados', 'indefinidos'), counts))
    # Cadastros e situação atual não são históricos reconstruídos pelo período.
    assert summary.json['cadastros']['objetos'] == 1
    assert summary.json['visitantes']['cadastrados'] == 4
    exported = client.get('/api/relatorios/acessos.csv', query_string=params, headers=headers['root'])
    assert exported.status_code == 200
    rows = list(csv.DictReader(StringIO(exported.data.decode('utf-8-sig')), delimiter=';'))
    assert [int(row['id']) for row in rows] == ids


def test_filtro_de_data_informa_fim_exclusivo_utc(client, headers):
    result = client.get('/api/relatorios/acessos?inicio=2026-11-01&fim=2026-11-01', headers=headers['root']).json
    assert result['filtros'] == {'fuso': 'UTC', 'inicio': '2026-11-01T00:00:00Z',
                                 'fim_exclusivo': '2026-11-02T00:00:00Z'}


@pytest.mark.parametrize('params', [
    {'inicio': ''}, {'inicio': 'invalido'}, {'fim': '2026-02-30'}, {'fim': '9999-12-31'},
    {'inicio': '2026-11-01T10:00:00'}, {'inicio': '9999-12-31T23:59:59-23:00'},
    {'inicio': 'x' * 65}, {'inicio': '2026-11-03', 'fim': '2026-11-01'},
    {'inicio': '2026-11-01T00:00:00Z', 'fim': '2026-11-01T00:00:00Z'},
    {'local': 0}, {'local': -1}, {'local': ''}, {'local': 'abc'}, {'local': '1.5'},
    {'local': str(2**63)}, {'visitante': 'true'}, {'visitante': 0},
    {'resultado': ''}, {'resultado': 'sucesso'}, {'resultado': "' OR 1=1 --"},
    {'pagina': 0}, {'pagina': 'x'}, {'limite': 0}, {'limite': 101},
    {'pagina': str(2**63 - 1), 'limite': 100}, {'limite': str(2**63)},
    {'objeto': 1}, {'campo_desconhecido': 1},
    [('local', '1'), ('local', '2')],
])
def test_relatorio_rejeita_filtros_invalidos_com_400_sem_gravar(client, headers, models, params):
    response = client.get('/api/relatorios/acessos', query_string=params, headers=headers['root'])
    assert response.status_code == 400
    assert 'message' in response.json
    assert models.Registro_Acesso.query.count() == models.Historico_patrimonio.query.count() == 0


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_validacao_dos_novos_endpoints_preserva_http_400(client, headers, endpoint):
    assert client.get(endpoint, query_string={'inicio': 'invalido'}, headers=headers['root']).status_code == 400


def test_paginacao_estavel_e_pagina_vazia_preservam_total(client, headers, analytics_data):
    result = client.get('/api/relatorios/acessos?pagina=2&limite=2', headers=headers['root']).json
    assert result['total'] == 7 and result['pagina'] == 2 and result['limite'] == 2
    assert [row['id'] for row in result['acessos']] == [4, 3]
    result = client.get('/api/relatorios/acessos?pagina=999&limite=100', headers=headers['root']).json
    assert result['total'] == 7 and result['acessos'] == []


def test_nome_de_visitante_depende_do_vinculo_do_evento_e_nao_do_dono_atual_da_tag(
        client, headers, analytics_data, visitor_factory, database, models, password_hash):
    previous = analytics_data['visitors'][0]
    uid = previous.credencial_rfid
    previous.credencial_rfid = None
    database.session.commit()
    current = visitor_factory(credencial_rfid=uid)
    unlinked = models.Registro_Acesso(id_rfid=uid, id_local=analytics_data['other_place'].id,
                                     horario=datetime(2026, 11, 4), status_tentativa='Liberado')
    database.session.add(unlinked)
    database.session.commit()
    response = client.get('/api/relatorios/acessos', headers=headers['root'])
    by_id = {row['id']: row for row in response.json['acessos']}
    assert by_id[2]['visitante_id'] == previous.id != current.id
    assert by_id[2]['visitante_nome'] == previous.nome
    assert by_id[unlinked.id]['visitante_id'] is by_id[unlinked.id]['visitante_nome'] is None
    assert by_id[1]['visitante_id'] is None
    assert password_hash.encode() not in response.data
    assert b'email' not in response.data and b'senha' not in response.data


def test_registro_com_local_ausente_continua_no_relatorio(client, headers, database, models):
    record = models.Registro_Acesso(id_local=99999, horario=datetime(2026, 11, 1), status_tentativa='Liberado')
    database.session.add(record)
    database.session.commit()
    result = client.get('/api/relatorios/acessos', headers=headers['root']).json
    assert result['total'] == 1
    assert result['acessos'][0]['id_local'] == 99999 and result['acessos'][0]['local'] is None
    summary = client.get('/api/dashboards/resumo', headers=headers['root']).json
    assert summary['acessos']['autorizados'] == 1
    assert summary['salas_mais_acessadas'] == [{'id_local': 99999, 'local': None, 'autorizados': 1}]
    assert models.Local.query.count() == 0


def test_evolucao_informa_limite_sem_truncar_totais(client, headers, database, models, inventory):
    start = datetime(2020, 1, 1)
    database.session.add_all([models.Registro_Acesso(id_local=inventory['place'].id,
        horario=start + timedelta(days=offset), status_tentativa='Liberado') for offset in range(367)])
    database.session.commit()
    result = client.get('/api/dashboards/resumo', headers=headers['root']).json
    assert result['acessos']['total'] == 367
    series = result['evolucao_diaria']
    assert len(series['dias']) == series['limite_dias_com_registros'] == 366
    assert series['ha_dias_anteriores'] is True
    assert series['dias'][0]['data'] == '2020-01-02'
    assert len(result['ultimos_acessos']) == 10


def test_ranking_limita_dez_salas_e_conta_somente_liberados(client, headers, database, models, inventory):
    places = [models.Local(endereco=f'Sala {index}', descricao='Teste', responsavel='Equipe') for index in range(11)]
    database.session.add_all(places)
    database.session.flush()
    now = datetime(2026, 11, 1)
    database.session.add_all([models.Registro_Acesso(id_local=place.id, horario=now, status_tentativa='Liberado')
                              for place in places])
    database.session.add_all([models.Registro_Acesso(id_local=inventory['place'].id, horario=now,
                                                   status_tentativa='Negado') for _ in range(20)])
    database.session.commit()
    result = client.get('/api/dashboards/resumo', headers=headers['root']).json
    assert [row['id_local'] for row in result['salas_mais_acessadas']] == [place.id for place in places[:10]]
    assert all(row['autorizados'] == 1 for row in result['salas_mais_acessadas'])
    assert result['acessos']['negados'] == 20


@pytest.mark.parametrize('params,ids', [
    ({'inicio': '2026-11-01', 'fim': '2026-11-01'}, [1]),
    ({'resultado': 'falha'}, [2]), ({'resultado': 'sucesso'}, [3, 1]),
    ({'acao': 'buscar_objeto_id'}, [1]), ({'objeto': 1}, [3, 1]),
    ({'usuario': 1}, [2]), ({'usuario': 2}, [3]),
    ({'objeto': 99999}, []), ({'acao': "' OR 1=1 --"}, []),
])
def test_atividades_filtram_consultas_reais_sem_inferir_movimentacao(client, headers, analytics_data, params, ids):
    response = client.get('/api/relatorios/atividades', query_string=params, headers=headers['root'])
    assert response.status_code == 200
    assert response.json['total'] == len(ids)
    assert [row['id'] for row in response.json['atividades']] == ids
    assert 'sem comprovação de movimentação' in response.json['escopo']


@pytest.mark.parametrize('params', [
    {'local': 1}, {'visitante': 1}, {'objeto': 0}, {'usuario': -1},
    {'resultado': 'Liberado'}, {'acao': ''}, {'acao': ' '}, {'acao': 'x' * 101},
])
def test_atividades_rejeitam_filtros_sem_significado_nessa_fonte(client, headers, params):
    assert client.get('/api/relatorios/atividades', query_string=params, headers=headers['root']).status_code == 400


def test_resumo_filtra_atividades_apenas_por_periodo(client, headers, analytics_data):
    result = client.get('/api/dashboards/resumo', query_string={
        'inicio': '2026-11-02', 'fim': '2026-11-02', 'local': 99999, 'resultado': 'Liberado'},
        headers=headers['root']).json
    assert result['acessos']['total'] == 0
    assert [row['id'] for row in result['ultimas_atividades_patrimoniais']] == [2]
    assert 'somente pelo período' in result['escopo']['atividades_patrimoniais']


def test_busca_original_de_objeto_aparece_como_consulta_no_resumo(client, headers, inventory):
    assert client.get(f"/buscar_objeto_id/{inventory['item'].id}").status_code == 200
    result = client.get('/api/dashboards/resumo', headers=headers['root']).json
    activity = result['ultimas_atividades_patrimoniais'][0]
    assert activity['acao'] == 'buscar_objeto_id' and activity['status_tentativa'] == 'sucesso'
    assert activity['id_usuario'] is None
    assert result['acessos']['total'] == 0
    assert all(item['valor'] is None for item in result['indisponiveis'])


def test_leitura_http_com_mac_nao_vira_acesso_ou_retirada(client, headers, inventory, models):
    response = client.post('/cadastrar_rfid', json={'uid': inventory['tags'][0].uid,
        'date': '2026-11-01', 'mac_adress': inventory['device'].mac})
    assert response.status_code == 200
    assert response.json == {'message': 'Leitura processada !!'}
    result = client.get('/api/dashboards/resumo', headers=headers['root']).json
    assert result['acessos']['total'] == 0
    assert models.Historico_patrimonio.query.count() == 0
    assert all(item['valor'] is None for item in result['indisponiveis'])


def test_eventos_da_porta_original_alimentam_resumo_e_vinculo_visitante(
        client, headers, inventory, visitor_factory, database, models, users):
    database.session.add(models.PermissaoAcesso(pessoa_id=users['user'].id, local_id=inventory['place'].id))
    database.session.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    visitor = visitor_factory(inicio=now + timedelta(days=1), expiracao=now + timedelta(days=2))
    for uid, status, opens in [(inventory['tags'][2].uid, 200, True), ('uid-desconhecida', 403, False),
                               (visitor.credencial_rfid, 403, False)]:
        response = client.post('/acessar_porta', json={'uid_solicitante': uid, 'local': inventory['place'].id})
        assert response.status_code == status
        assert response.json['abrir'] is opens
    result = client.get('/api/dashboards/resumo', headers=headers['root']).json
    assert result['acessos'] == {'total': 3, 'autorizados': 1, 'negados': 2, 'indefinidos': 0}
    report = client.get('/api/relatorios/acessos', query_string={'visitante': visitor.id}, headers=headers['root']).json
    assert report['total'] == 1 and report['acessos'][0]['status_tentativa'] == 'Negado'


@pytest.mark.parametrize('value', ['=1+1', '+1+1', '-1+1', '@SOMA(1)', '  =1+1', '\ttexto', '\rtexto', '\ntexto'])
def test_csv_neutraliza_formulas_sem_modificar_cadastro(client, headers, database, inventory, analytics_data, value):
    inventory['place'].endereco = value
    database.session.commit()
    exported = client.get('/api/relatorios/acessos.csv', headers=headers['root'])
    assert exported.status_code == 200
    rows = list(csv.DictReader(StringIO(exported.data.decode('utf-8-sig')), delimiter=';'))
    assert all(row['local'] == "'" + value for row in rows if int(row['id_local']) == inventory['place'].id)
    assert inventory['place'].endereco == value
    result = client.get('/api/relatorios/acessos', headers=headers['root']).json
    assert all(row['local'] == value for row in result['acessos'] if row['id_local'] == inventory['place'].id)


def test_csv_preserva_acentos_separadores_e_quebras_de_linha(client, headers, database, inventory, analytics_data):
    inventory['place'].endereco = 'Sala; patrimônio\nSão Paulo'
    analytics_data['visitors'][0].nome = '=HIPERLINK("exemplo")'
    database.session.commit()
    response = client.get('/api/relatorios/acessos.csv', headers=headers['root'])
    assert response.data.startswith(b'\xef\xbb\xbf')
    assert response.mimetype == 'text/csv'
    assert response.headers['Content-Disposition'] == 'attachment; filename="safe-track-acessos.csv"'
    assert response.headers['Cache-Control'] == 'no-store'
    rows = list(csv.DictReader(StringIO(response.data.decode('utf-8-sig')), delimiter=';'))
    assert len(rows) == 7
    assert rows[0]['visitante_id'] == rows[0]['visitante_nome'] == ''
    assert rows[-1]['local'] == 'Sala; patrimônio\nSão Paulo'
    assert next(row for row in rows if row['id'] == '2')['visitante_nome'] == '\'=HIPERLINK("exemplo")'


def test_csv_exige_restringir_filtros_quando_ultrapassa_limite(client, headers, analytics_data, monkeypatch):
    from app.routes import dashboards
    monkeypatch.setattr(dashboards, 'CSV_LIMIT', 2)
    response = client.get('/api/relatorios/acessos.csv', headers=headers['root'])
    assert response.status_code == 400 and 'Restrinja' in response.json['message']
    response = client.get('/api/relatorios/acessos.csv?resultado=Negado', headers=headers['root'])
    assert response.status_code == 200
    assert len(list(csv.DictReader(StringIO(response.data.decode('utf-8-sig')), delimiter=';'))) == 2


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_consultas_administrativas_nao_inserem_eventos_ou_alteram_cadastros(
        client, headers, database, models, analytics_data, endpoint):
    from sqlalchemy import select
    def snapshot():
        return {table.name: database.session.execute(select(table).order_by(*table.primary_key.columns)).all()
                for table in database.metadata.sorted_tables}
    before = snapshot()
    assert client.get(endpoint, headers=headers['root']).status_code == 200
    assert snapshot() == before


@pytest.mark.parametrize('endpoint,function', [
    ('/api/dashboards/resumo', 'dashboard_summary'), ('/api/relatorios/acessos', 'access_query'),
    ('/api/relatorios/acessos.csv', 'access_query'), ('/api/relatorios/atividades', 'activity_query')])
def test_erro_sql_nos_novos_relatorios_e_generico_sem_expor_consulta(client, headers, endpoint, function):
    with patch(f'app.routes.dashboards.queries.{function}',
               side_effect=OperationalError('SELECT dado_sigilosissimo', {}, Exception('detalhe interno'))), \
            patch('app.routes.dashboards.db.session.rollback') as rollback:
        response = client.get(endpoint, headers=headers['root'])
    assert response.status_code == 500
    assert response.json == {'message': 'Não foi possível consultar os dados administrativos.'}
    assert b'dado_sigilosissimo' not in response.data and b'detalhe interno' not in response.data
    rollback.assert_called_once()
