// DroneMagNav firmware - ESP32-S3
//
// Sensor loop (100 Hz IMU, 80 Hz mag, 10 Hz baro) -> attitude (complementary
// filter) -> Tolles-Lawson compensated scalar field -> MagNav particle filter
// against WMM core field + WDMAM anomaly map from the SD card. GNSS initialises
// and (when present) benchmarks the filter; when GNSS is lost the MagNav
// estimate is fed to the flight controller as GPS_INPUT. Phone UI over WiFi.
#include <Arduino.h>
#include <SPI.h>
#include <SD_MMC.h>
#include "pins.h"
#include "sensors/bmi088.h"
#include "sensors/lis3mdl.h"
#include "sensors/bmp280.h"
#include "nav/geo.h"
#include "nav/wmm.h"
#include "nav/wdmam_map.h"
#include "nav/tolles_lawson.h"
#include "nav/particle_filter.h"
#include "comm/gnss.h"
#include "comm/mavlink_lite.h"
#include "comm/web_ui.h"

SPIClass spiBus(FSPI);
BMI088 imu(spiBus, PIN_CS_ACC, PIN_CS_GYR);
LIS3MDL mag(spiBus, PIN_CS_MAG);
BMP280 baro(spiBus, PIN_CS_BARO);
GNSS gnss(Serial1);
MavlinkLite mav(Serial2);
WMM wmm;
AnomalyMap worldMap, localMap;
TollesLawson tl;
MagNavPF pf;
WebUI web;

static bool sdOk = false, mapOk = false, wmmOk = false;
static bool magnavMode = false;         // true when GNSS lost / denied
static bool calibrating = false;
static float roll = 0, pitch = 0, yaw = 0;              // rad
static float bxf = 0, byf = 0, bzf = 0, bxPrev = 0, byPrev = 0, bzPrev = 0;
static float scalarComp = 0, anomAtEst = 0, altBaroM = 0, qnh = 101325;
static double estLat = 0, estLon = 0; static float estSigma = 9999, estBias = 0;
static uint32_t tLastImu = 0, tLastMag = 0, tLastBaro = 0, tLastPf = 0, tLastHb = 0,
                tLastGpsIn = 0;
static float vnDR = 0, veDR = 0;                        // dead-reckoning velocity

static float decimalYear() { return 2026.7f; }         // replace with RTC/GNSS date

// ---------------------------------------------------------------- attitude
static void attitudeUpdate(float ax, float ay, float az, float gx, float gy,
                           float gz, float dt) {
    roll += gx * dt; pitch += gy * dt; yaw += gz * dt;
    float an = sqrtf(ax * ax + ay * ay + az * az);
    if (an > 8.0f && an < 11.5f) {                    // near 1 g: trust accel
        float rollA = atan2f(ay, az), pitchA = atan2f(-ax, sqrtf(ay * ay + az * az));
        roll = 0.98f * roll + 0.02f * rollA;
        pitch = 0.98f * pitch + 0.02f * pitchA;
    }
    // tilt-compensated magnetic heading (WMM declination applied in caller)
    float mx = bxf * cosf(pitch) + bzf * sinf(pitch);
    float my = bxf * sinf(roll) * sinf(pitch) + byf * cosf(roll) - bzf * sinf(roll) * cosf(pitch);
    float yawMag = atan2f(-my, mx);
    yaw = 0.95f * yaw + 0.05f * yawMag;
}

// ---------------------------------------------------------------- callbacks
static void statusCb(NavStatus& s) {
    s.mode = calibrating ? "CAL" : (magnavMode ? "MAGNAV" : (gnss.fresh() ? "GNSS" : "INIT"));
    s.lat = estLat; s.lon = estLon; s.alt = altBaroM; s.sigmaM = estSigma;
    s.fieldNt = scalarComp; s.anomNt = anomAtEst; s.headingDeg = fmodf(yaw * 57.2958f + 360, 360);
    s.fcAlive = mav.fc().alive && (millis() - mav.fc().lastMs) < 3000;
    s.sdOk = sdOk; s.mapOk = mapOk; s.wmmOk = wmmOk;
    s.gnssFix = gnss.fresh(); s.sats = gnss.fix().sats; s.particles = MagNavPF::N;
}
static bool uploadCb(const double* lats, const double* lons, int n, float altRel) {
    static MavlinkLite::Waypoint wps[WebUI::MAXWP];
    for (int i = 0; i < n; i++) wps[i] = {lats[i], lons[i], altRel};
    mav.startMissionUpload(wps, n);
    uint32_t t0 = millis();
    while (millis() - t0 < 6000) {
        mav.poll();
        if (mav.uploadState() == MavlinkLite::Upload::Done) return true;
        if (mav.uploadState() == MavlinkLite::Upload::Failed) return false;
        delay(5);
    }
    return false;
}
static void calCb(bool start) {
    calibrating = start;
    if (start) tl.beginFit();
    else if (tl.solve()) { tl.save(SD_MMC); Serial.println("[cal] Tolles-Lawson saved"); }
}
static void initCb(double lat, double lon) {
    pf.init(lat, lon, 500.0f, 200.0f);
    estLat = lat; estLon = lon; magnavMode = true;
}
static float anomCb(double lat, double lon) {
    AnomalyMap& m = localMap.covers(lat, lon) ? localMap : worldMap;
    return m.lookup(lat, lon);
}

// ---------------------------------------------------------------- setup
void setup() {
    Serial.begin(115200);
    pinMode(PIN_LED_NAV, OUTPUT); pinMode(PIN_LED_FIX, OUTPUT); pinMode(PIN_LED_LINK, OUTPUT);
    pinMode(PIN_SD_DET, INPUT_PULLUP);
    // GNSS TIMEPULSE is tied inside the MAX-M10S to SAFEBOOT_N through 1 kOhm
    // (integration manual UBX-20053088, table 1): this pin must never be
    // driven low at receiver start-up or the module enters safeboot. Input only.
    pinMode(PIN_GNSS_PPS, INPUT);

    spiBus.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI);
    Serial.printf("[imu] %s\n", imu.begin() ? "ok" : "FAIL");
    Serial.printf("[mag] %s\n", mag.begin() ? "ok" : "FAIL");
    Serial.printf("[baro] %s\n", baro.begin() ? "ok" : "FAIL");

    SD_MMC.setPins(PIN_SD_CLK, PIN_SD_CMD, PIN_SD_D0, PIN_SD_D1, PIN_SD_D2, PIN_SD_D3);
    sdOk = SD_MMC.begin("/sdcard", false);
    Serial.printf("[sd] %s\n", sdOk ? "ok" : "FAIL");
    if (sdOk) {
        wmmOk = wmm.load(SD_MMC, "/maps/WMM.COF");
        mapOk = worldMap.open(SD_MMC, "/maps/wdmam.bin");
        localMap.open(SD_MMC, "/maps/local.bin");
        tl.load(SD_MMC);
        Serial.printf("[wmm] %s  [map] %s  [tl] %s\n", wmmOk ? "ok" : "missing",
                      mapOk ? "ok" : "missing", tl.valid ? "ok" : "uncalibrated");
    }
    gnss.begin(PIN_GNSS_RX, PIN_GNSS_TX, 38400);
    mav.begin(PIN_FC_RX, PIN_FC_TX, 57600);
    web.begin(statusCb, uploadCb, calCb, initCb, anomCb);
    Serial.println("[web] AP DroneMagNav  http://192.168.4.1/");
}

// ---------------------------------------------------------------- loop
void loop() {
    uint32_t now = millis();
    gnss.poll(); mav.poll(); web.poll();

    if (now - tLastImu >= 10) {                       // 100 Hz
        float dt = (now - tLastImu) / 1000.0f; tLastImu = now;
        float ax, ay, az, gx, gy, gz;
        imu.readAccel(ax, ay, az); imu.readGyro(gx, gy, gz);
        attitudeUpdate(ax, ay, az, gx, gy, gz, dt);
        // crude IMU dead reckoning in the horizontal plane (used only when the
        // flight controller does not supply velocity)
        float aN = ax * cosf(yaw) - ay * sinf(yaw), aE = ax * sinf(yaw) + ay * cosf(yaw);
        vnDR = 0.995f * (vnDR + aN * dt); veDR = 0.995f * (veDR + aE * dt);
    }
    if (now - tLastMag >= 12) {                       // ~80 Hz
        float dt = (now - tLastMag) / 1000.0f; tLastMag = now;
        float bx, by, bz;
        mag.read(bx, by, bz);
        bxf = 0.8f * bxf + 0.2f * bx; byf = 0.8f * byf + 0.2f * by; bzf = 0.8f * bzf + 0.2f * bz;
        float bxd = (bxf - bxPrev) / dt, byd = (byf - byPrev) / dt, bzd = (bzf - bzPrev) / dt;
        bxPrev = bxf; byPrev = byf; bzPrev = bzf;
        float scalar = sqrtf(bxf * bxf + byf * byf + bzf * bzf);
        scalarComp = scalar - tl.correction(bxf, byf, bzf, bxd, byd, bzd);
        if (calibrating && gnss.fresh() && wmmOk) {
            float ref = (float)wmm.totalField(gnss.fix().lat, gnss.fix().lon,
                                              altBaroM / 1000.0, decimalYear()) +
                        (isnan(anomCb(gnss.fix().lat, gnss.fix().lon)) ? 0 : anomCb(gnss.fix().lat, gnss.fix().lon));
            tl.addSample(bxf, byf, bzf, bxd, byd, bzd, scalar - ref);
        }
    }
    if (now - tLastBaro >= 100) {                     // 10 Hz
        tLastBaro = now;
        float p, t; baro.read(p, t);
        altBaroM = BMP280::altitudeFromPressure(p, qnh);
    }

    // ---- navigation at 10 Hz ------------------------------------------
    if (now - tLastPf >= 100) {
        float dt = (now - tLastPf) / 1000.0f; tLastPf = now;
        bool fcVel = mav.fc().alive && (now - mav.fc().lastMs) < 1000;
        float vn = fcVel ? mav.fc().vn : vnDR, ve = fcVel ? mav.fc().ve : veDR;

        if (gnss.fresh() && !magnavMode) {
            estLat = gnss.fix().lat; estLon = gnss.fix().lon; estSigma = gnss.fix().hdop * 2.5f;
            if (!pf.initialised || estSigma < 20) pf.init(estLat, estLon, 50.0f, 100.0f);
        } else if (!gnss.fresh() && pf.initialised) {
            magnavMode = true;
        }
        if (magnavMode && pf.initialised && mapOk && wmmOk) {
            AnomalyMap& m = localMap.covers(estLat, estLon) ? localMap : worldMap;
            m.ensureWindow(estLat, estLon);
            pf.predict(vn, ve, dt, 1.5f, 5.0f);
            pf.update(scalarComp, wmm, m, altBaroM / 1000.0, decimalYear(), 40.0f);
            pf.estimate(estLat, estLon, estBias, estSigma);
            anomAtEst = m.lookup(estLat, estLon);
            if (now - tLastGpsIn >= 200) {
                tLastGpsIn = now;
                mav.sendGpsInput(estLat, estLon, altBaroM, estSigma, vn, ve, 3, 8);
            }
        } else if (mapOk) {
            AnomalyMap& m = localMap.covers(estLat, estLon) ? localMap : worldMap;
            m.ensureWindow(estLat, estLon);
            anomAtEst = m.lookup(estLat, estLon);
        }
        digitalWrite(PIN_LED_NAV, magnavMode && estSigma < 500);
        digitalWrite(PIN_LED_FIX, gnss.fresh());
        digitalWrite(PIN_LED_LINK, mav.fc().alive && (now - mav.fc().lastMs) < 3000);
    }
    if (now - tLastHb >= 1000) { tLastHb = now; mav.sendHeartbeat(); }
}
