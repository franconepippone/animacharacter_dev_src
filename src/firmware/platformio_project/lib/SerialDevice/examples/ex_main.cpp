#include "SerialDevice.h"
#include <Arduino.h>
#include <ezLED.h>

SerialDevice dev(Serial, "ANIM1:HEAD");

ezLED led(LED_BUILTIN);

double y;

struct {
  char phrase[32] = "Ciao sono paolo";
} my_pack_format;


// handler for packets of id 20
void triggerIdent(SerialDevice* dev) {
  _debug_blink_builtin(20);
  dev->requestPeername(1000);
  dev->sendPacket(dev->peerName);
  //dev->sendBytes((byte*)dev->peerName, 5, 3);
  //memcpy(dev->txf.packet.txBuff, resp, 5);
  //auto n = dev->txf.sendData(5, 3);
  delay(500);
}

void setup()
{
  pinMode(13, OUTPUT);
  dev.begin(115200);
  y = 4.5;
  led.blink(500, 800);
  // binds cb
}



void loop()
{
  dev.poll();
  led.loop();

  

  if (false) {
    char msg[30];
    dev.recvPacket(msg);
    //blink(2);
    delay(500);

    char resp[5] = {'A', 'B', 'C', 'D', 'E'};
    //dev.sendBytes((byte*)resp, 5, 3);
    memcpy(dev.txf.packet.txBuff, resp, 5);
    auto n = dev.txf.sendData(5, 3);
    //dev.sendPacket(resp, 3);

    _debug_blink_builtin(n);

    //myTransfer.packet.rxObj(ciccio);
    //uint8_t id = myTransfer.currentPacketID();
    
    //myTransfer.packet.txBuff
    //delay(500);
    //myTransfer.txObj(my_pack_format);
    //myTransfer.sendData(sizeof(my_pack_format), 5);

  }
  y += 1;
}