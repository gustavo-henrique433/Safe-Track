import mqtt_configs
import json


def enviar_autorizacao(cliente_ativo, codigo_status):
    try:
        cliente_ativo.publish(mqtt_configs.TOPICO_CALLBACK, str(codigo_status))
        print(f"\n[PUBLISH] status da reqsuisição {codigo_status} para {mqtt_configs.TOPICO_CALLBACK}")

    except Exception as e:
        print(f"[PUBLISH] Erro ao enviar mensagem: {e}")    

    



