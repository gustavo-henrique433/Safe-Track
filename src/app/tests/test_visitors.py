from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.security import check_password_hash


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


@pytest.fixture
def payload(inventory):
    now = utcnow()
    return {'nome': 'Visitante da API', 'email': 'visitor-api@example.test', 'senha': 'Senha-ficticia-123!',
            'credencial_rfid': inventory['tags'][1].uid, 'inicio': iso(now - timedelta(hours=1)),
            'expiracao': iso(now + timedelta(hours=1)), 'locais': [inventory['place'].id]}


@pytest.fixture
def visitor_headers(visitor_factory):
    from flask_jwt_extended import create_access_token
    visitor = visitor_factory()
    return {'Authorization': 'Bearer ' + create_access_token(identity=str(visitor.id))}


@pytest.mark.parametrize('method,path', [('post', '/visitantes'), ('get', '/visitantes'),
    ('get', '/visitantes/999'), ('put', '/visitantes/999'), ('post', '/visitantes/999/revogar'),
    ('get', '/visitantes/999/acessos')])
@pytest.mark.parametrize('role,status', [(None, 401), ('user', 403), ('visitante', 403)])
def test_administracao_de_visitantes_exige_root(client, headers, visitor_headers, method, path, role, status):
    authorization = visitor_headers if role == 'visitante' else headers[role] if role else {}
    response = getattr(client, method)(path, headers=authorization, json={})
    assert response.status_code == status


@pytest.mark.parametrize('method,path', [('post', '/registrar_root'), ('post', '/atribuir_rfid_usuario'),
    ('get', '/visualizar_todos_usuarios'), ('post', '/cadastrar_objeto'), ('put', '/recadastrar_objeto'),
    ('delete', '/excluir_objeto'), ('post', '/cadastrar_local'), ('put', '/editar_local'), ('delete', '/excluir_rfid')])
def test_visitante_nao_recebe_permissoes_root_existentes(client, visitor_headers, method, path):
    assert getattr(client, method)(path, headers=visitor_headers, json={}).status_code == 403


def test_cadastro_visitante_reutiliza_user_sem_expor_senha(client, headers, payload, models):
    response = client.post('/visitantes', headers=headers['root'], json=payload)
    assert response.status_code == 201
    result = response.json['visitante']
    assert result['tipo_user'] == 'visitante'
    assert result['status'] == 'ativo'
    assert result['credencial_rfid'] == payload['credencial_rfid']
    assert result['locais'][0]['id'] == payload['locais'][0]
    assert not {'senha', 'senha_root'} & set(result)
    visitor = models.Visitante.query.one()
    assert not isinstance(visitor, models.Root)
    assert check_password_hash(visitor.senha, payload['senha'])
    assert models.User.query.filter_by(id=visitor.id).one().tipo_user == 'visitante'


@pytest.mark.parametrize('missing', ['nome', 'email', 'senha', 'credencial_rfid', 'inicio', 'expiracao', 'locais'])
def test_cadastro_visitante_rejeita_campos_ausentes(client, headers, payload, models, missing):
    del payload[missing]
    assert client.post('/visitantes', headers=headers['root'], json=payload).status_code == 400
    assert models.Visitante.query.count() == 0
    assert models.User.query.count() == 3


@pytest.mark.parametrize('changes,status', [
    ({'nome': ''}, 400), ({'nome': ' '}, 400), ({'nome': 'x' * 101}, 400),
    ({'email': 'sem-arroba'}, 400), ({'email': 'x' * 101}, 400), ({'senha': None}, 400),
    ({'senha': True}, 400), ({'senha': 'x' * 257}, 400),
    ({'credencial_rfid': 1234}, 400), ({'credencial_rfid': 'x' * 129}, 400),
    ({'credencial_rfid': 'nao-cadastrada'}, 404), ({'credencial_rfid': 'a1b2c3d4'}, 409),
    ({'credencial_rfid': 'c3d4e5f6'}, 409), ({'email': 'root@example.test'}, 409),
    ({'inicio': '2026-01-01T10:00:00'}, 400), ({'inicio': 'invalido'}, 400),
    ({'inicio': None}, 400), ({'inicio': '9999-12-31T23:59:59-23:00'}, 400),
    ({'locais': []}, 400), ({'locais': None}, 400), ({'locais': '1'}, 400),
    ({'locais': [True]}, 400), ({'locais': [0]}, 400), ({'locais': ['1']}, 400),
    ({'locais': [1, 1]}, 400), ({'locais': [999]}, 404), ({'locais': list(range(1, 102))}, 400),
    ({'tipo_user': 'roots'}, 400), ({'status_conta': True}, 400),
])
def test_cadastro_visitante_valida_novos_campos_sem_persistencia_parcial(client, headers, payload, models, changes, status):
    payload.update(changes)
    response = client.post('/visitantes', headers=headers['root'], json=payload)
    assert response.status_code == status
    assert models.Visitante.query.count() == 0
    assert models.User.query.count() == 3


@pytest.mark.parametrize('kind', ['igual', 'invertido'])
def test_periodo_visitante_exige_inicio_anterior_a_expiracao(client, headers, payload, kind):
    payload['inicio'] = payload['expiracao'] if kind == 'igual' else iso(utcnow() + timedelta(days=1))
    assert client.post('/visitantes', headers=headers['root'], json=payload).status_code == 400


def test_datas_visitante_com_offset_sao_armazenadas_em_utc(client, headers, payload, models):
    payload.update(inicio='2026-11-01T10:00:00-03:00', expiracao='2026-11-01T12:00:00-03:00')
    response = client.post('/visitantes', headers=headers['root'], json=payload)
    assert response.status_code == 201
    visitor = models.Visitante.query.one()
    assert visitor.inicio == datetime(2026, 11, 1, 13)
    assert visitor.expiracao == datetime(2026, 11, 1, 15)
    assert response.json['visitante']['inicio'] == '2026-11-01T13:00:00Z'


@pytest.mark.parametrize('state', ['ativo', 'agendado', 'expirado', 'revogado'])
def test_filtro_administrativo_por_situacao(client, headers, visitor_factory, state):
    now = utcnow()
    records = {
        'ativo': visitor_factory(),
        'agendado': visitor_factory(inicio=now + timedelta(hours=1), expiracao=now + timedelta(hours=2)),
        'expirado': visitor_factory(inicio=now - timedelta(hours=2), expiracao=now - timedelta(hours=1)),
        'revogado': visitor_factory(status_conta=False),
    }
    response = client.get('/visitantes?status=' + state, headers=headers['root'])
    assert response.status_code == 200
    assert response.json['total'] == 1
    assert response.json['visitantes'][0]['id'] == records[state].id
    assert response.json['visitantes'][0]['status'] == state


def test_paginacao_visitantes_nao_expoe_hashes(client, headers, visitor_factory):
    visitors = [visitor_factory() for _ in range(3)]
    response = client.get('/visitantes?pagina=2&limite=2', headers=headers['root'])
    assert response.status_code == 200
    assert response.json['total'] == 3
    assert [row['id'] for row in response.json['visitantes']] == [visitors[2].id]
    assert 'senha' not in response.text


@pytest.mark.parametrize('query', ['pagina=0', 'pagina=abc', 'limite=0', 'limite=101', 'limite=1.5', 'status=invalido'])
def test_listagem_visitantes_rejeita_filtros_invalidos(client, headers, query):
    assert client.get('/visitantes?' + query, headers=headers['root']).status_code == 400


def test_consulta_individual_nao_confunde_user_ou_root_com_visitante(client, headers, users, visitor_factory):
    visitor = visitor_factory()
    response = client.get(f'/visitantes/{visitor.id}', headers=headers['root'])
    assert response.status_code == 200
    assert response.json['visitante']['id'] == visitor.id
    for user in users.values():
        assert client.get(f'/visitantes/{user.id}', headers=headers['root']).status_code == 404


@pytest.mark.parametrize('method,suffix', [('get', ''), ('put', ''), ('post', '/revogar'), ('get', '/acessos')])
def test_visitante_inexistente_retorna_404(client, headers, method, suffix):
    assert getattr(client, method)('/visitantes/999' + suffix, headers=headers['root'], json={}).status_code == 404


def test_edicao_periodo_local_e_uid_preserva_perfil(client, headers, visitor_factory, inventory, models, database):
    visitor = visitor_factory()
    new_place = models.Local(endereco='Outra sala', descricao='Fictícia', responsavel='Pessoa fictícia')
    database.session.add(new_place)
    database.session.commit()
    response = client.put(f'/visitantes/{visitor.id}', headers=headers['root'], json={
        'inicio': iso(utcnow() - timedelta(minutes=30)), 'expiracao': iso(utcnow() + timedelta(hours=3)),
        'credencial_rfid': inventory['tags'][1].uid, 'locais': [new_place.id]})
    assert response.status_code == 200
    assert response.json['visitante']['tipo_user'] == 'visitante'
    assert visitor.credencial_rfid == inventory['tags'][1].uid
    assert [place.id for place in visitor.locais] == [new_place.id]


@pytest.mark.parametrize('changes,status', [({}, 400), ({'tipo_user': 'roots'}, 400),
    ({'status_conta': True}, 400), ({'locais': [999], 'credencial_rfid': 'b2c3d4e5'}, 404),
    ({'credencial_rfid': 'c3d4e5f6'}, 409), ({'inicio': 'sem-fuso'}, 400)])
def test_edicao_invalida_nao_altera_visitante(client, headers, visitor_factory, changes, status):
    visitor = visitor_factory()
    before = (visitor.credencial_rfid, visitor.inicio, visitor.expiracao, [place.id for place in visitor.locais])
    response = client.put(f'/visitantes/{visitor.id}', headers=headers['root'], json=changes)
    assert response.status_code == status
    assert (visitor.credencial_rfid, visitor.inicio, visitor.expiracao, [place.id for place in visitor.locais]) == before


def test_revogacao_idempotente_nao_exclui_cadastro_ou_historico(client, headers, visitor_factory, models, inventory):
    visitor = visitor_factory()
    assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': inventory['place'].id}).status_code == 200
    for _ in range(2):
        response = client.post(f'/visitantes/{visitor.id}/revogar', headers=headers['root'])
        assert response.status_code == 200
        assert response.json['visitante']['status'] == 'revogado'
    assert models.Visitante.query.count() == 1
    assert models.VisitanteAcesso.query.count() == 1
    assert models.Registro_Acesso.query.count() == 1
    assert visitor.status_conta is False


@pytest.mark.parametrize('state,other_local,status', [('ativo', False, 200), ('agendado', False, 403),
    ('expirado', False, 403), ('revogado', False, 403), ('ativo', True, 403)])
def test_acesso_visitante_preserva_payload_respostas_e_registro(client, visitor_factory, database, models, inventory, state, other_local, status):
    now = utcnow()
    fields = {}
    if state == 'agendado':
        fields.update(inicio=now + timedelta(hours=1), expiracao=now + timedelta(hours=2))
    elif state == 'expirado':
        fields.update(inicio=now - timedelta(hours=2), expiracao=now - timedelta(hours=1))
    elif state == 'revogado':
        fields['status_conta'] = False
    visitor = visitor_factory(**fields)
    place = inventory['place']
    if other_local:
        place = models.Local(endereco='Sala não autorizada', descricao='Teste', responsavel='Pessoa')
        database.session.add(place)
        database.session.commit()
    response = client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': place.id})
    assert response.status_code == status
    assert response.json['abrir'] is (status == 200)
    assert set(response.json) == {'message', 'abrir'}
    event = models.Registro_Acesso.query.one()
    link = models.VisitanteAcesso.query.one()
    assert event.status_tentativa == ('Liberado' if status == 200 else 'Negado')
    assert event.id_rfid == visitor.credencial_rfid
    assert link.registro_id == event.id
    assert link.visitante_id == visitor.id


@pytest.mark.parametrize('offset,allowed', [(-1, False), (0, True), (3599, True), (3600, False)])
def test_limites_temporais_inicio_inclusivo_expiracao_exclusiva(visitor_factory, inventory, offset, allowed):
    start = datetime(2026, 11, 17, 10)
    visitor = visitor_factory(inicio=start, expiracao=start + timedelta(hours=1))
    assert visitor.pode_acessar(inventory['place'].id, start + timedelta(seconds=offset)) is allowed


def test_expiracao_e_reavaliada_sem_alterar_banco_ou_scheduler(client, visitor_factory, inventory, models, monkeypatch):
    now = utcnow()
    visitor = visitor_factory(inicio=now - timedelta(minutes=1), expiracao=now + timedelta(minutes=1))
    current = [now]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current[0].replace(tzinfo=timezone.utc) if tz else current[0]

    monkeypatch.setattr(models, 'datetime', Clock)
    body = {'uid_solicitante': visitor.credencial_rfid, 'local': inventory['place'].id}
    assert client.post('/acessar_porta', json=body).status_code == 200
    current[0] = now + timedelta(minutes=2)
    assert client.post('/acessar_porta', json=body).status_code == 403
    assert [row.status_tentativa for row in models.Registro_Acesso.query.order_by(models.Registro_Acesso.id)] == ['Liberado', 'Negado']
    assert models.VisitanteAcesso.query.count() == 2


def test_historico_permanece_com_visitante_apos_reassociacao_pela_rota_original(client, headers, visitor_factory, inventory, models):
    first = visitor_factory()
    uid = first.credencial_rfid
    body = {'uid_solicitante': uid, 'local': inventory['place'].id}
    assert client.post('/acessar_porta', json=body).status_code == 200
    assert client.post('/atribuir_rfid_usuario', headers=headers['root'], json={
        'id_usuario': first.id, 'uid_usuario': inventory['tags'][1].uid}).status_code == 200
    second = visitor_factory(credencial_rfid=uid)
    assert client.post('/acessar_porta', json=body).status_code == 200
    first_history = client.get(f'/visitantes/{first.id}/acessos', headers=headers['root']).json
    second_history = client.get(f'/visitantes/{second.id}/acessos', headers=headers['root']).json
    assert first_history['total'] == second_history['total'] == 1
    assert first_history['acessos'][0]['id_rfid'] == second_history['acessos'][0]['id_rfid'] == uid
    assert first_history['acessos'][0]['id'] != second_history['acessos'][0]['id']
    assert models.VisitanteAcesso.query.count() == 2


def test_historico_administrativo_filtra_sem_inferir_eventos_antigos(client, headers, visitor_factory, inventory, models, database):
    visitor = visitor_factory()
    first_time = datetime(2026, 11, 1, 10)
    for index, result in enumerate(('Liberado', 'Negado')):
        record = models.Registro_Acesso(id_rfid=visitor.credencial_rfid, id_local=inventory['place'].id,
                                        horario=first_time + timedelta(hours=index), status_tentativa=result)
        database.session.add(record)
        database.session.flush()
        database.session.add(models.VisitanteAcesso(registro_id=record.id, visitante_id=visitor.id))
    database.session.add(models.Registro_Acesso(id_rfid=visitor.credencial_rfid, id_local=inventory['place'].id,
                                               horario=first_time, status_tentativa='Liberado'))
    database.session.commit()
    base = f'/visitantes/{visitor.id}/acessos'
    assert client.get(base, headers=headers['root']).json['total'] == 2
    response = client.get(base + '?resultado=Negado&inicio=2026-11-01T10:30:00Z&fim=2026-11-01T12:00:00Z&local=1', headers=headers['root'])
    assert response.status_code == 200
    assert response.json['total'] == 1
    assert response.json['acessos'][0]['status_tentativa'] == 'Negado'
    assert response.json['acessos'][0]['horario'].endswith('Z')
    response = client.get(base + '?pagina=2&limite=1', headers=headers['root'])
    assert response.json['total'] == 2 and len(response.json['acessos']) == 1


@pytest.mark.parametrize('query', ['resultado=invalido', 'local=0', 'local=abc', 'inicio=sem-fuso',
    'inicio=2026-11-01T12:00:00Z&fim=2026-11-01T10:00:00Z', 'pagina=0'])
def test_filtros_invalidos_do_historico(client, headers, visitor_factory, query):
    visitor = visitor_factory()
    assert client.get(f'/visitantes/{visitor.id}/acessos?' + query, headers=headers['root']).status_code == 400


def test_visitante_usa_login_jwt_original_sem_promocao(client, visitor_factory):
    visitor = visitor_factory()
    response = client.post('/login', json={'email': visitor.email, 'senha': 'Senha-ficticia-123!'})
    assert response.status_code == 200
    assert response.json['user_type'] == 'visitante'
    assert response.json['access_token']


def test_cadastro_publico_original_nao_e_fechado_pelo_novo_perfil(client, visitor_headers, models):
    """Limitação aprovada: a rota pública continua pública, mesmo com JWT visitante."""
    response = client.post('/registrar_usuario', headers=visitor_headers, json={
        'nome': 'Conta pública fictícia', 'email': 'public@example.test', 'senha': 'Ficticia-123!'})
    assert response.status_code == 201
    assert models.User.query.filter_by(email='public@example.test').one().tipo_user == 'users'


@pytest.mark.parametrize('error,status', [(OperationalError('SQL fictício', {}, Exception('offline')), 500),
                                        (IntegrityError('SQL fictício', {}, Exception('duplicado')), 409)], ids=['offline', 'conflito'])
def test_falha_no_cadastro_visitante_reverte_todas_as_inclusoes(client, headers, payload, models, database, error, status):
    with patch.object(database.session, 'commit', side_effect=error):
        response = client.post('/visitantes', headers=headers['root'], json=payload)
    assert response.status_code == status
    assert 'SQL fictício' not in response.text
    assert models.User.query.count() == 3
    assert models.Visitante.query.count() == 0
    assert database.session.execute(models.visitante_locais.select()).all() == []


@pytest.mark.parametrize('operation', ['editar', 'revogar'])
def test_falha_de_gravacao_preserva_autorizacao_existente(client, headers, visitor_factory, database, operation):
    visitor = visitor_factory()
    previous_end = visitor.expiracao
    with patch.object(database.session, 'commit', side_effect=OperationalError('SQL fictício', {}, Exception('offline'))):
        if operation == 'editar':
            response = client.put(f'/visitantes/{visitor.id}', headers=headers['root'], json={'expiracao': iso(utcnow() + timedelta(days=1))})
        else:
            response = client.post(f'/visitantes/{visitor.id}/revogar', headers=headers['root'])
    assert response.status_code == 500
    assert visitor.status_conta is True
    assert visitor.expiracao == previous_end


def test_falha_no_vinculo_do_historico_reverte_registro_e_nao_abre_porta(client, visitor_factory, inventory, models):
    visitor = visitor_factory()

    def fail(mapper, connection, target):
        raise OperationalError('SQL fictício', {}, Exception('offline'))

    event.listen(models.VisitanteAcesso, 'before_insert', fail)
    try:
        response = client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': inventory['place'].id})
    finally:
        event.remove(models.VisitanteAcesso, 'before_insert', fail)
    assert response.status_code == 500
    assert response.json.get('abrir') is not True
    assert models.Registro_Acesso.query.count() == 0
    assert models.VisitanteAcesso.query.count() == 0


@pytest.mark.parametrize('body,content_type', [('[]', 'application/json'), ('null', 'application/json'),
    ('{', 'application/json'), ('texto', 'text/plain')])
def test_json_invalido_e_tratado_apenas_nas_rotas_novas(client, headers, body, content_type):
    response = client.post('/visitantes', headers=headers['root'], data=body, content_type=content_type)
    assert response.status_code == 400


def test_visitante_pode_ter_varios_locais_e_edicao_tem_efeito_no_proximo_acesso(client, headers, visitor_factory, inventory, database, models):
    other = models.Local(endereco='Segunda sala', descricao='Teste', responsavel='Pessoa')
    database.session.add(other)
    database.session.commit()
    visitor = visitor_factory(locais=[inventory['place'], other])
    for place in (inventory['place'], other):
        assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': place.id}).status_code == 200
    assert client.put(f'/visitantes/{visitor.id}', headers=headers['root'], json={'locais': [other.id]}).status_code == 200
    assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': inventory['place'].id}).status_code == 403
    assert client.post('/acessar_porta', json={'uid_solicitante': visitor.credencial_rfid, 'local': other.id}).status_code == 200
    assert models.VisitanteAcesso.query.count() == 4


@pytest.mark.parametrize('role', ['root', 'user'])
def test_permissao_individual_de_comum_ou_root_independe_dos_locais_de_outro_visitante(client, visitor_factory, users, inventory, database, models, role):
    visitor_factory()
    other = models.Local(endereco='Sala fora da visita', descricao='Teste', responsavel='Pessoa')
    database.session.add(other)
    database.session.flush()
    database.session.add(models.PermissaoAcesso(pessoa_id=users[role].id, local_id=other.id))
    if role == 'root':
        users['root'].credencial_rfid = inventory['tags'][1].uid
    database.session.commit()
    response = client.post('/acessar_porta', json={'uid_solicitante': users[role].credencial_rfid, 'local': other.id})
    assert response.status_code == 200
    assert response.json == {'message': f'Abrindo porta para {users[role].nome}', 'abrir': True}
    assert models.VisitanteAcesso.query.count() == 0


@pytest.mark.parametrize('expired', [False, True])
def test_leitura_rfid_de_visitante_mantem_mac_e_resposta_originais(client, visitor_factory, inventory, expired):
    from app.routes import rfid
    fields = {'inicio': utcnow() - timedelta(hours=2), 'expiracao': utcnow() - timedelta(hours=1)} if expired else {}
    visitor = visitor_factory(**fields)
    with patch.object(rfid, 'emit') as emit:
        response = client.post('/cadastrar_rfid', json={'uid': visitor.credencial_rfid,
            'date': '2026-01-01', 'mac_adress': inventory['device'].mac})
    assert response.status_code == 200
    assert response.json == {'message': 'Leitura processada !!'}
    assert emit.call_args.args[1]['status'] == 'usuario'
    assert emit.call_args.kwargs == {'namespace': '/', 'broadcast': True}


def test_uid_numerica_herdada_permanece_aceita_sem_alterar_tipo_da_coluna(client, headers, payload, models, database, inventory):
    database.session.add(models.RFID(uid='00001234', date='2026-01-01'))
    database.session.commit()
    payload['credencial_rfid'] = '00001234'
    response = client.post('/visitantes', headers=headers['root'], json=payload)
    assert response.status_code == 201
    visitor = models.Visitante.query.one()
    # Afinidade INTEGER original, sem coluna textual extra ou normalização de dados.
    assert visitor.credencial_rfid == 1234
    assert client.put(f'/visitantes/{visitor.id}', headers=headers['root'], json={'expiracao': iso(utcnow() + timedelta(days=1))}).status_code == 200
    response = client.post('/acessar_porta', json={'uid_solicitante': '00001234', 'local': inventory['place'].id})
    assert response.status_code == 200
    assert models.Registro_Acesso.query.one().id_rfid == '00001234'
