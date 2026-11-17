//Arrumar a captação de data pois o dia de envio de dados está fixo
#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>  //Protocolo no qual o ESP32 conversa com o RC522 
#include <MFRC522.h> //Biblioteca do RFID RC522
// #include <time.h>
#include <ESP32Servo.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include "logo.h"

#define SS_PIN 5 //Pino usado para conexão e conversa entre o ESP32 e o RFID
#define RST_PIN 27 //Pino do Reset do RFID

const int Led_Vermelho = 13; //Aqui eu estou declarando o led vermelho como uma "constante" pino 13
const int Led_Verde = 12;  //Aqui eu estou declarando o led verde como uma "constante" pino 12
//const int PINO_BUZZER = 15;
 
const char* ssid = "open-ic"; //IP da Rede
const char* password = "Nc?dKaB3N9Hz"; //Senha da rede

const char* serverUrl = "http://143.106.73.80:5001/acessar_porta"; //URL com IP e endereço para o envio de dados, é aqui onde eu conecto ele a API

Servo myservo;

MFRC522 mfrc522(SS_PIN, RST_PIN); // Cria a instância do sensor
Adafruit_SH1106G display = Adafruit_SH1106G(128, 64, &Wire, -1);

// struct tm timeinfo;

int pos = 0;
int servoPin = 27;

void setup() {

  pinMode(Led_Vermelho, OUTPUT);
  pinMode(Led_Verde, OUTPUT);
  
  Serial.begin(115200); //Inicializa o monitor serial

  SPI.begin(); //Inicializa o barramento SPI
  mfrc522.PCD_Init(); //Inicializa o sensor no caso é o RC522
  delay(250); 
  display.begin(0x3C, true); 
  display.clearDisplay();

  display.drawBitmap(0, 0, epd_bitmap_Logo_anonymous, 128, 64, SH110X_WHITE);
  display.display();

  delay(5000); 

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.println(" SAFE-TRACK ");
  display.display();

  myservo.setPeriodHertz(50); // standard 50 hz servo
  myservo.attach(servoPin, 500, 2400);
  myservo.write(0);

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

  mfrc522.PICC_HaltA();

  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;

    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"uid_solicitante\":\"" + uid_convertido + "\",\"date\":\"2026-03-19\",\"local\":1}";

    int httpResponseCode = http.POST(json);

    Serial.print("Código HTTP: ");
    Serial.println(httpResponseCode);
    

    if (httpResponseCode == 200) {

      String response = http.getString();

      digitalWrite(Led_Verde, HIGH);
      //digitalWrite(PINO_BUZZER, HIGH);
      delay(2000);
      //digitalWrite(PINO_BUZZER, LOW);


      Serial.println("Resposta:");
      Serial.println(response);

      display.clearDisplay();
      display.setCursor(0, 0);
      display.println(response);
      display.display();

      for (pos = 0; pos <= 180; pos += 1) {

        myservo.write(pos);

        delay(15);
      }

      delay(200);

      myservo.write(0);
      delay(2000);
      display.clearDisplay();
     

    } else {

      digitalWrite(Led_Vermelho, HIGH);
      Serial.print("Erro: ");
      Serial.print("Acesso negado !!");
      Serial.println(http.errorToString(httpResponseCode));
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Acesso negado !!");
      display.println(httpResponseCode);
      display.display();
      delay(2000);
      display.clearDisplay();
    }

    http.end();

  } else {

    Serial.println("WiFi desconectado");
    digitalWrite(Led_Vermelho, HIGH);
  }
}