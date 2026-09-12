// Great-circle geometry (WGS-84 sphere approximation, R = 6371.0088 km)
#pragma once
#include <math.h>

namespace geo {

constexpr double R_EARTH = 6371008.8;    // metres
constexpr double DEG = M_PI / 180.0;

inline double haversine(double lat1, double lon1, double lat2, double lon2) {
    double p1 = lat1 * DEG, p2 = lat2 * DEG;
    double dp = (lat2 - lat1) * DEG, dl = (lon2 - lon1) * DEG;
    double a = sin(dp / 2) * sin(dp / 2) + cos(p1) * cos(p2) * sin(dl / 2) * sin(dl / 2);
    return 2 * R_EARTH * atan2(sqrt(a), sqrt(1 - a));
}

// initial bearing, degrees clockwise from true north
inline double bearing(double lat1, double lon1, double lat2, double lon2) {
    double p1 = lat1 * DEG, p2 = lat2 * DEG, dl = (lon2 - lon1) * DEG;
    double y = sin(dl) * cos(p2);
    double x = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl);
    double b = atan2(y, x) / DEG;
    return fmod(b + 360.0, 360.0);
}

// point at fraction f (0..1) along the great circle from 1 to 2
inline void intermediate(double lat1, double lon1, double lat2, double lon2,
                         double f, double& lat, double& lon) {
    double p1 = lat1 * DEG, l1 = lon1 * DEG, p2 = lat2 * DEG, l2 = lon2 * DEG;
    double d = haversine(lat1, lon1, lat2, lon2) / R_EARTH;
    if (d < 1e-12) { lat = lat1; lon = lon1; return; }
    double a = sin((1 - f) * d) / sin(d), b = sin(f * d) / sin(d);
    double x = a * cos(p1) * cos(l1) + b * cos(p2) * cos(l2);
    double y = a * cos(p1) * sin(l1) + b * cos(p2) * sin(l2);
    double z = a * sin(p1) + b * sin(p2);
    lat = atan2(z, sqrt(x * x + y * y)) / DEG;
    lon = atan2(y, x) / DEG;
}

// destination point given start, bearing (deg) and distance (m)
inline void destination(double lat1, double lon1, double brgDeg, double dist,
                        double& lat, double& lon) {
    double p1 = lat1 * DEG, l1 = lon1 * DEG, b = brgDeg * DEG, dr = dist / R_EARTH;
    double p2 = asin(sin(p1) * cos(dr) + cos(p1) * sin(dr) * cos(b));
    double l2 = l1 + atan2(sin(b) * sin(dr) * cos(p1), cos(dr) - sin(p1) * sin(p2));
    lat = p2 / DEG;
    lon = fmod(l2 / DEG + 540.0, 360.0) - 180.0;
}

}  // namespace geo
