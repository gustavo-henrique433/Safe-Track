#include <WiFi.h> // Use <ESP8266WiFi.h> se for um ESP8266

const char* ssid = "open-ic";
const char* password = "Nc?dKaB3N9Hz";

const char* hostIP = "177.220.85.177"; // IP que você quer testar
const int porta = 5001;                // Porta que você quer testar

void setup() {
  Serial.begin(115200);
  
  // Conecta no Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Conectando ao WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado à rede!");

  // Cria o cliente para testar a conexão
  WiFiClient client;

  Serial.printf("Testando conexão em %s na porta %d...\n", hostIP, porta);

  // O comando client.connect() é o equivalente ao "nc -z"
  if (client.connect(hostIP, porta)) {
    Serial.println("SUCESSO: A porta está ABERTA! [Equivalente ao succeeded]");
    client.stop(); // Fecha a conexão já que era só um teste
  } else {
    Serial.println("FALHA: A porta está FECHADA ou bloqueada.");
  }
}

void loop() {
  // Nada para fazer aqui, o teste rodou uma vez no setup
}