import io
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError


def object_payload(**changes):
    payload = {'nome': 'Objeto novo fictício', 'descricao': 'Descrição de teste',
               'especificacoes': 'Especificações fictícias', 'local': '1', 'uid_recebido': 'b2c3d4e5',
               'imagem': (io.BytesIO(b'imagem-ficticia'), 'foto teste.png')}
    payload.update(changes)
    return payload


def test_cadastro_objeto_e_imagem_no_diretorio_temporario(client, headers, inventory, models, tmp_path):
    response = client.post('/cadastrar_objeto', headers=headers['root'], data=object_payload())
    assert response.status_code == 201
    item = models.Object.query.filter_by(id_rfid='b2c3d4e5').one()
    assert item.id_lugar == inventory['place'].id
    assert item.url_imagem == 'static/uploads/foto_teste.png'
    assert (tmp_path / item.url_imagem).read_bytes() == b'imagem-ficticia'
    image = client.get('/static/uploads/foto_teste.png')
    assert image.status_code == 200
    assert image.data == b'imagem-ficticia'


@pytest.mark.parametrize('field', ['nome', 'descricao', 'local', 'uid_recebido', 'imagem'])
def test_cadastro_objeto_rejeita_campos_obrigatorios_ausentes(client, headers, inventory, models, field):
    payload = object_payload()
    del payload[field]
    response = client.post('/cadastrar_objeto', headers=headers['root'], data=payload)
    assert response.status_code == 400
    assert models.Object.query.count() == 1


@pytest.mark.parametrize('changes', [{'uid_recebido': 'inexistente'}, {'local': '999'}])
def test_cadastro_objeto_rejeita_referencias_inexistentes(client, headers, inventory, models, changes):
    response = client.post('/cadastrar_objeto', headers=headers['root'], data=object_payload(**changes))
    assert response.status_code == 404
    assert models.Object.query.count() == 1


def test_nome_do_upload_e_sanitizado(client, headers, inventory, tmp_path):
    response = client.post('/cadastrar_objeto', headers=headers['root'], data=object_payload(
        imagem=(io.BytesIO(b'ficticio'), '../../fora.png')))
    assert response.status_code == 201
    assert (tmp_path / 'static/uploads/fora.png').read_bytes() == b'ficticio'
    assert not (tmp_path / 'fora.png').exists()


@pytest.mark.parametrize('payload,status', [({}, 400), ({'id_objeto': 999, 'nova_uid': 'b2c3d4e5'}, 404),
    ({'id_objeto': 1, 'nova_uid': 'inexistente'}, 404), ({'id_objeto': 1, 'nova_uid': 'a1b2c3d4'}, 400)])
def test_recadastro_objeto_rejeita_entradas_e_conflitos(client, headers, inventory, payload, status):
    response = client.put('/recadastrar_objeto', headers=headers['root'], json=payload)
    assert response.status_code == status
    assert inventory['item'].id_rfid == 'a1b2c3d4'


def test_recadastro_objeto_atualiza_uid(client, headers, inventory, models):
    response = client.put('/recadastrar_objeto', headers=headers['root'], json={
        'id_objeto': inventory['item'].id, 'nova_uid': inventory['tags'][1].uid})
    assert response.status_code == 200
    assert models.Object.query.one().id_rfid == inventory['tags'][1].uid


@pytest.mark.parametrize('payload,status,remaining', [({}, 400, 1), ({'objeto_excluir': 999}, 404, 1),
                                                      ({'objeto_excluir': 1}, 200, 0)])
def test_exclusao_objeto(client, headers, inventory, models, payload, status, remaining):
    response = client.delete('/excluir_objeto', headers=headers['root'], json=payload)
    assert response.status_code == status
    assert models.Object.query.count() == remaining


@pytest.mark.parametrize('role', ['root', 'user'])
def test_inventario_disponivel_aos_perfis_existentes(client, headers, inventory, role):
    response = client.get('/vizualizar_todos_objetos', headers=headers[role])
    assert response.status_code == 200
    assert response.json['total_objetos'] == 1
    assert response.json['objetos'][0]['id_rfid'] == inventory['tags'][0].uid


def test_inventario_exige_jwt(client):
    assert client.get('/vizualizar_todos_objetos').status_code == 401


@pytest.mark.parametrize('path,status,action,result', [
    ('/buscar_objeto_id/1', 200, 'buscar_objeto_id', 'sucesso'),
    ('/buscar_objeto_id/999', 404, 'buscar_objeto_id', 'falha'),
    ('/buscar_objeto_uid/a1b2c3d4', 200, 'buscar_objeto_uid', 'sucesso'),
    ('/buscar_objeto_uid/inexistente', 404, 'buscar_objeto_uid', 'falha'),
])
def test_consultas_publicas_preservam_historico(client, inventory, models, path, status, action, result):
    response = client.get(path)
    assert response.status_code == status
    history = models.Historico_patrimonio.query.one()
    assert history.acao == action
    assert history.status_tentativa == result
    assert history.id_objeto == (inventory['item'].id if status == 200 else None)
    if status == 200:
        assert response.json['objeto']['nome'] == inventory['item'].nome


@pytest.mark.parametrize('term,status', [('Notebook', 200), ('book', 200), ('INEXISTENTE', 404)])
def test_busca_objeto_por_nome(client, inventory, models, term, status):
    response = client.get('/buscar_objeto_nome/' + term)
    assert response.status_code == status
    if status == 200:
        assert len(response.json['objetos']) == 1
    assert models.Historico_patrimonio.query.count() == 0


def test_cadastro_e_edicao_de_local(client, headers, inventory, models):
    response = client.post('/cadastrar_local', headers=headers['root'], json={
        'endereco': 'Nova sala', 'descricao': 'Descrição', 'responsavel': 'Responsável fictício'})
    assert response.status_code == 200
    assert models.Local.query.count() == 2
    response = client.put('/editar_local', headers=headers['root'], json={
        'local_alterado': inventory['place'].id, 'novo_endereco': 'Sala atualizada',
        'nova_descricao': 'Atualizada', 'novo_responsavel': 'Nova pessoa fictícia'})
    assert response.status_code == 200
    assert models.Local.query.filter_by(id=inventory['place'].id).one().endereco == 'Sala atualizada'


@pytest.mark.parametrize('method,path,payload,status', [('post', '/cadastrar_local', {}, 400),
    ('put', '/editar_local', {}, 400), ('put', '/editar_local', {'local_alterado': 999}, 404)])
def test_locais_rejeitam_corpo_vazio_ou_id_inexistente(client, headers, inventory, method, path, payload, status):
    assert getattr(client, method)(path, headers=headers['root'], json=payload).status_code == status


@pytest.mark.defeito_api
@pytest.mark.parametrize('missing', ['endereco', 'descricao', 'responsavel'])
def test_local_incompleto_deve_ser_rejeitado_com_400(client, headers, missing):
    payload = {'endereco': 'Sala', 'descricao': 'Descrição', 'responsavel': 'Pessoa fictícia'}
    del payload[missing]
    response = client.post('/cadastrar_local', headers=headers['root'], json=payload)
    assert response.status_code == 400


def test_listagem_publica_de_locais(client, inventory):
    response = client.get('/listar_locais')
    assert response.status_code == 200
    assert response.json['total_locais'] == 1
    assert response.json['locais'][0]['endereco'] == inventory['place'].endereco


def test_cadastro_esp32_preserva_mac_e_local_sem_token(client, inventory, models):
    mac = 'AA:BB:CC:DD:EE:02'
    response = client.post('/cadastrar_esp32', json={'mac_adress': mac, 'local': inventory['place'].id})
    assert response.status_code == 200
    assert set(response.json) == {'message'}
    device = models.Esp32_registro.query.filter_by(mac=mac).one()
    assert device.local == inventory['place'].id


@pytest.mark.parametrize('payload', [{}, {'mac_adress': 'AA:BB:CC:DD:EE:02'}, {'local': 1}])
def test_cadastro_esp32_rejeita_campos_ausentes(client, models, payload):
    response = client.post('/cadastrar_esp32', json=payload)
    assert response.status_code == 400
    assert models.Esp32_registro.query.count() == 0


def test_esp32_duplicado_nao_persiste_novamente(client, models, inventory):
    response = client.post('/cadastrar_esp32', json={'mac_adress': inventory['device'].mac, 'local': inventory['place'].id})
    assert response.status_code == 500  # Contrato existente para erro de integridade.
    assert models.Esp32_registro.query.count() == 1


@pytest.mark.parametrize('uid,expected_status', [('d4e5f6a7', 'livre'), ('a1b2c3d4', 'objeto'), ('c3d4e5f6', 'usuario')])
def test_leitura_http_autorizada_apenas_por_mac_cadastrado(client, inventory, models, uid, expected_status):
    from app.routes import rfid
    with patch.object(rfid, 'emit') as emit:
        response = client.post('/cadastrar_rfid', json={'uid': uid, 'date': '2026-01-01', 'mac_adress': inventory['device'].mac})
    assert response.status_code == 200
    assert models.RFID.query.filter_by(uid=uid).count() == 1
    event, payload = emit.call_args.args
    assert event == 'rfid_update'
    assert payload['uid'] == uid
    assert payload['status'] == expected_status
    assert emit.call_args.kwargs == {'namespace': '/', 'broadcast': True}
    assert rfid.ultimo_contato_esp > 0


@pytest.mark.parametrize('mac', ['AA:BB:CC:DD:EE:99', '', None])
def test_mac_nao_cadastrado_nao_autoriza_leitura(client, inventory, models, mac):
    response = client.post('/cadastrar_rfid', json={'uid': 'd4e5f6a7', 'date': '2026-01-01', 'mac_adress': mac})
    assert response.status_code == 403
    assert models.RFID.query.count() == 3


def test_leitura_idempotente_nao_duplica_tag(client, inventory, models):
    payload = {'uid': 'd4e5f6a7', 'date': '2026-01-01', 'mac_adress': inventory['device'].mac}
    assert client.post('/cadastrar_rfid', json=payload).status_code == 200
    assert client.post('/cadastrar_rfid', json=payload).status_code == 200
    assert models.RFID.query.count() == 4


def test_evento_socketio_real_em_processo_apos_leitura(client, app, inventory):
    from app.routes.app import socketio
    connection = socketio.test_client(app)
    assert connection.is_connected()
    try:
        response = client.post('/cadastrar_rfid', json={'uid': 'd4e5f6a7', 'date': '2026-01-01', 'mac_adress': inventory['device'].mac})
        assert response.status_code == 200
        received = connection.get_received()
        event = next(item for item in received if item['name'] == 'rfid_update')
        assert event['args'][0]['uid'] == 'd4e5f6a7'
    finally:
        connection.disconnect()


def test_rfid_corpo_vazio_retorna_400(client):
    assert client.post('/cadastrar_rfid', json={}).status_code == 400


def test_listagem_rfid_publica_preserva_campos(client, inventory):
    response = client.get('/vizualizar_todos_rfid')
    assert response.status_code == 200
    assert response.json['total_objetos'] == 3
    assert {item['tipo'] for item in response.json['objetos']} == {'livre', 'objeto', 'usuario'}


@pytest.mark.parametrize('uid,status', [('a1b2c3d4', 200), ('inexistente', 400)])
def test_consulta_rfid_por_uid(client, inventory, uid, status):
    response = client.get('/buscar_rfid/' + uid)
    assert response.status_code == status
    if status == 200:
        assert response.json['objeto']['uid'] == uid


@pytest.mark.parametrize('payload,status,remaining', [({}, 400, 3), ({'uid_recebido': 'inexistente'}, 404, 3),
    ({'uid_recebido': 'a1b2c3d4'}, 400, 3), ({'uid_recebido': 'b2c3d4e5'}, 200, 2)])
def test_exclusao_de_tag_livre_e_bloqueio_de_objeto(client, headers, inventory, models, payload, status, remaining):
    response = client.delete('/excluir_rfid', headers=headers['root'], json=payload)
    assert response.status_code == status
    assert models.RFID.query.count() == remaining


@pytest.mark.parametrize('method,path,payload', [
    ('post', '/cadastrar_local', {'endereco': 'Sala', 'descricao': 'Descrição', 'responsavel': 'Pessoa'}),
    ('put', '/editar_local', {'local_alterado': 1, 'novo_endereco': 'Sala', 'nova_descricao': 'Nova', 'novo_responsavel': 'Pessoa'}),
    ('post', '/cadastrar_esp32', {'mac_adress': 'AA:BB:CC:DD:EE:02', 'local': 1}),
    ('post', '/atribuir_rfid_usuario', {'id_usuario': 1, 'uid_usuario': 'b2c3d4e5'}),
    ('put', '/recadastrar_objeto', {'id_objeto': 1, 'nova_uid': 'b2c3d4e5'}),
    ('delete', '/excluir_objeto', {'objeto_excluir': 1}),
    ('delete', '/excluir_rfid', {'uid_recebido': 'b2c3d4e5'}),
])
def test_falha_de_commit_nao_persiste_operacao(client, headers, inventory, models, database, method, path, payload):
    with patch.object(database.session, 'commit', side_effect=OperationalError('SQL fictício', {}, Exception('offline'))), \
            patch.object(database.session, 'rollback', wraps=database.session.rollback) as rollback:
        response = getattr(client, method)(path, headers=headers['root'], json=payload)
    assert response.status_code == 500
    assert rollback.called
    assert models.Object.query.one().id_rfid == 'a1b2c3d4'
    assert models.RFID.query.count() == 3
    assert models.Esp32_registro.query.count() == 1
    assert models.Local.query.one().endereco == 'Laboratório de teste'
