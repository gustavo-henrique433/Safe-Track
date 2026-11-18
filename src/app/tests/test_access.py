import pytest
from sqlalchemy.exc import OperationalError
from unittest.mock import patch


@pytest.mark.parametrize('mode,status,result,allowed', [('valid', 200, 'Liberado', True),
    ('inactive', 403, 'Negado', False), ('unknown', 403, 'Negado', False)],
    ids=['credencial_valida', 'conta_inativa', 'credencial_desconhecida'])
def test_fluxo_original_da_porta_e_historico(client, database, models, users, inventory, mode, status, result, allowed):
    database.session.add(models.PermissaoAcesso(pessoa_id=users['user'].id, local_id=inventory['place'].id))
    database.session.commit()
    uid = inventory['tags'][2].uid
    if mode == 'inactive':
        users['user'].status_conta = False
        database.session.commit()
    elif mode == 'unknown':
        uid = 'nao-cadastrada'
    response = client.post('/acessar_porta', json={'uid_solicitante': uid, 'local': inventory['place'].id})
    assert response.status_code == status
    assert response.json['abrir'] is allowed
    event = models.Registro_Acesso.query.one()
    assert event.id_rfid == uid
    assert event.id_local == inventory['place'].id
    assert event.status_tentativa == result
    assert event.horario is not None


@pytest.mark.parametrize('payload,status', [({}, 400), ({'uid_solicitante': 'c3d4e5f6', 'local': 999}, 404),
                                           ({'uid_solicitante': 'c3d4e5f6'}, 404)])
def test_porta_sem_local_valido_nao_cria_evento(client, models, inventory, payload, status):
    response = client.post('/acessar_porta', json=payload)
    assert response.status_code == status
    assert models.Registro_Acesso.query.count() == 0


def test_falha_ao_persistir_acesso_nao_abre_porta(client, database, models, inventory):
    with patch.object(database.session, 'commit', side_effect=OperationalError('SQL fictício', {}, Exception('offline'))), \
            patch.object(database.session, 'rollback', wraps=database.session.rollback) as rollback:
        response = client.post('/acessar_porta', json={'uid_solicitante': inventory['tags'][2].uid, 'local': inventory['place'].id})
    assert response.status_code == 500
    assert response.json.get('abrir') is not True
    assert rollback.called
    assert models.Registro_Acesso.query.count() == 0
