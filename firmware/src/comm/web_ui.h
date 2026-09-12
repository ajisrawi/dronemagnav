// WiFi access point + HTTP API for the phone UI.
//
// AP: SSID "DroneMagNav", password "magnav123", page at http://192.168.4.1/
// The page itself (/www/index.html) and the offline coastline map
// (/maps/coast.json) live on the SD card; a tiny embedded fallback page is
// served if the card is missing.
#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SD_MMC.h>
#include "../nav/geo.h"

struct NavStatus {
    const char* mode;        // "GNSS", "MAGNAV", "INIT"
    double lat, lon;
    float alt, sigmaM, fieldNt, anomNt, headingDeg;
    bool fcAlive, sdOk, mapOk, wmmOk, gnssFix;
    uint8_t sats;
    int particles;
};

class WebUI {
public:
    using StatusFn = void (*)(NavStatus&);
    using UploadFn = bool (*)(const double* lats, const double* lons, int n, float altRel);
    using CalFn = void (*)(bool start);
    using InitFn = void (*)(double lat, double lon);
    using AnomFn = float (*)(double lat, double lon);

    static constexpr int MAXWP = 200;

    void begin(StatusFn st, UploadFn up, CalFn cal, InitFn init, AnomFn anom) {
        _status = st; _upload = up; _cal = cal; _init = init; _anom = anom;
        WiFi.mode(WIFI_AP);
        WiFi.softAP("DroneMagNav", "magnav123");
        _srv.on("/", HTTP_GET, [this] { servePage(); });
        _srv.on("/api/status", HTTP_GET, [this] { apiStatus(); });
        _srv.on("/api/route", HTTP_GET, [this] { apiRoute(); });
        _srv.on("/api/upload", HTTP_POST, [this] { apiUpload(); });
        _srv.on("/api/coast", HTTP_GET, [this] { streamFile("/maps/coast.json", "application/json"); });
        _srv.on("/api/anom", HTTP_GET, [this] { apiAnom(); });
        _srv.on("/api/cal", HTTP_POST, [this] { _cal(_srv.arg("start") == "1"); ok(); });
        _srv.on("/api/init", HTTP_POST, [this] {
            _init(_srv.arg("lat").toDouble(), _srv.arg("lon").toDouble()); ok(); });
        _srv.onNotFound([this] { _srv.send(404, "text/plain", "not found"); });
        _srv.begin();
    }
    void poll() { _srv.handleClient(); }

    // last computed route (used by main for upload)
    double wpLat[MAXWP], wpLon[MAXWP];
    int nwp = 0;
    float routeAlt = 50;

private:
    WebServer _srv{80};
    StatusFn _status = nullptr; UploadFn _upload = nullptr; CalFn _cal = nullptr;
    InitFn _init = nullptr; AnomFn _anom = nullptr;

    void ok() { _srv.send(200, "application/json", "{\"ok\":true}"); }

    void servePage() {
        if (!streamFile("/www/index.html", "text/html")) {
            _srv.send(200, "text/html",
                "<html><body style='font-family:sans-serif'><h2>DroneMagNav</h2>"
                "<p>SD card missing or /www/index.html not found.</p>"
                "<p>Run tools/prepare_sd.py and insert the card.</p></body></html>");
        }
    }

    bool streamFile(const char* path, const char* type) {
        File f = SD_MMC.open(path, "r");
        if (!f) return false;
        _srv.streamFile(f, type);
        f.close();
        return true;
    }

    void apiStatus() {
        NavStatus s{};
        _status(s);
        char buf[420];
        snprintf(buf, sizeof(buf),
            "{\"mode\":\"%s\",\"lat\":%.7f,\"lon\":%.7f,\"alt\":%.1f,\"sigma\":%.1f,"
            "\"field\":%.1f,\"anom\":%.1f,\"hdg\":%.1f,\"fc\":%d,\"sd\":%d,\"map\":%d,"
            "\"wmm\":%d,\"fix\":%d,\"sats\":%d,\"particles\":%d,\"nwp\":%d}",
            s.mode, s.lat, s.lon, s.alt, s.sigmaM, s.fieldNt, s.anomNt, s.headingDeg,
            s.fcAlive, s.sdOk, s.mapOk, s.wmmOk, s.gnssFix, s.sats, s.particles, nwp);
        _srv.send(200, "application/json", buf);
    }

    // GET /api/route?lat1&lon1&lat2&lon2&alt&spacing  -> great-circle waypoints
    void apiRoute() {
        double la1 = _srv.arg("lat1").toDouble(), lo1 = _srv.arg("lon1").toDouble();
        double la2 = _srv.arg("lat2").toDouble(), lo2 = _srv.arg("lon2").toDouble();
        float spacing = _srv.hasArg("spacing") ? _srv.arg("spacing").toFloat() : 500.0f;
        routeAlt = _srv.hasArg("alt") ? _srv.arg("alt").toFloat() : 50.0f;
        double dist = geo::haversine(la1, lo1, la2, lo2);
        double brg = geo::bearing(la1, lo1, la2, lo2);
        int n = (int)ceil(dist / spacing) + 1;
        if (n < 2) n = 2;
        if (n > MAXWP) n = MAXWP;
        String out = "{\"distance_m\":" + String(dist, 1) + ",\"bearing_deg\":" +
                     String(brg, 1) + ",\"alt_rel\":" + String(routeAlt, 1) + ",\"wps\":[";
        for (int i = 0; i < n; i++) {
            double f = (double)i / (n - 1), la, lo;
            geo::intermediate(la1, lo1, la2, lo2, f, la, lo);
            wpLat[i] = la; wpLon[i] = lo;
            out += (i ? "," : "") + String("[") + String(la, 7) + "," + String(lo, 7) + "]";
        }
        nwp = n;
        out += "]}";
        _srv.send(200, "application/json", out);
    }

    void apiUpload() {
        if (nwp < 2) { _srv.send(400, "application/json", "{\"ok\":false,\"err\":\"no route\"}"); return; }
        bool r = _upload(wpLat, wpLon, nwp, routeAlt);
        _srv.send(200, "application/json", r ? "{\"ok\":true}" : "{\"ok\":false,\"err\":\"fc\"}");
    }

    // GET /api/anom?lat&lon&span(deg)&n -> n x n grid of anomaly values (nT)
    void apiAnom() {
        double lat = _srv.arg("lat").toDouble(), lon = _srv.arg("lon").toDouble();
        double span = _srv.hasArg("span") ? _srv.arg("span").toDouble() : 2.0;
        int n = _srv.hasArg("n") ? _srv.arg("n").toInt() : 32;
        if (n > 48) n = 48;
        String out = "{\"lat0\":" + String(lat - span / 2, 5) + ",\"lon0\":" +
                     String(lon - span / 2, 5) + ",\"span\":" + String(span, 5) +
                     ",\"n\":" + String(n) + ",\"v\":[";
        for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++) {
                float v = _anom(lat - span / 2 + span * (j + 0.5) / n,
                                lon - span / 2 + span * (i + 0.5) / n);
                out += ((i || j) ? "," : "") + (isnan(v) ? String("null") : String((int)v));
            }
        out += "]}";
        _srv.send(200, "application/json", out);
    }
};
