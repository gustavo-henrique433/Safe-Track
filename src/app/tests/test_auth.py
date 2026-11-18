import pytest
from datetime import timedelta
from unittest.mock import patch


@pytest.mark.parametrize('email,senha,status_esperado', [
    ('root@example.test', 'Senha-ficticia-123!', 200),
    ('root@example.test', 'admin123', 401),
    ('root@example.test', 'senha_errada', 401),
    ('fantasma@example.test', 'admin123', 401),
    ('', 'admin123', 401),
], ids=['credenciais_validas', 'senha_incorreta', 'outra_senha_incorreta', 'usuario_inexistente', 'email_vazio'])
def test_login_dinamico(client, users, email, senha, status_esperado):
    """Os cinco cenários originais, com fixture e contrato efetivo de /login."""
    resposta = client.post('/login', json={'email': email, 'senha': senha})
    assert resposta.status_code == status_esperado
    if status_esperado == 200:
        assert resposta.json['access_token']
        assert resposta.json['user_type'] == 'roots'
    else:
        assert 'access_token' not in resposta.json


@pytest.mark.parametrize('role', ['root', 'user'])
def test_login_emite_jwt_com_identidade_e_expiracao(client, users, role):
    from flask_jwt_extended import decode_token
    response = client.post('/login', json={'email': users[role].email, 'senha': 'Senha-ficticia-123!'})
    assert response.status_code == 200
    claims = decode_token(response.json['access_token'])
    assert claims['sub'] == str(users[role].id)
    assert claims['type'] == 'access'
    assert claims['exp'] > claims['iat']


def test_cadastro_publico_preserva_contrato_e_armazena_hash(client, database, models):
    from werkzeug.security import check_password_hash
    response = client.post('/registrar_usuario', json={'nome': 'Pessoa fictícia', 'email': 'novo@example.test',
                                                      'senha': 'Outra-senha-ficticia-123!'})
    assert response.status_code == 201
    account = models.User.query.one()
    assert account.tipo_user == 'users'
    assert account.senha != 'Outra-senha-ficticia-123!'
    assert check_password_hash(account.senha, 'Outra-senha-ficticia-123!')
    assert client.post('/login', json={'email': account.email, 'senha': 'Outra-senha-ficticia-123!'}).status_code == 200


@pytest.mark.parametrize('payload', [{}, {'nome': 'Teste'}, {'nome': 'Teste', 'email': 'novo@example.test'},
                                     {'email': 'novo@example.test', 'senha': 'Ficticia-123!'}],
                         ids=['vazio', 'somente_nome', 'sem_senha', 'sem_nome'])
def test_cadastro_incompleto_nao_persiste(client, models, payload):
    response = client.post('/registrar_usuario', json=payload)
    assert response.status_code == 400
    assert models.User.query.count() == 0


@pytest.mark.defeito_api
def test_cadastro_email_duplicado_deve_retornar_400(client, users, models):
    """A própria rota pretende responder 400, mas passa um set para jsonify."""
    response = client.post('/registrar_usuario', json={'nome': 'Duplicado', 'email': users['user'].email,
                                                      'senha': 'Ficticia-duplicada-123!'})
    assert response.status_code == 400
    assert models.User.query.count() == 3


@pytest.mark.parametrize('method,path', [
    ('post', '/registrar_root'), ('post', '/atribuir_rfid_usuario'), ('get', '/visualizar_todos_usuarios'),
    ('post', '/cadastrar_objeto'), ('put', '/recadastrar_objeto'), ('delete', '/excluir_objeto'),
    ('post', '/cadastrar_local'), ('put', '/editar_local'), ('delete', '/excluir_rfid'),
])
@pytest.mark.parametrize('role,status', [(None, 401), ('user', 403)])
def test_permissoes_administrativas_existentes(client, headers, method, path, role, status):
    response = getattr(client, method)(path, json={}, headers=headers[role] if role else {})
    assert response.status_code == status


@pytest.mark.parametrize('kind,status', [('expired', 401), ('malformed', 422), ('wrong_signature', 422), ('refresh', 422)])
def test_jwt_invalido_nao_acessa_rota_protegida(client, users, app, kind, status):
    from flask_jwt_extended import create_access_token, create_refresh_token
    if kind == 'expired':
        token = create_access_token(identity=str(users['root'].id), expires_delta=timedelta(seconds=-1))
    elif kind == 'refresh':
        token = create_refresh_token(identity=str(users['root'].id))
    elif kind == 'wrong_signature':
        with patch.dict(app.config, JWT_SECRET_KEY='different-key-exclusive-to-invalid-token-tests'):
            token = create_access_token(identity=str(users['root'].id))
    else:
        token = 'conteudo.que.nao-e-jwt'
    response = client.get('/visualizar_todos_usuarios', headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == status
    assert 'usuarios' not in response.json


def test_callback_existente_rejeita_jti_na_blocklist_da_aplicacao(client, users):
    from app.routes.app import BLOCKLIST
    from flask_jwt_extended import create_access_token, decode_token
    token = create_access_token(identity=str(users['root'].id))
    BLOCKLIST.add(decode_token(token)['jti'])
    response = client.get('/visualizar_todos_usuarios', headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 401


def test_logout_registra_jti_no_conjunto_da_rota(client, headers):
    from app.routes import auth
    from flask_jwt_extended import decode_token
    response = client.post('/logout', headers=headers['root'])
    assert response.status_code == 200
    token = headers['root']['Authorization'].removeprefix('Bearer ')
    assert decode_token(token)['jti'] in auth.BLOCKLIST


@pytest.mark.defeito_api
def test_token_deve_ser_rejeitado_apos_logout(client, headers):
    assert client.post('/logout', headers=headers['root']).status_code == 200
    response = client.get('/visualizar_todos_usuarios', headers=headers['root'])
    assert response.status_code == 401


@pytest.mark.defeito_api
def test_root_pode_cadastrar_outro_root_valido(client, headers, models):
    response = client.post('/registrar_root', headers=headers['root'], json={
        'nome': 'Outro administrador fictício', 'email': 'outro-root@example.test',
        'senha_root': 'Outra-senha-root-ficticia-123!', 'nivel_permissao': 'total'})
    assert response.status_code == 201
    assert models.Root.query.count() == 2
    assert client.post('/login', json={'email': 'outro-root@example.test',
                                      'senha': 'Outra-senha-root-ficticia-123!'}).status_code == 200


@pytest.mark.parametrize('payload,status', [({}, 400), ({'id_usuario': 999, 'uid_usuario': 'b2c3d4e5'}, 404),
    ({'id_usuario': 1, 'uid_usuario': 'nao-cadastrada'}, 404),
    ({'id_usuario': 1, 'uid_usuario': 'a1b2c3d4'}, 409),
    ({'id_usuario': 1, 'uid_usuario': 'c3d4e5f6'}, 409),
    ({'id_usuario': 3, 'uid_usuario': 'b2c3d4e5'}, 404)])
def test_associacao_usuario_rfid_rejeita_conflitos(client, headers, inventory, payload, status):
    response = client.post('/atribuir_rfid_usuario', headers=headers['root'], json=payload)
    assert response.status_code == status


def test_associacao_usuario_rfid_valida(client, headers, users, inventory, models):
    response = client.post('/atribuir_rfid_usuario', headers=headers['root'], json={
        'id_usuario': users['root'].id, 'uid_usuario': inventory['tags'][1].uid})
    assert response.status_code == 200
    assert models.Root.query.one().credencial_rfid == inventory['tags'][1].uid


def test_consulta_usuarios_root_nao_retorna_hashes(client, headers, users):
    response = client.get('/visualizar_todos_usuarios', headers=headers['root'])
    assert response.status_code == 200
    assert response.json['total'] == 3
    assert all(set(row) == {'id', 'nome', 'email', 'credencial_rfid'} for row in response.json['usuarios'])


@pytest.mark.parametrize('uid,status', [('c3d4e5f6', 200), ('inexistente', 404)])
def test_busca_usuario_por_uid_preserva_rota_publica(client, inventory, uid, status):
    response = client.get('/buscar_usuario_uid/' + uid)
    assert response.status_code == status
    if status == 200:
        assert response.json['usuario']['credencial_rfid'] == uid
