"""Isolamento de testes sem alterar o código ou a configuração da implantação."""
import importlib
import json
import logging
import math
from pathlib import Path
import socket
import sqlite3
import statistics
import time
from urllib.parse import unquote, urlsplit

import pytest
from flask.testing import FlaskClient
from flask_sqlalchemy import SQLAlchemy
from werkzeug.datastructures import FileStorage


def pytest_addoption(parser):
    parser.addoption('--api-timings', metavar='ARQUIVO',
                     help='Salva tempos do cliente Flask, sem corpos, senhas ou JWTs.')


def pytest_configure(config):
    config.safe_track_timings = []


def pytest_terminal_summary(terminalreporter, config):
    samples = config.safe_track_timings
    if not samples:
        return
    durations = sorted(item['duration_ms'] for item in samples)
    summary = {
        'requests': len(samples),
        'mean_ms': round(statistics.mean(durations), 3),
        'median_ms': round(statistics.median(durations), 3),
        'p95_ms': durations[math.ceil(len(durations) * .95) - 1],
        'max_ms': durations[-1],
        'scope': 'Cliente Flask em processo; sem rede, broker ou ESP32.',
    }
    terminalreporter.write_sep('-', 'Tempos das requisições no cliente Flask')
    terminalreporter.write_line(json.dumps(summary, ensure_ascii=False))
    output = config.getoption('--api-timings')
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'summary': summary, 'samples': samples},
                                   ensure_ascii=False, indent=2), encoding='utf-8')


class TimedClient(FlaskClient):
    def open(self, *args, **kwargs):
        started = time.perf_counter_ns()
        response = super().open(*args, **kwargs)
        self.timings.append({'method': response.request.method,
                             'path': response.request.path,
                             'status': response.status_code,
                             'duration_ms': round((time.perf_counter_ns() - started) / 1_000_000, 3)})
        return response


@pytest.fixture(scope='session', autouse=True)
def isolated_runtime(tmp_path_factory):
    """Instale os bloqueios antes do primeiro import da aplicação."""
    boundary = tmp_path_factory.getbasetemp().resolve()
    runtime = tmp_path_factory.mktemp('safe-track-runtime')
    original_connect = sqlite3.dbapi2.connect
    original_init = SQLAlchemy.init_app
    original_save = FileStorage.save
    original_handler_init = logging.FileHandler.__init__

    def temporary_database_only(database, *args, **kwargs):
        value = str(database)
        candidate = unquote(urlsplit(value).path) if value.startswith('file:') else value
        if value != ':memory:' and not Path(candidate).resolve().is_relative_to(boundary):
            raise AssertionError('Teste tentou abrir banco fora do diretório temporário.')
        return original_connect(database, *args, **kwargs)

    def initialize_test_database(extension, application):
        application.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SECRET_KEY='safe-track-session-key-exclusive-to-tests',
            JWT_SECRET_KEY='safe-track-jwt-signing-key-exclusive-to-tests',
        )
        return original_init(extension, application)

    def temporary_upload_only(storage, destination, *args, **kwargs):
        if not isinstance(destination, (str, Path)) or not Path(destination).resolve().is_relative_to(boundary):
            raise AssertionError('Teste tentou salvar upload fora do diretório temporário.')
        return original_save(storage, destination, *args, **kwargs)

    def temporary_log_only(handler, filename, *args, **kwargs):
        if not Path(filename).resolve().is_relative_to(boundary):
            raise AssertionError('Teste tentou abrir log fora do diretório temporário.')
        return original_handler_init(handler, filename, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise AssertionError('Rede real bloqueada nos testes; use mocks para MQTT/HTTP externo.')

    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(runtime)
        patch.setattr(sqlite3, 'connect', temporary_database_only)
        patch.setattr(sqlite3.dbapi2, 'connect', temporary_database_only)
        patch.setattr(SQLAlchemy, 'init_app', initialize_test_database)
        patch.setattr(FileStorage, 'save', temporary_upload_only)
        patch.setattr(logging.FileHandler, '__init__', temporary_log_only)
        patch.setattr(socket.socket, 'connect', no_network)
        patch.setattr(socket.socket, 'connect_ex', no_network)
        patch.setattr(socket, 'getaddrinfo', no_network)
        # A função original mantém handlers, níveis, mensagens e formatação.
        # Somente o caminho de origem visto durante os testes é temporário.
        log_module = importlib.import_module('src.logs.config_log')
        patch.setattr(log_module, '__file__', str(runtime / 'src/logs/config_log.py'))
        yield {'boundary': boundary, 'root': runtime}


@pytest.fixture(scope='session')
def app(isolated_runtime):
    module = importlib.import_module('app.routes.app')
    application = module.app
    assert application.testing
    assert application.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://'
    with application.app_context():
        assert module.db.engine.url.database in (None, '', ':memory:')
    application.test_client_class = TimedClient
    yield application
    with application.app_context():
        module.db.session.remove()
        module.db.engine.dispose()
    for handler in module.logger.handlers[:]:
        handler.close()
        module.logger.removeHandler(handler)


@pytest.fixture(scope='session')
def models(app):
    return importlib.import_module('src.database.models')


@pytest.fixture(autouse=True)
def database(app, monkeypatch, tmp_path):
    from app.config.extensions import db
    from app.routes import app as app_module, auth, rfid
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rfid, 'ultimo_contato_esp', 0)
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        # Os conjuntos originais continuam distintos: a fixture não corrige logout.
        app_module.BLOCKLIST.clear()
        auth.BLOCKLIST.clear()
        yield db
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        app_module.BLOCKLIST.clear()
        auth.BLOCKLIST.clear()


@pytest.fixture
def client(app, database, request):
    with app.test_client() as test_client:
        test_client.timings = request.config.safe_track_timings
        yield test_client


@pytest.fixture(scope='session')
def password_hash():
    from werkzeug.security import generate_password_hash
    return generate_password_hash('Senha-ficticia-123!')


@pytest.fixture
def users(database, models, password_hash):
    root = models.Root(nome='Admin fictício', email='root@example.test', senha=password_hash,
                       senha_root=password_hash, nivel_permissao='total', tipo_user='roots')
    common = models.User(nome='Usuário fictício', email='user@example.test', senha=password_hash, tipo_user='users')
    inactive = models.User(nome='Inativo fictício', email='inactive@example.test', senha=password_hash,
                           tipo_user='users', status_conta=False)
    database.session.add_all([root, common, inactive])
    database.session.commit()
    return {'root': root, 'user': common, 'inactive': inactive}


@pytest.fixture
def headers(users):
    from flask_jwt_extended import create_access_token
    return {role: {'Authorization': 'Bearer ' + create_access_token(identity=str(user.id))}
            for role, user in users.items()}


@pytest.fixture
def inventory(database, models, users):
    place = models.Local(endereco='Laboratório de teste', descricao='Sala fictícia', responsavel='Equipe fictícia')
    tags = [models.RFID(uid=uid, date='2026-01-01') for uid in ('a1b2c3d4', 'b2c3d4e5', 'c3d4e5f6')]
    database.session.add_all([place, *tags])
    database.session.flush()
    device = models.Esp32_registro(mac='AA:BB:CC:DD:EE:01', local=place.id)
    item = models.Object(nome='Notebook fictício', descricao='Equipamento de teste', especificacoes='Dados fictícios',
                         id_rfid=tags[0].uid, id_lugar=place.id, url_imagem='static/uploads/teste.png')
    users['user'].credencial_rfid = tags[2].uid
    database.session.add_all([device, item])
    database.session.commit()
    return {'place': place, 'tags': tags, 'device': device, 'item': item}


@pytest.fixture
def mqtt_modules(monkeypatch):
    # O executável original importa os módulos como irmãos de topo.
    # Os testes reproduzem esse caminho sem modificar os imports da integração.
    directory = Path(__file__).resolve().parents[1] / 'services'
    monkeypatch.syspath_prepend(str(directory))
    return {name: importlib.import_module(name) for name in
            ('mqtt_configs', 'mqtt_publish', 'mqtt_subscribe', 'mqtt_client')}


@pytest.fixture
def visitor_factory(database, models, inventory, password_hash):
    from datetime import datetime, timedelta, timezone
    counter = 0

    def create(**changes):
        nonlocal counter
        counter += 1
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        uid = changes.pop('credencial_rfid', f'd4e5{counter:04x}')
        if database.session.get(models.RFID, uid) is None:
            database.session.add(models.RFID(uid=uid, date='2026-01-01'))
            database.session.flush()
        fields = {'nome': f'Visitante fictício {counter}', 'email': f'visitor-{counter}@example.test',
                  'senha': password_hash, 'tipo_user': 'visitante', 'credencial_rfid': uid,
                  'inicio': now - timedelta(hours=1), 'expiracao': now + timedelta(hours=1),
                  'locais': [inventory['place']]}
        fields.update(changes)
        places = fields.pop('locais')
        visitor = models.Visitante(**fields)
        database.session.add(visitor)
        visitor.permissoes = [models.PermissaoAcesso(local_id=place.id, revogada=False) for place in places]
        database.session.commit()
        return visitor

    return create
