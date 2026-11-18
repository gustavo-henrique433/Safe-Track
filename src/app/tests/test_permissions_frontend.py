"""Contratos reais e assets da integração Pessoas/Locais, apenas no SQLite isolado."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import pytest


@pytest.mark.parametrize('filename,mimetype', [('permissions.js', 'text/javascript'),
                                             ('permissions.css', 'text/css')])
def test_assets_de_permissoes_no_flask_original(client, filename, mimetype):
    response = client.get(f'/static/{filename}')
    assert response.status_code == 200
    assert response.mimetype == mimetype


def test_amostras_reais_de_pessoas_locais_e_escrita_para_dom(
        client, headers, users, inventory, visitor_factory, models, database):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expired = visitor_factory(nome='Visitante com credencial expirada',
                              inicio=now - timedelta(days=2), expiracao=now - timedelta(days=1))
    active = visitor_factory(nome='Visitante com credencial ativa')
    second = models.Local(endereco='Sala dos servidores', descricao='Somente teste', responsavel='Equipe fictícia')
    third = models.Local(endereco='Sala sem permissão', descricao='Somente teste', responsavel='Equipe fictícia')
    database.session.add_all([second, third]); database.session.commit()
    person_id, local_id = users['user'].id, inventory['place'].id

    def get(path):
        response = client.get(path, headers=headers['root'])
        assert response.status_code == 200
        return response.json

    def put(room_id, body):
        response = client.put(f'/pessoas/{person_id}/permissoes/{room_id}', headers=headers['root'], json=body)
        assert response.status_code in (200, 201)
        return response.json

    put(local_id, {'revogada': False})
    put(second.id, {'inicio': '2026-01-01T10:30:00.123456Z', 'expiracao': '2030-01-01T10:30:00Z', 'revogada': True})
    person = get(f'/pessoas/{person_id}/permissoes')
    room_all = get(f'/locais/{local_id}/autorizacoes?situacao=todas')
    room_effective = get(f'/locais/{local_id}/autorizacoes')
    denied = next(row for row in room_all['autorizacoes'] if row['pessoa']['id'] == expired.id)
    assert denied['situacao'] == 'vigente' and denied['pessoa']['status_credencial'] == 'expirado'
    assert denied['acesso_efetivo'] is False
    assert expired.id not in {row['pessoa']['id'] for row in room_effective['autorizacoes']}
    changed = put(second.id, {'expiracao': None})
    assert changed['permissao']['revogada'] is True
    reactivated = put(second.id, {'revogada': False})
    response = client.post(f'/pessoas/{person_id}/permissoes/{local_id}/revogar', headers=headers['root'])
    assert response.status_code == 200
    assert database.session.get(models.User, person_id) is not None
    assert database.session.get(models.PermissaoAcesso, (person_id, second.id)).revogada is False
    snapshot = {'person': person, 'expired_person': get(f'/pessoas/{expired.id}/permissoes'),
                'room_all': room_all, 'room_effective': room_effective,
                'locals': get('/listar_locais'), 'accounts': get('/visualizar_todos_usuarios'),
                'changed': changed, 'reactivated': reactivated, 'revoked': response.json,
                'created': put(third.id, {'inicio': None, 'expiracao': None, 'revogada': False}),
                'ids': {'person': person_id, 'room': local_id, 'second': second.id, 'third': third.id,
                        'expired': expired.id, 'active': active.id}}
    output = os.environ.get('SAFE_TRACK_FRONTEND_ARTIFACTS')
    if output:
        directory = Path(output).resolve()
        assert directory.is_relative_to(Path('/tmp'))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'permissions-api.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
