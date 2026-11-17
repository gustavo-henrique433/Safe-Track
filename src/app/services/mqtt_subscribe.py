import json
import requests
import mqtt_configs
import mqtt_publish

def ao_connectar(client, userdata, flags, rc):
    client.subscribe(mqtt_configs.TOPICO_ESCUTA)

def ao_receber_mensagem(client, userdata, msg):
    topico = msg.topic
    payload_str = msg.payload.decode('utf-8')
    
    if topico == mqtt_configs.TOPICO_ESCUTA:
        try:
            dados = json.loads(payload_str)
            uid = dados.get('uid')
            date = dados.get('date')
            mac_adress = dados.get('mac_adress')
            
            print(f"\n[MQTT] Tag {uid} recebida... Repassando para a API...")

            pacote_para_api = {
                "uid": uid,
                "date": date,
                "mac_adress": mac_adress
            }
            
           
            resposta = requests.post(mqtt_configs.API_URL, json=pacote_para_api)
            print(f"\nPayload recebido do ESP32 - {pacote_para_api}")
            
           
            if resposta.status_code == 200 or resposta.status_code == 201:
                print("\n[MQTT] Sucesso no envio da tag.")
                mqtt_publish.enviar_autorizacao(client, 200)
            else:
                print(f"[MQTT] Acesso negado: {resposta.status_code}")
                mqtt_publish.enviar_autorizacao(client, 401)
                
        except json.JSONDecodeError:
            print("[MQTT] Erro de formato JSON.")
            mqtt_publish.enviar_autorizacao(client, 500)
            
        except requests.exceptions.RequestException as e:
            print(f"[MQTT] Falha ao alcancar a API: {e}")
            mqtt_publish.enviar_autorizacao(client, 500)