"""Template real e amostras de contratos para os testes de DOM sem rede."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path

import pytest


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.admin_links = []
        self.assets = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if attributes.get('id'):
            self.ids.append(attributes['id'])
        if 'data-safe-track-admin' in attributes:
            self.admin_links.append(attributes)
        if tag in {'link', 'script'}:
            self.assets.append(attributes.get('src', attributes.get('href')))


def test_template_preserva_modulos_e_oculta_novos_acessos_antes_do_login(client, models):
    response = client.get('/')
    assert response.status_code == 200
    page = Elements()
    page.feed(response.get_data(as_text=True))
    assert all(count == 1 for count in Counter(page.ids).values())
    assert {'tela-login', 'aba-dashboard', 'aba-busca', 'aba-cadastro', 'aba-usuarios',
            'aba-locais', 'sec-tags', 'form-cadastro', 'form-local', 'form-editar-local',
            'novo_nome_usuario', 'id_usuario_atribuir'} <= set(page.ids)
    assert {'aba-visitantes', 'aba-relatorios', 'st-visitante-dialogo'} <= set(page.ids)
    assert len(page.admin_links) == 2
    assert all('hidden' in link and 'hidden' in link['class'].split() for link in page.admin_links)
    assert {'static/script.js', '/static/admin.js', '/static/admin.css'} <= set(page.assets)
    assert models.Registro_Acesso.query.count() == models.Historico_patrimonio.query.count() == 0


@pytest.mark.parametrize('filename,mimetype', [('admin.js', 'text/javascript'),
                                             ('admin.css', 'text/css')])
def test_assets_da_interface_sao_servidos_pelo_flask_existente(client, filename, mimetype):
    response = client.get(f'/static/{filename}')
    assert response.status_code == 200
    assert response.mimetype == mimetype
    assert len(response.data) > 100


def test_contratos_reais_disponiveis_para_o_frontend_sem_alterar_rotas(
        client, headers, models, visitor_factory, inventory):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active = visitor_factory(nome='Visitante ativo da interface')
    visitor_factory(nome='Visitante expirado da interface', inicio=now - timedelta(days=2),
                    expiracao=now - timedelta(days=1))
    visitor_factory(nome='Visitante revogado da interface', status_conta=False)
    for uid, status in [(active.credencial_rfid, 200), ('uid-sem-cadastro', 403)]:
        response = client.post('/acessar_porta', json={'uid_solicitante': uid, 'local': inventory['place'].id})
        assert response.status_code == status
    assert client.get(f"/buscar_objeto_id/{inventory['item'].id}").status_code == 200
    paths = {'visitors': '/visitantes', 'visitor': f'/visitantes/{active.id}',
             'summary': '/api/dashboards/resumo', 'accesses': '/api/relatorios/acessos',
             'activities': '/api/relatorios/atividades', 'locals': '/listar_locais',
             'tags': '/vizualizar_todos_rfid'}
    snapshots = {}
    for name, path in paths.items():
        response = client.get(path, headers=headers['root'])
        assert response.status_code == 200
        snapshots[name] = response.json
    csv = client.get('/api/relatorios/acessos.csv', headers=headers['root'])
    assert csv.status_code == 200
    snapshots['csv'] = csv.data.decode('utf-8-sig')
    assert snapshots['visitors']['total'] == 3
    assert snapshots['summary']['acessos'] == {'total': 2, 'autorizados': 1, 'negados': 1, 'indefinidos': 0}
    assert snapshots['accesses']['acessos'][0]['visitante_id'] is None
    assert snapshots['accesses']['acessos'][1]['visitante_id'] == active.id
    assert models.Registro_Acesso.query.count() == 2
    assert models.Historico_patrimonio.query.count() == 1
    # Exportação opcional de dados fictícios, só em /tmp, para o runner Node.
    output = os.environ.get('SAFE_TRACK_FRONTEND_ARTIFACTS')
    if output:
        directory = Path(output).resolve()
        assert directory.is_relative_to(Path('/tmp'))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'index-renderizado.html').write_text(client.get('/').get_data(as_text=True), encoding='utf-8')
        (directory / 'frontend-api.json').write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding='utf-8')
