"""Controle individual, somente com SQLite isolado e identidades fictícias."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


@pytest.fixture
def grant(database, models):
    def create(person, place, **values):
        permission = models.PermissaoAcesso(pessoa_id=person.id, local_id=place.id, **values)
        database.session.add(permission)
        database.session.commit()
        return permission
    return create


@pytest.fixture
def second_place(database, models):
    place = models.Local(endereco='Sala dos servidores fictícia', descricao='Teste', responsavel='Equipe')
    database.session.add(place)
    database.session.commit()
    return place


def base(users, inventory):
    return f"/pessoas/{users['user'].id}/permissoes/{inventory['place'].id}"


@pytest.mark.parametrize('endpoint,method', [('person', 'get'), ('grant', 'put'), ('revoke', 'post'), ('local', 'get')])
@pytest.mark.parametrize('role,status', [(None, 401), ('user', 403), ('visitante', 403)])
def test_permissoes_administrativas_exigem_root(client, headers, users, inventory, visitor_factory, endpoint, method, role, status):
    from flask_jwt_extended import create_access_token
    visitor = visitor_factory()
    auth = {'Authorization': 'Bearer ' + create_access_token(identity=str(visitor.id))} if role == 'visitante' else headers[role] if role else {}
    paths = {'person': f"/pessoas/{users['user'].id}/permissoes", 'grant': base(users, inventory),
             'revoke': base(users, inventory) + '/revogar', 'local': f"/locais/{inventory['place'].id}/autorizacoes"}
    assert getattr(client, method)(paths[endpoint], headers=auth, json={'revogada': False}).status_code == status


def test_root_concede_atualiza_e_consulta_sem_alterar_pessoa_ou_expor_segredos(client, headers, users, inventory, models, password_hash):
    path = base(users, inventory)
    response = client.put(path, headers=headers['root'], json={'revogada': False})
    assert response.status_code == 201
    permission = response.json['permissao']
    assert permission['situacao'] == 'vigente' and permission['acesso_efetivo'] is True
    assert permission['inicio'] is permission['expiracao'] is None
    assert permission['pessoa']['tipo_user'] == 'users'
    assert permission['pessoa']['status_credencial'] == 'ativo'
    assert permission['local']['id'] == inventory['place'].id
    response = client.put(path, headers=headers['root'], json={'inicio': '2026-11-01T10:00:00-03:00'})
    assert response.status_code == 200
    assert response.json['permissao']['inicio'] == '2026-11-01T13:00:00Z'
    assert models.PermissaoAcesso.query.count() == 1
    result = client.get(f"/pessoas/{users['user'].id}/permissoes", headers=headers['root'])
    assert result.status_code == 200 and result.json['total'] == 1
    assert b'senha' not in result.data and b'email' not in result.data and password_hash.encode() not in result.data
    assert users['user'].status_conta is True and models.User.query.count() == 3


@pytest.mark.parametrize('body', [{}, {'inicio': 'sem-data'}, {'inicio': '2026-11-01T10:00:00'},
    {'inicio': 42}, {'expiracao': True}, {'inicio': 'x' * 65}, {'inicio': '9999-12-31T23:59:59-23:00'},
    {'inicio': '2026-11-02T00:00:00Z', 'expiracao': '2026-11-01T00:00:00Z'},
    {'inicio': '2026-11-01T00:00:00Z', 'expiracao': '2026-11-01T00:00:00Z'},
    {'revogada': 1}, {'revogada': 'false'}, {'revogada': None}, {'tipo_user': 'roots'},
    {'pessoa_id': 999}, {'local_id': 999}, [], None])
def test_permissao_invalida_nao_e_gravada(client, headers, users, inventory, models, body):
    response = client.put(base(users, inventory), headers=headers['root'], json=body)
    assert response.status_code == 400
    assert models.PermissaoAcesso.query.count() == 0


@pytest.mark.parametrize('body,content_type', [('{', 'application/json'), ('texto', 'text/plain'), ('null', 'application/json')])
def test_json_invalido_das_rotas_novas_preserva_400(client, headers, users, inventory, body, content_type):
    assert client.put(base(users, inventory), headers=headers['root'], data=body, content_type=content_type).status_code == 400


@pytest.mark.parametrize('person,place', [(99999, 1), (2, 99999)])
def test_ids_inexistentes_nao_criam_permissao(client, headers, models, inventory, person, place):
    assert client.put(f'/pessoas/{person}/permissoes/{place}', headers=headers['root'], json={'revogada': False}).status_code == 404
    assert models.PermissaoAcesso.query.count() == 0


@pytest.mark.parametrize('role', ['user', 'root'])
def test_nenhum_perfil_tem_acesso_universal_sem_permissao(client, users, inventory, database, models, role):
    if role == 'root':
        users[role].credencial_rfid = inventory['tags'][1].uid
        database.session.commit()
    response = client.post('/acessar_porta', json={'uid_solicitante': users[role].credencial_rfid, 'local': inventory['place'].id})
    assert response.status_code == 403
    assert response.json == {'message': 'Acesso negado', 'abrir': False}
    assert models.Registro_Acesso.query.one().status_tentativa == 'Negado'


def test_duas_pessoas_multiplas_salas_e_permissoes_diferentes(client, users, inventory, second_place, grant, database, models):
    other = users['inactive']; other.status_conta = True; other.credencial_rfid = inventory['tags'][1].uid
    database.session.commit()
    grant(users['user'], inventory['place'])
    grant(other, second_place)
    for person, place, status in [(users['user'], inventory['place'], 200), (users['user'], second_place, 403),
                                  (other, inventory['place'], 403), (other, second_place, 200)]:
        response = client.post('/acessar_porta', json={'uid_solicitante': person.credencial_rfid, 'local': place.id})
        assert response.status_code == status
        assert response.json['abrir'] is (status == 200)
        assert set(response.json) == {'abrir', 'message'}
    grant(users['user'], second_place)
    assert client.post('/acessar_porta', json={'uid_solicitante': users['user'].credencial_rfid, 'local': second_place.id}).status_code == 200
    assert models.Registro_Acesso.query.count() == 5


@pytest.mark.parametrize('kind', ['agendada', 'expirada', 'revogada', 'inativo', 'uid_ausente', 'uid_vazia', 'sem_pessoa', 'tag_inexistente'])
def test_condicoes_de_negacao_nunca_abrem_a_porta(client, users, inventory, models, database, grant, kind):
    point = now()
    values = {'inicio': point + timedelta(hours=1)} if kind == 'agendada' else {'expiracao': point - timedelta(hours=1)} if kind == 'expirada' else {'revogada': True} if kind == 'revogada' else {}
    grant(users['user'], inventory['place'], **values)
    body = {'uid_solicitante': users['user'].credencial_rfid, 'local': inventory['place'].id}
    if kind == 'inativo': users['user'].status_conta = False
    elif kind == 'uid_ausente': del body['uid_solicitante']
    elif kind == 'uid_vazia': body['uid_solicitante'] = ''
    elif kind == 'sem_pessoa': body['uid_solicitante'] = inventory['tags'][1].uid
    elif kind == 'tag_inexistente':
        users['user'].credencial_rfid = body['uid_solicitante'] = 'tag-ausente'
    database.session.commit()
    response = client.post('/acessar_porta', json=body)
    assert response.status_code == 403
    assert response.json['abrir'] is False
    assert models.Registro_Acesso.query.one().status_tentativa == 'Negado'


@pytest.mark.parametrize('offset,status', [(-1, 'agendada'), (0, 'vigente'), (3599, 'vigente'), (3600, 'expirada')])
def test_inicio_inclusivo_e_fim_exclusivo_da_permissao(grant, users, inventory, offset, status):
    point = datetime(2026, 11, 1, 10)
    permission = grant(users['user'], inventory['place'], inicio=point, expiracao=point + timedelta(hours=1))
    instant = point + timedelta(seconds=offset)
    assert permission.situacao(instant) == status
    assert users['user'].pode_acessar(inventory['place'].id, instant) is (status == 'vigente')


def test_visitante_usa_intersecao_de_validade_global_e_por_local(client, visitor_factory, inventory, second_place, grant, database, models):
    visitor = visitor_factory(locais=[inventory['place'], second_place])
    permission = database.session.get(models.PermissaoAcesso, (visitor.id, inventory['place'].id))
    permission.expiracao = now() - timedelta(seconds=1)
    database.session.commit()
    for place, status in [(inventory['place'], 403), (second_place, 200)]:
        assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': place.id}).status_code == status
    visitor.expiracao = now() - timedelta(seconds=1)
    visitor.inicio = now() - timedelta(days=1)
    database.session.commit()
    assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': second_place.id}).status_code == 403
    assert models.VisitanteAcesso.query.count() == 3


def test_revogar_sala_nao_exclui_pessoa_ou_outras_permissoes(client, headers, users, inventory, second_place, grant, models):
    grant(users['user'], inventory['place']); grant(users['user'], second_place)
    path = base(users, inventory)
    for _ in range(2):
        response = client.post(path + '/revogar', headers=headers['root'])
        assert response.status_code == 200
        assert response.json['permissao']['situacao'] == 'revogada'
        assert response.json['permissao']['acesso_efetivo'] is False
    assert models.User.query.count() == 3 and models.PermissaoAcesso.query.count() == 2
    assert client.post('/acessar_porta', json={'uid_solicitante': users['user'].credencial_rfid, 'local': second_place.id}).status_code == 200
    assert client.post('/acessar_porta', json={'uid_solicitante': users['user'].credencial_rfid, 'local': inventory['place'].id}).status_code == 403
    response = client.put(path, headers=headers['root'], json={'expiracao': iso(now() + timedelta(days=1))})
    assert response.json['permissao']['revogada'] is True
    assert client.put(path, headers=headers['root'], json={'revogada': False}).json['permissao']['acesso_efetivo'] is True


def test_lista_local_distingue_permissao_vigente_de_acesso_efetivo(client, headers, users, inventory, visitor_factory, grant):
    grant(users['user'], inventory['place'])
    grant(users['inactive'], inventory['place'])
    expired = visitor_factory(inicio=now() - timedelta(days=2), expiracao=now() - timedelta(days=1))
    active = visitor_factory()
    path = f"/locais/{inventory['place'].id}/autorizacoes"
    response = client.get(path, headers=headers['root'])
    assert response.status_code == 200
    assert {row['pessoa']['id'] for row in response.json['autorizacoes']} == {users['user'].id, active.id}
    response = client.get(path + '?situacao=vigente', headers=headers['root'])
    assert response.json['total'] == 4
    by_id = {row['pessoa']['id']: row for row in response.json['autorizacoes']}
    assert by_id[expired.id]['pessoa']['status_credencial'] == 'expirado'
    assert by_id[expired.id]['acesso_efetivo'] is False
    assert by_id[users['inactive'].id]['pessoa']['status_credencial'] == 'inativo'


@pytest.mark.parametrize('state,values', [('agendada', {'inicio': 'future'}), ('expirada', {'expiracao': 'past'}), ('revogada', {'revogada': True})])
def test_filtro_por_situacao_individual(client, headers, users, inventory, grant, state, values):
    kwargs = {key: now() + timedelta(hours=1) if value == 'future' else now() - timedelta(hours=1) if value == 'past' else value for key, value in values.items()}
    grant(users['user'], inventory['place'], **kwargs)
    response = client.get(f"/locais/{inventory['place'].id}/autorizacoes?situacao={state}", headers=headers['root'])
    assert response.status_code == 200 and response.json['total'] == 1
    assert response.json['autorizacoes'][0]['situacao'] == state
    assert response.json['autorizacoes'][0]['acesso_efetivo'] is False


@pytest.mark.parametrize('query', ['pagina=0', 'limite=0', 'limite=101', 'pagina=abc', 'pagina=9999999999999999999999999',
    'pagina=9223372036854775807&limite=100', 'situacao=invalida', 'situacao=', 'nome=x', 'pagina=1&pagina=2'])
def test_filtros_administrativos_invalidos_retornam_400(client, headers, inventory, query):
    assert client.get(f"/locais/{inventory['place'].id}/autorizacoes?{query}", headers=headers['root']).status_code == 400


def test_paginacao_pessoa_e_local_preserva_total(client, headers, users, inventory, second_place, grant):
    grant(users['user'], inventory['place']); grant(users['user'], second_place)
    response = client.get(f"/pessoas/{users['user'].id}/permissoes?pagina=2&limite=1", headers=headers['root'])
    assert response.status_code == 200 and response.json['total'] == 2
    assert response.json['permissoes'][0]['local']['id'] == second_place.id
    response = client.get(f"/pessoas/{users['user'].id}/permissoes?pagina=3&limite=1", headers=headers['root'])
    assert response.json['total'] == 2 and response.json['permissoes'] == []


def test_edicao_visitante_preserva_metadados_e_nao_reativa_sala_revogada(client, headers, visitor_factory, inventory, second_place, models, database):
    visitor = visitor_factory(locais=[inventory['place'], second_place])
    first = database.session.get(models.PermissaoAcesso, (visitor.id, inventory['place'].id))
    other = database.session.get(models.PermissaoAcesso, (visitor.id, second_place.id))
    first.inicio = now() - timedelta(hours=1); first.expiracao = now() + timedelta(hours=1)
    first.revogada = True
    old_period = (first.inicio, first.expiracao)
    database.session.commit()
    path = f'/visitantes/{visitor.id}'
    assert client.put(path, headers=headers['root'], json={'expiracao': iso(now() + timedelta(days=2))}).status_code == 200
    assert first.revogada is True and (first.inicio, first.expiracao) == old_period
    assert client.put(path, headers=headers['root'], json={'locais': [inventory['place'].id]}).status_code == 200
    assert first.revogada is False and (first.inicio, first.expiracao) == old_period
    assert other.revogada is True
    assert database.session.execute(models.visitante_locais.select()).all() == []


def test_legado_nao_e_fallback_que_reautoriza_permissa_revogada(client, visitor_factory, inventory, models, database):
    visitor = visitor_factory()
    database.session.execute(models.visitante_locais.insert().values(visitante_id=visitor.id, local_id=inventory['place'].id))
    permission = database.session.get(models.PermissaoAcesso, (visitor.id, inventory['place'].id))
    permission.revogada = True
    database.session.commit()
    assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': inventory['place'].id}).status_code == 403


def test_troca_de_tag_nao_transfere_permissoes_para_novo_dono(client, headers, users, inventory, second_place, grant, database):
    grant(users['user'], inventory['place'])
    old_uid = users['user'].credencial_rfid
    assert client.post('/atribuir_rfid_usuario', headers=headers['root'], json={'id_usuario': users['user'].id, 'uid_usuario': inventory['tags'][1].uid}).status_code == 200
    other = users['inactive']; other.status_conta = True; other.credencial_rfid = old_uid
    database.session.commit()
    assert client.post('/acessar_porta', json={'uid_solicitante': other.credencial_rfid, 'local': inventory['place'].id}).status_code == 403


@pytest.mark.parametrize('error,status', [(OperationalError('SQL privado', {}, Exception('erro privado')), 500),
                                        (IntegrityError('SQL privado', {}, Exception('conflito')), 409)])
def test_falha_na_gravacao_reverte_a_permissao_sem_expor_sql(client, headers, users, inventory, models, error, status):
    with patch('app.routes.control_door.db.session.commit', side_effect=error):
        response = client.put(base(users, inventory), headers=headers['root'], json={'revogada': False})
    assert response.status_code == status
    assert 'SQL privado' not in response.text and 'erro privado' not in response.text
    assert models.PermissaoAcesso.query.count() == 0


def test_falha_na_consulta_da_porta_nao_abre_por_padrao(client, inventory, users):
    with patch('src.database.models.User.pode_acessar', side_effect=OperationalError('SQL', {}, Exception('offline'))):
        response = client.post('/acessar_porta', json={'uid_solicitante': users['user'].credencial_rfid, 'local': inventory['place'].id})
    assert response.status_code == 500
    assert response.json == {'message': 'Erro interno no servidor ao registrar acesso.'}
    assert response.json.get('abrir') is not True


def test_mac_permanece_no_fluxo_rfid_e_nao_vira_campo_obrigatorio_na_porta(client, users, inventory, grant):
    grant(users['user'], inventory['place'])
    for mac, status in [(inventory['device'].mac, 200), ('FF:FF:FF:FF:FF:FF', 403)]:
        assert client.post('/cadastrar_rfid', json={'uid': users['user'].credencial_rfid, 'date': '2026-11-18', 'mac_adress': mac}).status_code == status
    response = client.post('/acessar_porta', json={'uid_solicitante': users['user'].credencial_rfid, 'local': inventory['place'].id})
    assert response.status_code == 200 and response.json['abrir'] is True


def test_uid_numerica_e_credencial_herdada_continuam_consultaveis(client, headers, users, inventory, models, database, grant):
    database.session.add(models.RFID(uid='00001234', date='2026-01-01'))
    users['user'].credencial_rfid = '00001234'
    database.session.commit()
    grant(users['user'], inventory['place'])
    assert users['user'].credencial_rfid == 1234
    response = client.get(f"/locais/{inventory['place'].id}/autorizacoes", headers=headers['root'])
    assert response.status_code == 200 and response.json['total'] == 1
    assert response.json['autorizacoes'][0]['pessoa']['status_credencial'] == 'ativo'
    assert client.post('/acessar_porta', json={'uid_solicitante': '00001234', 'local': inventory['place'].id}).status_code == 200


def test_validade_da_permissao_e_reavaliada_em_cada_tentativa(client, users, inventory, grant, models, monkeypatch):
    point = now()
    grant(users['user'], inventory['place'], inicio=point, expiracao=point + timedelta(hours=1))
    clock = [point]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return clock[0].replace(tzinfo=timezone.utc) if tz else clock[0]
    monkeypatch.setattr(models, 'datetime', Clock)
    body = {'uid_solicitante': users['user'].credencial_rfid, 'local': inventory['place'].id, 'date': '1900-01-01'}
    assert client.post('/acessar_porta', json=body).status_code == 200
    clock[0] = point + timedelta(hours=1)
    assert client.post('/acessar_porta', json=body).status_code == 403


@pytest.mark.parametrize('endpoint', ['person', 'local', 'revoke'])
def test_falha_sql_administrativa_e_tratada_sem_detalhes_internos(client, headers, users, inventory, endpoint):
    paths = {'person': (f"/pessoas/{users['user'].id}/permissoes", 'get'),
             'local': (f"/locais/{inventory['place'].id}/autorizacoes", 'get'),
             'revoke': (base(users, inventory) + '/revogar', 'post')}
    path, method = paths[endpoint]
    # A verificação Root usa a mesma sessão; uma falha nela também deve fechar o acesso.
    with patch('app.routes.control_door.db.session.get', side_effect=OperationalError('sql-interno', {}, Exception('privado'))):
        response = getattr(client, method)(path, headers=headers['root'])
    assert response.status_code == 500
    assert response.json == {'message': 'Não foi possível processar as permissões de acesso.'}


def test_default_por_local_exclui_credenciais_ausentes_e_preserva_consulta_todas(client, headers, users, inventory, grant, database):
    grant(users['root'], inventory['place'])
    grant(users['user'], inventory['place'])
    users['user'].credencial_rfid = 'tag-inexistente'
    database.session.commit()
    path = f"/locais/{inventory['place'].id}/autorizacoes"
    assert client.get(path, headers=headers['root']).json['total'] == 0
    result = client.get(path + '?situacao=todas', headers=headers['root']).json
    assert result['total'] == 2
    assert all(not row['acesso_efetivo'] for row in result['autorizacoes'])
    assert all(row['pessoa']['status_credencial'] == 'sem_credencial' for row in result['autorizacoes'])


def test_revogacao_ou_edicao_falha_nao_perde_autorizacao_antes_valida(client, headers, users, inventory, grant, models):
    permission = grant(users['user'], inventory['place'])
    with patch('app.routes.control_door.db.session.commit', side_effect=OperationalError('sql', {}, Exception('offline'))):
        response = client.post(base(users, inventory) + '/revogar', headers=headers['root'])
    assert response.status_code == 500
    assert permission.revogada is False
    assert models.PermissaoAcesso.query.count() == 1


def test_tag_ja_vinculada_continua_rejeitada_pela_associacao_original(client, headers, users, inventory, visitor_factory):
    visitor = visitor_factory()
    response = client.post('/atribuir_rfid_usuario', headers=headers['root'], json={
        'id_usuario': users['user'].id, 'uid_usuario': visitor.credencial_rfid})
    assert response.status_code == 409
    assert users['user'].credencial_rfid == inventory['tags'][2].uid


def test_paginacao_de_autorizados_por_local_e_estado_individual(client, headers, users, inventory, visitor_factory, grant):
    grant(users['user'], inventory['place'])
    visitor = visitor_factory()
    response = client.get(f"/locais/{inventory['place'].id}/autorizacoes?pagina=2&limite=1", headers=headers['root'])
    assert response.status_code == 200 and response.json['total'] == 2
    assert response.json['autorizacoes'][0]['pessoa']['id'] == visitor.id
