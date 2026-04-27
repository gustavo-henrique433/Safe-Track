#include <WiFi.h>
#include <HTTPClient.h>
//#include < SPI.h > 
#include <MFRC522.h> //Biblioteca do RFID RC522
// #include <time.h>

#define SS_PIN 5 //Pino usado para conexão e conversa entre o ESP32 e o RFID
#define RST_PIN 27 //Pino do Reset do RFID

const int  Led_Vermelho = 13; //Aqui eu estou declarando o led vermelho como uma "constante" pino 13
const int Led_Verde = 12;  //Aqui eu estou declarando o led verde como uma "constante" pino 12
 
const char* ssid = "********"; //IP da Rede
const char* password = "********"; //Senha da rede

const char* serverUrl = "http://***********/cadastrar_rfid"; //URL com IP e endereço para o envio de dados, é aqui  onde eu conecto ele a API


MFRC522 mfrc522(SS_PIN, RST_PIN); // Cria a instância do sensor

// struct tm timeinfo;


void setup() {

  pinMode (Led_Vermelho, OUTPUT);
  pinMode (Led_Verde, OUTPUT);
  
  Serial.begin(115200); //Inicializa o monitor serial

  SPI.begin(); //Inicializa o barramento SPI
  mfrc522.PCD_Init(); //Inicializa o sensor no caso é o RC522

  WiFi.begin(ssid, password); //Aqui eu faço a conexão com a minha rede wifi
  Serial.print("Iniciando conexão com a rede!!");

    while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConectado !!");
  configTime(-10800, 0, "pool.ntp.org");
  Serial.print("IP do ESP32: ");
  Serial.println(WiFi.localIP());
}

void loop() {

  digitalWrite(Led_Verde, LOW);
  digitalWrite(Led_Vermelho, LOW);
  String uid_convertido = "";

  if  ( ! mfrc522.PICC_IsNewCardPresent()) {
      return;
    }

    if ( ! mfrc522.PICC_ReadCardSerial()) {
      return; 
    }

    for (byte x = 0; x < mfrc522.uid.size; x++) {
      
      uid_convertido +=  String(mfrc522.uid.uidByte[x], HEX) ;

    }

    Serial.print("Cartão lido: ");
    Serial.println(uid_convertido);
    mfrc522.PICC_HaltA();

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"uid\":\"" + uid_convertido + "\",\"date\":\"2026-03-19\"}";

     int httpResponseCode = http.POST(json);

    Serial.print("Código HTTP: ");
    Serial.println(httpResponseCode);

    if (httpResponseCode > 0) {
      String response = http.getString();
      digitalWrite(Led_Verde, HIGH);
      Serial.println("Resposta:");
      Serial.println(response);
    } else {
      digitalWrite(Led_Vermelho, HIGH);
      Serial.print("Erro: ");
      Serial.println(http.errorToString(httpResponseCode));
    }

    http.end();

  } 
  else {
    Serial.println("WiFi desconectado");
  }
 
 }






