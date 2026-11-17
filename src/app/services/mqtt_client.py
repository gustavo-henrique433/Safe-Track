import paho.mqtt.client as mqtt
import mqtt_configs
import mqtt_subscribe



def iniciar_cliente():
 
    cliente = mqtt.Client()

    cliente.on_connect = mqtt_subscribe.ao_connectar
    cliente.on_message = mqtt_subscribe.ao_receber_mensagem

    print(f"\n[*] Conectando ao broker {mqtt_configs.BROKER} na porta {mqtt_configs.PORTA_BROKER}...")

    try:
   
        cliente.connect(mqtt_configs.BROKER, mqtt_configs.PORTA_BROKER)
        
        cliente.loop_forever()
        
    except KeyboardInterrupt:
        print("\n[*] Desconectando do broker MQTT...")
        cliente.disconnect()
    except Exception as e:
        print(f"[!] Erro ao conectar no broker: {e}")

if __name__ == "__main__":
    iniciar_cliente()