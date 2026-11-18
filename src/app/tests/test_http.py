from pathlib import Path
import socket
import sqlite3
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import FileStorage


def test_pagina_inicial_preserva_template_e_javascript(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'id="login_email"' in response.text
    assert 'script.js' in response.text


@pytest.mark.defeito_api
@pytest.mark.parametrize('method,path,status', [('get', '/rota-inexistente', 404), ('get', '/login', 405)])
def test_erros_http_preservam_status_original(client, method, path, status):
    response = getattr(client, method)(path)
    assert response.status_code == status
    if status == 405:
        assert 'POST' in response.headers['Allow']


@pytest.mark.defeito_api
@pytest.mark.parametrize('payload,content_type,status', [('{', 'application/json', 400),
    ('texto', 'text/plain', 415)], ids=['json_malformado', 'content_type_incorreto'])
def test_erros_de_parse_json_preservam_status(client, payload, content_type, status):
    response = client.post('/login', data=payload, content_type=content_type)
    assert response.status_code == status


def test_excecao_inesperada_retorna_resposta_generica(client):
    from app.routes import local
    with patch.object(local.Local, 'query') as query:
        query.all.side_effect = RuntimeError('detalhe-ficticio-interno')
        response = client.get('/listar_locais')
    assert response.status_code == 500
    assert 'detalhe-ficticio-interno' not in response.text


def test_falha_de_banco_no_cadastro_retorna_500(client, database):
    with patch.object(database.session, 'commit', side_effect=OperationalError('SQL fictício', {}, Exception('offline'))):
        response = client.post('/registrar_usuario', json={'nome': 'Teste', 'email': 'teste@example.test', 'senha': 'Ficticia-123!'})
    assert response.status_code == 500


def test_logger_original_preserva_mensagem_e_arquivos_temporarios(client, isolated_runtime):
    client.get('/listar_locais')
    directory = isolated_runtime['root'] / 'Logs'
    text = (directory / 'debug.log').read_text()
    assert 'INFO - Acesso | IP: 127.0.0.1 | Método: GET | Rota: /listar_locais' in text
    assert (directory / 'error.log').is_file()


def test_bootstrap_esta_isolado_em_memoria(app, database, isolated_runtime):
    assert app.testing
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://'
    assert database.engine.url.database in (None, '', ':memory:')
    assert Path.cwd().is_relative_to(isolated_runtime['boundary'])


@pytest.mark.parametrize('operation', ['sqlite', 'sqlite_uri', 'socket', 'dns', 'upload'])
def test_bloqueios_impedem_acesso_externo(isolated_runtime, operation):
    import io
    with pytest.raises(AssertionError):
        if operation == 'sqlite':
            sqlite3.connect('/caminho-real-nao-permitido/hermes.db')
        elif operation == 'sqlite_uri':
            sqlite3.connect('file:///caminho-real-nao-permitido/hermes.db?mode=ro', uri=True)
        elif operation == 'socket':
            with socket.socket() as connection:
                connection.connect(('127.0.0.1', 1883))
        elif operation == 'dns':
            socket.getaddrinfo('test.mosquitto.org', 1883)
        else:
            FileStorage(stream=io.BytesIO(b'ficticio'), filename='teste.png').save('/caminho-real-nao-permitido/imagem.png')
