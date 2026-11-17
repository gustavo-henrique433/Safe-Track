BROKER = "test.mosquitto.org" ##Aqui eu insiro meu Broker, no meu caso é o mosquitto 
PORTA_BROKER = 1883 ## Porta em que o Broker vai trabalhar
TOPICO_ESCUTA = "ESP_envia_tag" ##Topico em que o ESP32 envia a tag RFID 
TOPICO_CALLBACK = "Resposta_API" ##Topico em que a API dá a respota ao esp32 na função Callback

API_URL = "http://143.106.73.80:5001/cadastrar_rfid" ##Rota da API que recebe a UID









