/*
This used to be the old library for serial communication, now we use SerialDevice.
This is now DEPRECATED, but could contain usable snippets of code
*/

#pragma once
#include <Arduino.h>

#define PSP_START_BYTE 0x01
#define PSP_END_BYTE 0x02
#define PSP_MAX_PACK_LENGTH 200
#define PSP_TIMEOUTms 1000
#define PSP_HEADER_SIZE 2

struct BaseSerPacket {
    u8_t category;
    byte data[]; 
};

typedef void (*PacketHandler)(BaseSerPacket* pck);

enum recvState {
  LOOKING_FOR_START,
  WAITING_FOR_HEADER,
  WAITING_FOR_PACKET
};

enum processErr {
    OK = 0,
    STREAM_EMPTY = -1,
    RESYNC_TIMEOUT = -2,
    STREAM_PROCESS_ERROR = -3,
    WRONG_START_BYTE = -4,
    NOT_ENOUGH_BYTES = -5,
    INVALID_HEADER = -6
};

// default packets IDs (reserved 0-10)

#define PSPPACKID_AUTH_RQST 0x04
#define PSPPACKID_AUTH_RESP 0x03
#define PSPPACKID_DIAGNOSTIC 0x01

// error codes (reserved 0-10)

#define PSP_ERR_UNKNOWN_PACKETID 0x00


// default handlers for internal packets

void handleAuthRqst(BaseSerPacket* pck) {
    pspdev.send_packet(PSPPACKID_AUTH_RESP, String(PSP_DEVICE_NAME));
}

/// @brief Allows interaction over a serial stream in a packet oriented way. Uses PSP (Packetized Serial Protocol) and expects the end device to 
/// be using PSP as well. This class implements a basic auto re-synchronization algorithm to ensure that if synchronism is lost due to incorrectly
/// formatted inbound data, it will eventually be regained automatically (but some packets might get lost).  
class packetizedSerial {
private:
    recvState state = LOOKING_FOR_START;
    uint16_t last_header;
    bool is_packet_valid = false;
    bool can_receive = true;
    String device_name; // used for authentication with the other device (who am I talking to?)

    HardwareSerial* ser;
    static const int MAX_HANDLERS = 256;  // category IDs are bytes
    PacketHandler handlers[MAX_HANDLERS] = {nullptr};

public:
    byte buffer[PSP_MAX_PACK_LENGTH];

    packetizedSerial(HardwareSerial& serial, const String& device_name = "defaultPSPdevice") 
        : ser(&serial), device_name(device_name) {
            on(PSPPACKID_AUTH_RQST, handleAuthRqst); // binds default auth handler
        }

    void begin(unsigned long baud) {
        serial.begin(baud);
    }

    // registers a handler function for a specific packet category
    void on(uint8_t category, PacketHandler handler) {
        if (category < MAX_HANDLERS) {
            handlers[category] = handler;
        }
    }

    // polls the serial stream and calls the appropriate handler if a full packet has been received
    void poll() {
        while (recv_packet()) {
            BaseSerPacket* pck = get_last_packet();
            if (pck && handlers[pck->category]) {
                handlers[pck->category](pck);
            } else {
                // send diagnostic if unknown
                send_packet(PSPPACKID_DIAGNOSTIC, PSP_ERR_UNKNOWN_PACKETID);
            }
        }
    }

    auto send_packet(uint8_t category, const byte *buffer, size_t size) {
        ser->write(PSP_START_BYTE);
        write_header(size + 1); //writes header (adds 1 for category byte)
        ser->write(category);
        auto out = ser->write(buffer, size);
        ser->write(PSP_END_BYTE);
        return out;
    }

    auto send_packet(uint8_t category, const String &s) {
        return send_packet(category, (byte*)s.c_str(), s.length());
    }

    auto send_packet(uint8_t category, int n) {
        return send_packet(category, (byte*)&n, sizeof(n));
    }

    bool packet_is_valid() {return is_packet_valid;}

    /// @brief processes the serial stream.
    /// @return true if a packet has been received and is ready to be consumed from the buffer. Only returns true once per packet
    bool recv_packet() {
        bool out = process_stream() == 0;
        return out && is_packet_valid;
    }

    /// @brief returns a pointer to the packet data buffer cast to a BaseSerPacket pointer
    inline BaseSerPacket* get_last_packet() {return (BaseSerPacket*)buffer;}

private:
    void write_header(size_t length) {
        // header gets truncated to the HEADER_SIZEnth byte
        for (int i = 0; i < PSP_HEADER_SIZE; i++) {
            ser->write(((uint8_t*)&length)[i]);
        }
    }
    
    inline bool is_header_valid(u16_t length) {return length <= PSP_MAX_PACK_LENGTH;}

    bool resync() {
        //Serial.println("resyncking");
        const uint16_t bytes_available = ser->available();
        const auto start_time = millis();

        for (int i = 0; i < bytes_available; i++) {
            {if ((millis() - start_time) > PSP_TIMEOUTms) return false;} //has been looking for start for too long, we return so the main program doesnt hang
            
            if (ser->peek() == PSP_START_BYTE) {
                return true; // start byte has been found, and will be returned by the next call to read()  
            }
            ser->read(); // advances 1 byte
        }
        return false;
    }

    /// @brief Processes the inbound serial data stream and implements a basic way of resynchronizing packets if sync is lost due to 
    /// incorrectly formatted data (data not following PSP standards)
    /// @return error code of process of type processErr
    int process_stream() {
        //Serial.print("STATE");
        //Serial.println(state);

        //Serial.println(ser->available());
        if (ser->available() == 0) return processErr::STREAM_EMPTY; // if no data is left to be processed, returns right away

        switch (state) {
        // NOTE the missing break statements are intentional to allow the whole function to execute in one go if every condition is met

        case LOOKING_FOR_START:
            // if function fails to obtain full packet and returns, packet will be marked as invalid
            is_packet_valid = false;

            // resynchronize if the next byte wasn't the start byte
            if (ser->peek() != PSP_START_BYTE)    {
                if (!resync()) return processErr::RESYNC_TIMEOUT;  //timeout expires, still hasn't managed to find start byte
                //Serial.println("Resync success.");
            }
            
            // at this point the next call to ser->read() should always return the start byte
            if (ser->read() != PSP_START_BYTE) return processErr::WRONG_START_BYTE;

            state = WAITING_FOR_HEADER;
            //Serial.println("looking for start finished");
        
        case WAITING_FOR_HEADER:
            if (ser->available() < PSP_HEADER_SIZE) return processErr::NOT_ENOUGH_BYTES; // returns if there aren't enough bytes yet.
            
            ser->readBytes((char*)&last_header, sizeof(last_header)); //reads header (expects little endian)
            if (is_header_valid(last_header)) {
                //Serial.println("Header valid.");
                state = WAITING_FOR_PACKET;
            } else {
                //Serial.println("Header INvalid.");
                state = LOOKING_FOR_START;
                is_packet_valid = false;
                return processErr::INVALID_HEADER;
            }
            //Serial.println("waiting gheader finish");

        
        case WAITING_FOR_PACKET:
            if (ser->available() < last_header + 1) return processErr::NOT_ENOUGH_BYTES; // returns if there aren't enough bytes yet (+1 to account for end byte)

            ser->readBytes((char*)buffer, last_header);
            u8_t end_byte = ser->read(); // should never return -1 since we checked if there were enough bytes at the beggining

            state = LOOKING_FOR_START;
            if (end_byte == PSP_END_BYTE) is_packet_valid = true;
            else is_packet_valid = false;
            //Serial.print("END valid: ");
            //Serial.println(end_byte);
            
            //Serial.println("waiting packet finish");

            return OK;
        }
        
        return processErr::STREAM_PROCESS_ERROR;
    }
    
};




/*SAMPLE CODE

packetizedSerial dev(Serial);

void setup() {    
    Serial.begin(9600);
}

void loop() {

    if (dev.recv_packet()) {
       int category = ((BaseSerPacket*)dev.buffer)->category;
       dev.send_packet(category, ((BaseSerPacket*)dev.buffer)->data, 7);
    };

    delay(5);
}*/