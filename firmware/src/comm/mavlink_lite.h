// Minimal MAVLink v2 for the flight-controller link.
//
// Sends:   HEARTBEAT, GPS_INPUT (MagNav position as an external GPS source),
//          mission upload (MISSION_COUNT / MISSION_ITEM_INT handshake)
// Receives: GLOBAL_POSITION_INT, VFR_HUD, MISSION_REQUEST(_INT), MISSION_ACK
// Only the fields this project needs are implemented; CRC_EXTRA values are
// from the common dialect.
#pragma once
#include <Arduino.h>

class MavlinkLite {
public:
    static constexpr uint8_t SYSID = 1, COMPID = 220;   // MAV_COMP_ID_GPS
    struct FcState {
        bool alive = false;
        double lat = 0, lon = 0;
        float relAlt = 0, vn = 0, ve = 0, groundspeed = 0, heading = 0;
        uint32_t lastMs = 0;
    };
    enum class Upload { Idle, Counting, Sending, Done, Failed };

    MavlinkLite(HardwareSerial& ser) : _ser(ser) {}
    void begin(int rxPin, int txPin, uint32_t baud = 57600) {
        _ser.begin(baud, SERIAL_8N1, rxPin, txPin);
    }

    // ---- outgoing ---------------------------------------------------------
    void sendHeartbeat() {
        uint8_t p[9] = {0};
        p[4] = 18;      // MAV_TYPE_ONBOARD_CONTROLLER
        p[5] = 8;       // MAV_AUTOPILOT_INVALID
        p[7] = 4;       // MAV_STATE_ACTIVE
        p[8] = 3;
        send(0, 50, p, 9);
    }

    // MagNav fix to the FC (ArduPilot: GPS_TYPE=14 MAV, PX4: not supported)
    void sendGpsInput(double lat, double lon, float altM, float horizAccM,
                      float vn, float ve, uint8_t fixType, uint8_t sats) {
        uint8_t p[65] = {0};
        uint64_t t = (uint64_t)micros();
        memcpy(p + 0, &t, 8);
        uint32_t wk = 0; memcpy(p + 8, &wk, 4);
        int32_t la = (int32_t)(lat * 1e7), lo = (int32_t)(lon * 1e7);
        memcpy(p + 12, &la, 4); memcpy(p + 16, &lo, 4);
        memcpy(p + 20, &altM, 4);
        float hdop = 1.0f, vdop = 1.5f, vd = 0, sacc = 0.5f, vacc = 5.0f;
        memcpy(p + 24, &hdop, 4); memcpy(p + 28, &vdop, 4);
        memcpy(p + 32, &vn, 4); memcpy(p + 36, &ve, 4); memcpy(p + 40, &vd, 4);
        memcpy(p + 44, &sacc, 4); memcpy(p + 48, &horizAccM, 4); memcpy(p + 52, &vacc, 4);
        uint16_t ignore = 1 | 8 | 128;      // ignore alt, vd, vert accuracy
        memcpy(p + 56, &ignore, 2);
        uint16_t week = 0; memcpy(p + 58, &week, 2);
        p[60] = 1;                          // gps_id
        p[61] = fixType;                    // 3 = 3D fix
        p[62] = sats;
        send(232, 151, p, 63);
    }

    struct Waypoint { double lat, lon; float altRel; };

    void startMissionUpload(const Waypoint* wps, int count) {
        _wps = wps; _nwp = count; _upload = Upload::Counting; _uploadMs = millis();
        sendMissionCount(count);
    }
    Upload uploadState() const { return _upload; }

    // ---- incoming ---------------------------------------------------------
    void poll() {
        while (_ser.available()) feed((uint8_t)_ser.read());
        if (_upload == Upload::Counting || _upload == Upload::Sending) {
            if (millis() - _uploadMs > 5000) _upload = Upload::Failed;
        }
    }
    const FcState& fc() const { return _fc; }

private:
    HardwareSerial& _ser;
    FcState _fc;
    uint8_t _seq = 0;
    // parser
    uint8_t _rx[300]; int _rxLen = 0, _need = 0;
    // mission upload
    const Waypoint* _wps = nullptr; int _nwp = 0;
    Upload _upload = Upload::Idle; uint32_t _uploadMs = 0;

    static uint16_t crcAccum(uint8_t d, uint16_t crc) {
        uint8_t tmp = d ^ (uint8_t)(crc & 0xff);
        tmp ^= (tmp << 4);
        return (crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4);
    }

    void send(uint32_t msgid, uint8_t crcExtra, const uint8_t* payload, uint8_t len) {
        uint8_t h[10] = {0xFD, len, 0, 0, _seq++, SYSID, COMPID,
                         (uint8_t)(msgid & 0xFF), (uint8_t)((msgid >> 8) & 0xFF),
                         (uint8_t)((msgid >> 16) & 0xFF)};
        uint16_t crc = 0xFFFF;
        for (int i = 1; i < 10; i++) crc = crcAccum(h[i], crc);
        for (int i = 0; i < len; i++) crc = crcAccum(payload[i], crc);
        crc = crcAccum(crcExtra, crc);
        _ser.write(h, 10);
        _ser.write(payload, len);
        _ser.write((uint8_t)(crc & 0xFF));
        _ser.write((uint8_t)(crc >> 8));
    }

    void sendMissionCount(uint16_t n) {
        uint8_t p[5] = {0};
        memcpy(p, &n, 2); p[2] = 1; p[3] = 1; p[4] = 0;   // target sys/comp, MISSION
        send(44, 221, p, 5);
    }

    void sendMissionItem(uint16_t seq) {
        uint8_t p[38] = {0};
        float hold = 0, accept = 5, pass = 0, yaw = NAN;
        int32_t x, y; float z; uint16_t cmd; uint8_t frame = 3;   // GLOBAL_RELATIVE_ALT
        if (seq == 0) {                    // home / takeoff placeholder
            x = (int32_t)(_wps[0].lat * 1e7); y = (int32_t)(_wps[0].lon * 1e7);
            z = _wps[0].altRel; cmd = 22;  // NAV_TAKEOFF
        } else {
            const Waypoint& w = _wps[seq];
            x = (int32_t)(w.lat * 1e7); y = (int32_t)(w.lon * 1e7); z = w.altRel;
            cmd = 16;                      // NAV_WAYPOINT
        }
        memcpy(p + 0, &hold, 4); memcpy(p + 4, &accept, 4);
        memcpy(p + 8, &pass, 4); memcpy(p + 12, &yaw, 4);
        memcpy(p + 16, &x, 4); memcpy(p + 20, &y, 4); memcpy(p + 24, &z, 4);
        memcpy(p + 28, &seq, 2); memcpy(p + 30, &cmd, 2);
        p[32] = 1; p[33] = 1; p[34] = frame; p[35] = (seq == 0); p[36] = 1; p[37] = 0;
        send(73, 38, p, 38);
    }

    void feed(uint8_t b) {
        if (_rxLen == 0) { if (b != 0xFD) return; _rx[_rxLen++] = b; return; }
        _rx[_rxLen++] = b;
        if (_rxLen == 2) _need = 10 + b + 2 + ((_rx[2] & 1) ? 13 : 0);
        if (_rxLen >= 3 && (_rx[2] & 1) && _rxLen == 3) _need = 10 + _rx[1] + 2 + 13;
        if (_rxLen >= 10 && _rxLen == _need) { handle(); _rxLen = 0; }
        if (_rxLen >= (int)sizeof(_rx)) _rxLen = 0;
    }

    void handle() {
        uint8_t len = _rx[1];
        uint32_t id = _rx[7] | (_rx[8] << 8) | ((uint32_t)_rx[9] << 16);
        const uint8_t* pl = _rx + 10;
        auto rd32 = [&](int off) { int32_t v = 0; if (off + 4 <= len) memcpy(&v, pl + off, 4); return v; };
        auto rdf = [&](int off) { float v = 0; if (off + 4 <= len) memcpy(&v, pl + off, 4); return v; };
        auto rd16 = [&](int off) { int16_t v = 0; if (off + 2 <= len) memcpy(&v, pl + off, 2); return v; };
        switch (id) {
        case 33:   // GLOBAL_POSITION_INT
            _fc.lat = rd32(4) / 1e7; _fc.lon = rd32(8) / 1e7;
            _fc.relAlt = rd32(16) / 1000.0f;
            _fc.vn = rd16(20) / 100.0f; _fc.ve = rd16(22) / 100.0f;
            _fc.heading = (uint16_t)rd16(26) / 100.0f;
            _fc.alive = true; _fc.lastMs = millis();
            break;
        case 74:   // VFR_HUD
            _fc.groundspeed = rdf(4);
            break;
        case 51:   // MISSION_REQUEST_INT
        case 40: { // MISSION_REQUEST (legacy)
            uint16_t seq = (uint16_t)rd16(0);
            if (_upload == Upload::Counting || _upload == Upload::Sending) {
                _upload = Upload::Sending; _uploadMs = millis();
                if (seq < _nwp) sendMissionItem(seq);
            }
            break;
        }
        case 47:   // MISSION_ACK
            if (_upload == Upload::Sending || _upload == Upload::Counting)
                _upload = (len > 2 && pl[2] == 0) ? Upload::Done : Upload::Failed;
            break;
        default: break;
        }
    }
};
