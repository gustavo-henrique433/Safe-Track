import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def strict_engine(tmp_path, database):
    """FKs verificadas só neste engine de modelos; a API mantém sua configuração."""
    engine = create_engine('sqlite:///' + str(tmp_path / 'constraints.db'))

    @event.listens_for(engine, 'connect')
    def foreign_keys_on(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')

    database.metadata.create_all(engine)
    tables = database.metadata.tables
    with engine.begin() as connection:
        connection.execute(tables['local'].insert(), {'id': 1, 'endereco': 'Sala', 'descricao': 'Teste', 'responsavel': 'Pessoa'})
        connection.execute(tables['rfid'].insert(), [{'uid': 'a1b2c3d4', 'date': '2026-01-01'},
                                                     {'uid': 'b2c3d4e5', 'date': '2026-01-01'}])
        connection.execute(tables['users'].insert(), {'id': 1, 'nome': 'Teste', 'email': 'model@example.test',
            'senha': 'hash-ficticio', 'tipo_user': 'users', 'credencial_rfid': 'b2c3d4e5'})
        connection.execute(tables['object'].insert(), {'id': 1, 'id_rfid': 'a1b2c3d4', 'id_lugar': 1,
            'nome': 'Objeto', 'descricao': 'Teste', 'especificacoes': 'Teste'})
        connection.execute(tables['esp32_registro'].insert(), {'mac': 'AA:BB:CC:DD:EE:01', 'local': 1})
    yield engine
    engine.dispose()


CASES = [
    ('users', {'id': 2, 'nome': 'Outro', 'email': 'model@example.test', 'senha': 'hash', 'tipo_user': 'users'}),
    ('users', {'id': 2, 'nome': 'Outro', 'email': None, 'senha': 'hash', 'tipo_user': 'users'}),
    ('users', {'id': 2, 'nome': 'Outro', 'email': 'other@example.test', 'senha': None, 'tipo_user': 'users'}),
    ('users', {'id': 2, 'nome': 'Outro', 'email': 'other@example.test', 'senha': 'hash', 'tipo_user': 'users', 'credencial_rfid': 'b2c3d4e5'}),
    ('users', {'id': 2, 'nome': 'Outro', 'email': 'other@example.test', 'senha': 'hash', 'tipo_user': 'users', 'credencial_rfid': 'inexistente'}),
    ('rfid', {'uid': 'a1b2c3d4', 'date': '2026-01-02'}),
    ('rfid', {'uid': 'c3d4e5f6', 'date': None}),
    ('object', {'id': 2, 'id_rfid': 'a1b2c3d4', 'id_lugar': 1, 'nome': 'Outro', 'descricao': 'Teste', 'especificacoes': 'Teste'}),
    ('object', {'id': 2, 'id_rfid': 'inexistente', 'id_lugar': 1, 'nome': 'Outro', 'descricao': 'Teste', 'especificacoes': 'Teste'}),
    ('object', {'id': 2, 'id_rfid': 'b2c3d4e5', 'id_lugar': 999, 'nome': 'Outro', 'descricao': 'Teste', 'especificacoes': 'Teste'}),
    ('esp32_registro', {'mac': 'AA:BB:CC:DD:EE:01', 'local': 1}),
    ('esp32_registro', {'mac': 'AA:BB:CC:DD:EE:02', 'local': 999}),
    ('roots', {'id': 999, 'senha_root': 'hash-ficticio', 'nivel_permissao': 'total'}),
    ('roots', {'id': 1, 'senha_root': None, 'nivel_permissao': 'total'}),
    ('registro_acesso', {'id_rfid': 'inexistente', 'id_local': 1, 'status_tentativa': 'Negado'}),
    ('registro_acesso', {'id_rfid': None, 'id_local': 999, 'status_tentativa': 'Negado'}),
    ('historico_patrimonio', {'id_objeto': 999, 'id_usuario': None, 'acao': 'consulta'}),
    ('historico_patrimonio', {'id_objeto': None, 'id_usuario': 999, 'acao': 'consulta'}),
]


@pytest.mark.parametrize('table,values', CASES, ids=[
    'email_unico', 'email_obrigatorio', 'senha_obrigatoria', 'credencial_unica', 'credencial_fk',
    'uid_unica', 'data_obrigatoria', 'objeto_tag_unica', 'objeto_tag_fk', 'objeto_local_fk',
    'mac_unico', 'dispositivo_local_fk', 'root_usuario_fk', 'root_senha_obrigatoria',
    'acesso_tag_fk', 'acesso_local_fk', 'historico_objeto_fk', 'historico_usuario_fk'])
def test_restricoes_declaradas_no_schema(strict_engine, database, table, values):
    target = database.metadata.tables[table]
    with strict_engine.connect() as connection:
        before = len(connection.execute(select(target)).all())
    with pytest.raises(IntegrityError):
        with strict_engine.begin() as connection:
            connection.execute(target.insert(), values)
    with strict_engine.connect() as connection:
        assert len(connection.execute(select(target)).all()) == before


def test_referencias_opcionais_de_historico_aceitam_null(strict_engine, database):
    with strict_engine.begin() as connection:
        connection.execute(database.metadata.tables['registro_acesso'].insert(),
                           {'id_rfid': None, 'id_local': 1, 'status_tentativa': 'Negado'})
        connection.execute(database.metadata.tables['historico_patrimonio'].insert(),
                           {'id_objeto': None, 'id_usuario': None, 'acao': 'consulta', 'status_tentativa': 'falha'})
    with strict_engine.connect() as connection:
        row = connection.execute(select(database.metadata.tables['registro_acesso'])).one()
        assert row.id_rfid is None
        assert row.horario is not None


def test_hierarquia_user_root_e_relacionamento_local(users, inventory, models, database):
    database.session.expire_all()
    root = database.session.get(models.User, users['root'].id)
    assert isinstance(root, models.Root)
    assert root.tipo_user == 'roots'
    assert not isinstance(users['user'], models.Root)
    assert inventory['item'].local_relacionado.endereco == inventory['place'].endereco


def test_schema_original_com_as_extensoes_de_visitantes_e_permissoes_aprovadas(database):
    assert set(database.metadata.tables) == {'users', 'roots', 'rfid', 'object', 'local',
                                            'esp32_registro', 'registro_acesso', 'historico_patrimonio',
                                            'visitantes', 'visitante_locais', 'visitante_acessos', 'permissoes_acesso'}
    assert set(database.metadata.tables['esp32_registro'].columns.keys()) == {'mac', 'local'}


def test_verificacao_fk_dos_modelos_nao_reconfigura_engine_da_api(strict_engine, database):
    with strict_engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar() == 0


@pytest.mark.parametrize('case', ['pessoa_ausente', 'local_ausente', 'duplicada', 'periodo_igual',
                                 'periodo_invertido', 'revogada_nula', 'revogada_fora_do_dominio'])
def test_integridade_da_permissao_individual(strict_engine, database, case):
    table = database.metadata.tables['permissoes_acesso']
    values = {'pessoa_id': 1, 'local_id': 1}
    if case == 'pessoa_ausente': values['pessoa_id'] = 999
    if case == 'local_ausente': values['local_id'] = 999
    if case == 'duplicada':
        with strict_engine.begin() as connection: connection.execute(table.insert(), values)
    from datetime import datetime
    if case in {'periodo_igual', 'periodo_invertido'}:
        values.update(inicio=datetime(2026, 11, 2), expiracao=datetime(2026, 11, 2 if case == 'periodo_igual' else 1))
    if case == 'revogada_nula': values['revogada'] = None
    with pytest.raises(IntegrityError):
        with strict_engine.begin() as connection:
            if case == 'revogada_fora_do_dominio':
                connection.exec_driver_sql('INSERT INTO permissoes_acesso (pessoa_id,local_id,revogada) VALUES (1,1,2)')
            else: connection.execute(table.insert(), values)


def seed_visitor_legacy(connection, tables):
    from datetime import datetime
    connection.execute(tables['users'].insert(), {'id': 2, 'nome': 'Legado fictício',
        'email': 'legacy@example.test', 'senha': 'hash-ficticio', 'tipo_user': 'visitante'})
    connection.execute(tables['visitantes'].insert(), {'id': 2, 'inicio': datetime(2026, 1, 1),
        'expiracao': datetime(2027, 1, 1)})
    connection.execute(tables['visitante_locais'].insert(), {'visitante_id': 2, 'local_id': 1})


def test_backfill_explicito_preserva_legado_e_nao_reaplica_limites_globais(strict_engine, database):
    from src.database.permission_legacy import copy_visitor_permissions
    tables = database.metadata.tables
    with strict_engine.begin() as connection:
        seed_visitor_legacy(connection, tables)
        before = connection.execute(select(tables['visitante_locais'])).all()
        assert copy_visitor_permissions(connection) == 1
        assert copy_visitor_permissions(connection) == 0
        permission = connection.execute(select(tables['permissoes_acesso'])).mappings().one()
        assert (permission['pessoa_id'], permission['local_id']) == (2, 1)
        assert permission['inicio'] is permission['expiracao'] is None
        assert permission['revogada'] is False
        assert connection.execute(select(tables['visitante_locais'])).all() == before


def test_backfill_nao_reativa_ou_sobrescreve_permissao_existente(strict_engine, database):
    from datetime import datetime
    from src.database.permission_legacy import copy_visitor_permissions
    tables = database.metadata.tables
    with strict_engine.begin() as connection:
        seed_visitor_legacy(connection, tables)
        values = {'pessoa_id': 2, 'local_id': 1, 'inicio': datetime(2026, 3, 1),
                  'expiracao': datetime(2026, 4, 1), 'revogada': True}
        connection.execute(tables['permissoes_acesso'].insert(), values)
        assert copy_visitor_permissions(connection) == 0
        assert dict(connection.execute(select(tables['permissoes_acesso'])).mappings().one()) == values


def test_backfill_nao_faz_commit_e_pode_ser_revertido_pelo_chamador(strict_engine, database):
    from src.database.permission_legacy import copy_visitor_permissions
    tables = database.metadata.tables
    with strict_engine.begin() as connection: seed_visitor_legacy(connection, tables)
    with strict_engine.connect() as connection:
        transaction = connection.begin()
        assert copy_visitor_permissions(connection) == 1
        transaction.rollback()
        assert connection.execute(select(tables['permissoes_acesso'])).all() == []
        assert len(connection.execute(select(tables['visitante_locais'])).all()) == 1


@pytest.mark.parametrize('case', ['visitante_sem_user', 'inicio_nulo', 'periodo_invertido', 'periodo_igual',
    'local_inexistente', 'user_nao_visitante', 'local_duplicado', 'registro_inexistente',
    'historico_user_nao_visitante', 'registro_duplicado'])
def test_restricoes_das_tres_tabelas_de_visitante(strict_engine, database, case):
    from datetime import datetime, timedelta
    tables = database.metadata.tables
    start = datetime(2026, 11, 17, 10)
    end = start + timedelta(hours=1)
    with strict_engine.begin() as connection:
        connection.execute(tables['users'].insert(), [
            {'id': 2, 'nome': 'Visitante', 'email': 'visitor-model@example.test', 'senha': 'hash', 'tipo_user': 'visitante'},
            {'id': 3, 'nome': 'Usuário', 'email': 'other-model@example.test', 'senha': 'hash', 'tipo_user': 'users'}])
        connection.execute(tables['visitantes'].insert(), {'id': 2, 'inicio': start, 'expiracao': end})
        connection.execute(tables['visitante_locais'].insert(), {'visitante_id': 2, 'local_id': 1})
        connection.execute(tables['registro_acesso'].insert(), [
            {'id': 1, 'id_local': 1, 'status_tentativa': 'Negado'},
            {'id': 2, 'id_local': 1, 'status_tentativa': 'Negado'}])
        connection.execute(tables['visitante_acessos'].insert(), {'registro_id': 1, 'visitante_id': 2})
    attempts = {
        'visitante_sem_user': ('visitantes', {'id': 999, 'inicio': start, 'expiracao': end}),
        'inicio_nulo': ('visitantes', {'id': 3, 'inicio': None, 'expiracao': end}),
        'periodo_invertido': ('visitantes', {'id': 3, 'inicio': end, 'expiracao': start}),
        'periodo_igual': ('visitantes', {'id': 3, 'inicio': start, 'expiracao': start}),
        'local_inexistente': ('visitante_locais', {'visitante_id': 2, 'local_id': 999}),
        'user_nao_visitante': ('visitante_locais', {'visitante_id': 3, 'local_id': 1}),
        'local_duplicado': ('visitante_locais', {'visitante_id': 2, 'local_id': 1}),
        'registro_inexistente': ('visitante_acessos', {'registro_id': 999, 'visitante_id': 2}),
        'historico_user_nao_visitante': ('visitante_acessos', {'registro_id': 2, 'visitante_id': 3}),
        'registro_duplicado': ('visitante_acessos', {'registro_id': 1, 'visitante_id': 2}),
    }
    name, values = attempts[case]
    target = tables[name]
    with strict_engine.connect() as connection:
        before = len(connection.execute(select(target)).all())
    with pytest.raises(IntegrityError):
        with strict_engine.begin() as connection:
            connection.execute(target.insert(), values)
    with strict_engine.connect() as connection:
        assert len(connection.execute(select(target)).all()) == before
