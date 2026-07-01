#include "cloud.h"
#include "pump.h"
#include "valve.h"
#include "dht_sensor.h"
#include "soil_sensor.h"
#include "water_tank.h"

#pragma GCC optimize ("Os")

std::vector<OfflineLog> offlineLogs;

void setupTime() {
    configTime(10800, 0, "pool.ntp.org", "time.nist.gov"); // 10800 = GMT+3 for Kenya
    Serial.print("Waiting for NTP time sync");
    time_t now = time(nullptr);
    int retries = 0;
    while (now < 24 * 3600 && retries < 20) {
        delay(500);
        Serial.print(".");
        now = time(nullptr);
        retries++;
    }
    Serial.println("");
    if (now > 24 * 3600) {
        struct tm timeinfo;
        localtime_r(&now, &timeinfo);
        char buf[25];
        strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
        Serial.printf("Current Kenya time: %s\n", buf);
    } else {
        Serial.println("Time sync failed - using millis");
    }
}

String getTimeString() {
    time_t now = time(nullptr);
    if (now < 24 * 3600) return "NoTime";
    struct tm timeinfo;
    localtime_r(&now, &timeinfo);
    char buf[20];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
    return String(buf);
}

void cloud_init() {
    WiFi.mode(WIFI_AP_STA);

    WiFi.begin(HOME_SSID, HOME_PASS);
    Serial.print("Connecting to home WiFi");
    int tries = 0;
    while (WiFi.status()!= WL_CONNECTED && tries < 20) {
        delay(500);
        Serial.print(".");
        tries++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nCloud connected!");
        Serial.print("ESP32 Internet IP: ");
        Serial.println(WiFi.localIP());
        setupTime();
        flushOfflineLogs();
    } else {
        Serial.println("\nCloud connect failed — running local only");
    }

    WiFi.softAP("ESP32_Nursery", "nursery123");
    Serial.print("Local AP IP: ");
    Serial.println(WiFi.softAPIP());
}

void cloud_update() {
    static unsigned long lastSend = 0;
    if (millis() - lastSend < 2000) return;
    lastSend = millis();

    if (WiFi.status()!= WL_CONNECTED) return;

    flushOfflineLogs();

    String json = "{";
    // DELETED: pump and valve lines - ESP32 should NOT report these
    json += "\"temp\":" + String(dht_get_temperature(), 1) + ",";
    json += "\"hum\":" + String(dht_get_humidity(), 1) + ",";
    json += "\"soil1\":" + String(soil_get_percent_1(), 1) + ",";
    json += "\"soil2\":" + String(soil_get_percent_2(), 1) + ",";
    json += "\"fault1\":" + String(soil_is_fault_1()? "true" : "false") + ",";
    json += "\"fault2\":" + String(soil_is_fault_2()? "true" : "false") + ",";
    json += "\"percent\":" + String(tank_get_percent(), 1) + ",";
    json += "\"volume\":" + String(tank_get_volume_l(), 0);
    json += "}";

    HTTPClient http;
    http.begin(CLOUD_URL);
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(json);

    if (code == 200) {
        String resp = http.getString();
        Serial.println("Cloud OK: " + resp);
        if (resp.indexOf("\"pump\":\"ON\"") >= 0) pump_on();
        if (resp.indexOf("\"pump\":\"OFF\"") >= 0) pump_off();
        if (resp.indexOf("\"valve\":\"OPENING\"") >= 0) valve_open();
        if (resp.indexOf("\"valve\":\"CLOSING\"") >= 0) valve_close();
        if (resp.indexOf("\"valve\":\"STOPPED\"") >= 0) valve_stop();
    } else {
        Serial.println("Cloud fail: " + String(code));
    }
    http.end();
}

void sendLogToVercel(String username, bool success) {
    if (WiFi.status()!= WL_CONNECTED) {
        Serial.println("Cloud: No WiFi - buffering log");
        if (offlineLogs.size() < MAX_OFFLINE_LOGS) {
            offlineLogs.push_back({username, success, millis()});
            Serial.printf("Cloud: Buffered. Total: %d\n", offlineLogs.size());
        }
        return;
    }

    HTTPClient http;
    http.begin(CLOUD_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);

    String payload = "{\"user\":\"" + username + "\",\"success\":" + (success? "true" : "false") +
                     ",\"time\":\"" + getTimeString() + "\"}";
    int httpCode = http.POST(payload);

    if (httpCode == 200) {
        Serial.println("Cloud: Vercel notified of login");
    } else {
        Serial.printf("Cloud: Vercel notify failed, HTTP: %d\n", httpCode);
    }
    http.end();
}

void flushOfflineLogs() {
    if (offlineLogs.empty() || WiFi.status()!= WL_CONNECTED) return;

    Serial.printf("Cloud: Flushing %d offline logs\n", offlineLogs.size());
    HTTPClient http;
    http.begin(CLOUD_URL);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);

    for (auto it = offlineLogs.begin(); it!= offlineLogs.end(); ) {
        String payload = "{\"user\":\"" + it->username + "\",\"success\":" + (it->success? "true" : "false") +
                         ",\"offline\":true,\"delay_ms\":" + String(millis() - it->timestamp) +
                         ",\"time\":\"" + getTimeString() + "\"}";

        int code = http.POST(payload);
        if (code == 200) {
            Serial.println("Cloud: Flushed 1 offline log");
            it = offlineLogs.erase(it);
            delay(100);
        } else {
            break;
        }
    }
    http.end();
}
