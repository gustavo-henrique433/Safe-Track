import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


def message(modules, data=None, payload=None, topic=None):
    if payload is None:
        payload = json.dumps(data if data is not None else {
            'uid': 'a1b2c3d4', 'date': '2026-01-01', 'mac_adress': 'AA:BB:CC:DD:EE:01'}).encode()
    return SimpleNamespace(topic=topic or modules['mqtt_configs'].TOPICO_ESCUTA, payload=payload)


def test_configuracao_original_de_broker_topicos_e_rota(mqtt_modules):
    cfg = mqtt_modules['mqtt_configs']
    assert cfg.BROKER == 'test.mosquitto.org'
    assert cfg.PORTA_BROKER == 1883
    assert cfg.TOPICO_ESCUTA == 'ESP_envia_tag'
    assert cfg.TOPICO_CALLBACK == 'Resposta_API'
    assert cfg.API_URL.endswith('/cadastrar_rfid')


def test_conexao_assina_topico_original(mqtt_modules):
    client = Mock()
    mqtt_modules['mqtt_subscribe'].ao_connectar(client, None, {}, 0)
    client.subscribe.assert_called_once_with(mqtt_modules['mqtt_configs'].TOPICO_ESCUTA)


@pytest.mark.parametrize('http_status,expected', [(200, '200'), (201, '200'), (400, '401'),
    (401, '401'), (403, '401'), (404, '401'), (500, '401')])
def test_mensagem_encaminha_json_original_sem_token_ou_cabecalho_novo(mqtt_modules, http_status, expected):
    sub, cfg = mqtt_modules['mqtt_subscribe'], mqtt_modules['mqtt_configs']
    client = Mock()
    data = {'uid': 'a1b2c3d4', 'date': '2026-01-01', 'mac_adress': 'AA:BB:CC:DD:EE:01'}
    with patch.object(sub.requests, 'post') as post:
        post.return_value.status_code = http_status
        sub.ao_receber_mensagem(client, None, message(mqtt_modules, data))
    post.assert_called_once_with(cfg.API_URL, json=data)
    client.publish.assert_called_once_with(cfg.TOPICO_CALLBACK, expected)


def test_topico_alheio_nao_encaminha_mensagem(mqtt_modules):
    sub = mqtt_modules['mqtt_subscribe']
    client = Mock()
    with patch.object(sub.requests, 'post') as post:
        sub.ao_receber_mensagem(client, None, message(mqtt_modules, topic='outro_topico'))
    post.assert_not_called()
    client.publish.assert_not_called()


@pytest.mark.parametrize('payload', [b'{', b'nao-e-json', b''])
def test_json_malformado_publica_erro_original(mqtt_modules, payload):
    sub, cfg = mqtt_modules['mqtt_subscribe'], mqtt_modules['mqtt_configs']
    client = Mock()
    with patch.object(sub.requests, 'post') as post:
        sub.ao_receber_mensagem(client, None, message(mqtt_modules, payload=payload))
    post.assert_not_called()
    client.publish.assert_called_once_with(cfg.TOPICO_CALLBACK, '500')


@pytest.mark.parametrize('failure', ['ConnectionError', 'Timeout', 'RequestException'])
def test_falhas_de_rede_publicam_500_com_mocks(mqtt_modules, failure):
    sub, cfg = mqtt_modules['mqtt_subscribe'], mqtt_modules['mqtt_configs']
    client = Mock()
    with patch.object(sub.requests, 'post', side_effect=getattr(sub.requests.exceptions, failure)('falha fictícia')):
        sub.ao_receber_mensagem(client, None, message(mqtt_modules))
    client.publish.assert_called_once_with(cfg.TOPICO_CALLBACK, '500')


def test_campos_ausentes_continuam_encaminhados_sem_traducao_automatica(mqtt_modules):
    sub, cfg = mqtt_modules['mqtt_subscribe'], mqtt_modules['mqtt_configs']
    client = Mock()
    with patch.object(sub.requests, 'post') as post:
        post.return_value.status_code = 403
        sub.ao_receber_mensagem(client, None, message(mqtt_modules, {'mac': 'AA:BB:CC:DD:EE:01', 'uid': 'a1b2c3d4'}))
    post.assert_called_once_with(cfg.API_URL, json={'uid': 'a1b2c3d4', 'date': None, 'mac_adress': None})
    client.publish.assert_called_once_with(cfg.TOPICO_CALLBACK, '401')


def test_limite_atual_utf8_invalido_nao_tem_tratamento(mqtt_modules):
    """Caracterização explícita da limitação, sem afirmar que existe recuperação."""
    with pytest.raises(UnicodeDecodeError):
        mqtt_modules['mqtt_subscribe'].ao_receber_mensagem(Mock(), None, message(mqtt_modules, payload=b'\xff'))


def test_limite_atual_json_lista_nao_tem_tratamento(mqtt_modules):
    with pytest.raises(AttributeError):
        mqtt_modules['mqtt_subscribe'].ao_receber_mensagem(Mock(), None, message(mqtt_modules, payload=b'[]'))


@pytest.mark.parametrize('code', [200, 401, 500])
def test_resposta_mqtt_preserva_topico_e_codigo_textual(mqtt_modules, code):
    client = Mock()
    mqtt_modules['mqtt_publish'].enviar_autorizacao(client, code)
    client.publish.assert_called_once_with(mqtt_modules['mqtt_configs'].TOPICO_CALLBACK, str(code))


def test_erro_na_publicacao_e_registrado_sem_escapar(mqtt_modules, capsys):
    client = Mock()
    client.publish.side_effect = RuntimeError('falha fictícia')
    mqtt_modules['mqtt_publish'].enviar_autorizacao(client, 200)
    assert '[PUBLISH] Erro ao enviar mensagem:' in capsys.readouterr().out


def test_cliente_inicia_callbacks_e_loop_originais(mqtt_modules):
    module, sub, cfg = mqtt_modules['mqtt_client'], mqtt_modules['mqtt_subscribe'], mqtt_modules['mqtt_configs']
    client = Mock()
    with patch.object(module.mqtt, 'Client', return_value=client) as constructor:
        module.iniciar_cliente()
    constructor.assert_called_once_with()
    assert client.on_connect == sub.ao_connectar
    assert client.on_message == sub.ao_receber_mensagem
    client.connect.assert_called_once_with(cfg.BROKER, cfg.PORTA_BROKER)
    client.loop_forever.assert_called_once_with()


def test_cliente_trata_falha_de_conexao(mqtt_modules, capsys):
    module = mqtt_modules['mqtt_client']
    client = Mock()
    client.connect.side_effect = OSError('broker ficticiamente indisponível')
    with patch.object(module.mqtt, 'Client', return_value=client):
        module.iniciar_cliente()
    client.loop_forever.assert_not_called()
    assert '[!] Erro ao conectar no broker:' in capsys.readouterr().out


def test_interrupcao_desconecta_cliente(mqtt_modules):
    module = mqtt_modules['mqtt_client']
    client = Mock()
    client.loop_forever.side_effect = KeyboardInterrupt
    with patch.object(module.mqtt, 'Client', return_value=client):
        module.iniciar_cliente()
    client.disconnect.assert_called_once_with()
