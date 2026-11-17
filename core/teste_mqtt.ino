#include <WiFi.h>
#include <PubSubClient.h>
#include <SPI.h> 
#include <MFRC522.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include "logo.h"

#define SS_PIN 5 //Pino usado para conexão e conversa entre o ESP32 e o RFID
#define RST_PIN 27 //Pino do Reset do RFID

const int pin_Buzzer = 12;

const char* ssid = "open-ic";
const char* password = "Nc?dKaB3N9Hz";
const char* mqtt_server = "test.mosquitto.org";

WiFiClient Esp_Safe_Track; //Nome do meu ESP32 aqui vou colocar como Safe-Track
PubSubClient client(Esp_Safe_Track); //Logo meu client foi definido como Esp_Safe_Track, no futuro devo mudar cada client de acordo com  o local

MFRC522 mfrc522(SS_PIN, RST_PIN); // Cria a instância do sensor
Adafruit_SH1106G display = Adafruit_SH1106G(128, 64, &Wire, -1);


void callback(char* topic, byte* payload, unsigned int length) { //Parcialmente Pronto (Lembrar de implementar Display :) )
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");

  String resposta_API = "";
  for (int i = 0; i < lenght, i++) {
    resposta_API += (char)payload[i];
  }

  Serial.println(resposta_API)

  if (resposta_API == "200") {
    Serial.println("UID enviada com sucesso !!");
    digitalWrite(pin_Buzzer, HIGH);
    delay(1000);
    digitalWrite(pin_Buzzer, LOW);
    
  }

  else {
    Serial.println("Erro no envio do UID !!");
  }
}

void set_wifi() {

  Serial.print("Conectando-se ao WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado !!");
  configTime(-10800, 0, "pool.ntp.org");
  Serial.print("IP do ESP32: ");
  Serial.println(WiFi.localIP());
  Serial.print("Endereço Mac: ");
  Serial.println(WiFi.macAddress());
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP8266Client-";
    clientId += String(random(0xffff), HEX);
    if (client.connect("Esp_Safe_Track")) {
      Serial.println("connected");
      client.subscribe("ESP_resposta_API"); //Topico para onde a Tag é enviada
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}


void iniciar_RFID() {
  SPI.begin();
  mfrc522.PCD_Init();
}

void Ler_RFID() {
  String uid_convertido = "";

  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  if (!mfrc522.PICC_ReadCardSerial()) {
    return; 
  }

  for (byte x = 0; x < mfrc522.uid.size; x++) {
    uid_convertido += String(mfrc522.uid.uidByte[x], HEX);
  }

  Serial.print("Cartão lido: ");
  //digitalWrite(Led_Verde, HIGH);
  Serial.println(uid_convertido);

  String mac = WiFi.macAddress();
    String payload = "{\"mac\":\"" + mac + "\", \"uid\":\"" + uid_convertido + "\"}";
    client.publish("ESP_envia_tag", payload.c_str());

  mfrc522.PICC_HaltA();
  delay(1000);

}

void setup() {

  Serial.begin(115200);
  set_wifi();
  iniciar_RFID();

  pinMode(pin_Buzzer, OUTPUT);

  delay(250); 
  display.begin(0x3C, true); 
  display.clearDisplay();

  delay(5000); 

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.println(" SAFE-TRACK ");
  display.display();

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void loop() {

 if (!client.connected()) {
    reconnect();
  }
  
  client.loop(); 

  if (WiFi.status() == WL_CONNECTED) {
    Ler_RFID();
  }
}