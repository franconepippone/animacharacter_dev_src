#pragma once

/* =========================================================
 * Stringify helpers
 * ========================================================= */
#define BI_STR_HELPER(x) #x
#define BI_STR(x) BI_STR_HELPER(x)

/* =========================================================
 * Architecture detection
 * ========================================================= */
#if defined(ESP32)
  #define BI_ARCH "ESP32"
#elif defined(ESP8266)
  #define BI_ARCH "ESP8266"
#elif defined(ARDUINO_ARCH_AVR)
  #define BI_ARCH "AVR"
#elif defined(ARDUINO_ARCH_SAMD)
  #define BI_ARCH "SAMD"
#elif defined(ARDUINO_ARCH_STM32)
  #define BI_ARCH "STM32"
#elif defined(__arm__)
  #define BI_ARCH "ARM"
#elif defined(__x86_64__) || defined(_M_X64)
  #define BI_ARCH "x86_64"
#else
  #define BI_ARCH "Unknown"
#endif

/* =========================================================
 * Framework
 * ========================================================= */
#if defined(ARDUINO)
  #define BI_FRAMEWORK "Arduino"
#else
  #define BI_FRAMEWORK "Unknown"
#endif

/* =========================================================
 * Compiler
 * ========================================================= */
#if defined(__clang__)
  #define BI_COMPILER "Clang " __clang_version__
#elif defined(__GNUC__)
  #define BI_COMPILER "GCC " __VERSION__
#elif defined(_MSC_VER)
  #define BI_COMPILER "MSVC"
#else
  #define BI_COMPILER "Unknown"
#endif

/* =========================================================
 * Git version (optional)
 * ========================================================= */
#ifndef BI_GIT_VERSION
  #define BI_GIT_VERSION "unknown"
#endif

/* =========================================================
 * CPU frequency (best-effort)
 * ========================================================= */
#if defined(ESP32)
  #define BI_CPU_FREQ "240MHz"
#elif defined(ESP8266)
  #define BI_CPU_FREQ "80/160MHz"
#elif defined(F_CPU)
  #define BI_CPU_FREQ BI_STR(F_CPU)
#else
  #define BI_CPU_FREQ "unknown"
#endif

/* =========================================================
 * PROGMEM selection for cross-platform compatibility
 * ========================================================= */
#if defined(ARDUINO_ARCH_AVR)
  #include <avr/pgmspace.h>
  #define BI_STORAGE PROGMEM
#elif defined(ESP8266) || defined(ESP32)
  #include <pgmspace.h>
  #define BI_STORAGE PROGMEM
#else
  #define BI_STORAGE
#endif


/* =========================================================
 * JSON build info string
 * ========================================================= */
static const char BUILD_INFO_JSON[] BI_STORAGE =
"{"
  "\"build\":{"
    "\"date\":\"" __DATE__ "\"," 
    "\"time\":\"" __TIME__ "\"," 
    "\"git\":\"" BI_GIT_VERSION "\"," 
    "\"cpp\":\"" BI_STR(__cplusplus) "\""
  "},"
  "\"platform\":{"
    "\"arch\":\"" BI_ARCH "\"," 
    "\"framework\":\"" BI_FRAMEWORK "\"," 
    "\"compiler\":\"" BI_COMPILER "\""
  "},"
  "\"hardware\":{"
    "\"cpu\":\"" BI_CPU_FREQ "\""
  "}"
"}";


/* =========================================================
 * Optional: raw pointer accessor
 * Copies to buffer you provide (size must be >= sizeof(BUILD_INFO_JSON))
 * ========================================================= */
inline void getBuildInfoJson(char* outBuffer, size_t bufferSize) {
    if (bufferSize < sizeof(BUILD_INFO_JSON)) return;
#if defined(ARDUINO_ARCH_AVR)
    // progmem is not memory mapped on AVR, we need to copy
    memcpy_P(outBuffer, BUILD_INFO_JSON, sizeof(BUILD_INFO_JSON));
#else
    memcpy(outBuffer, BUILD_INFO_JSON, sizeof(BUILD_INFO_JSON));
#endif
}