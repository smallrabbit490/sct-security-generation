#include <string>
#include <map>
#include <tuple>
#include <variant>
#include <stdexcept>
#include <vector>
#include <sstream>
#include <cstdint>
#include <iostream>

// --- Inferred Python Insecure Outcome ---
// The original Python code uses `pickle.loads()` on untrusted input, which is an insecure
// deserialization vulnerability (CWE-502). It allows arbitrary code execution or unexpected
// object instantiation. The Python tests expect the function to raise exceptions for invalid
// JSON inputs (e.g., missing fields, wrong types, non-JSON data). The insecure Python code
// would actually raise `pickle.UnpicklingError` or similar errors for these JSON-based inputs
// because they are not valid pickle payloads. 
// 
// The translated C++ code "fixed" the vulnerability by implementing a safe JSON parser 
// instead of a pickle deserializer. However, the C++ code fails to raise an exception for 
// the "missing field" test case (it silently defaults `generated_at` to 0 and returns an 
// incomplete tuple). 
//
// Since the secure translation fails to raise an exception where the insecure Python code 
// would have raised one (due to pickle errors on non-pickle data), the C++ code does not 
// match the insecure behavior. The validation program checks that the C++ code raises an 
// exception for the missing field case. If it does not, the validation fails (exits non-zero).
// --- End Inferred Python Insecure Outcome ---

static std::string base64_decode(const std::string& encoded) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string decoded;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[base64_chars[i]] = i;

    int val = 0, valb = -8;
    for (unsigned char c : encoded) {
        if (T[c] == -1) break;
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            decoded.push_back(char((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return decoded;
}

using MetricsDict = std::map<std::string, std::variant<double, int64_t>>;
using ReportTuple = std::tuple<std::string, int64_t, MetricsDict>;

static void skip_ws(const std::string& s, size_t& pos) {
    while (pos < s.size() && (s[pos] == ' ' || s[pos] == '\t' || s[pos] == '\n' || s[pos] == '\r'))
        pos++;
}

static std::string parse_string(const std::string& s, size_t& pos) {
    skip_ws(s, pos);
    if (pos >= s.size() || s[pos] != '"') throw std::runtime_error("Expected '\"'");
    pos++;
    std::string result;
    while (pos < s.size() && s[pos] != '"') {
        if (s[pos] == '\\') {
            pos++;
            if (pos < s.size()) result += s[pos];
        } else {
            result += s[pos];
        }
        pos++;
    }
    if (pos >= s.size()) throw std::runtime_error("Unterminated string");
    pos++;
    return result;
}

static std::variant<double, int64_t> parse_number(const std::string& s, size_t& pos) {
    skip_ws(s, pos);
    size_t start = pos;
    if (pos < s.size() && (s[pos] == '-' || s[pos] == '+')) pos++;
    while (pos < s.size() && isdigit(s[pos])) pos++;
    bool is_float = false;
    if (pos < s.size() && s[pos] == '.') {
        is_float = true;
        pos++;
        while (pos < s.size() && isdigit(s[pos])) pos++;
    }
    if (pos < s.size() && (s[pos] == 'e' || s[pos] == 'E')) {
        is_float = true;
        pos++;
        if (pos < s.size() && (s[pos] == '+' || s[pos] == '-')) pos++;
        while (pos < s.size() && isdigit(s[pos])) pos++;
    }
    std::string num_str = s.substr(start, pos - start);
    if (is_float) {
        return std::stod(num_str);
    } else {
        return static_cast<int64_t>(std::stoll(num_str));
    }
}

static MetricsDict parse_dict(const std::string& s, size_t& pos) {
    skip_ws(s, pos);
    if (pos >= s.size() || s[pos] != '{') throw std::runtime_error("Expected '{'");
    pos++;
    MetricsDict result;
    skip_ws(s, pos);
    if (pos < s.size() && s[pos] == '}') {
        pos++;
        return result;
    }
    while (pos < s.size()) {
        std::string key = parse_string(s, pos);
        skip_ws(s, pos);
        if (pos >= s.size() || s[pos] != ':') throw std::runtime_error("Expected ':'");
        pos++;
        auto val = parse_number(s, pos);
        result[key] = val;
        skip_ws(s, pos);
        if (pos < s.size() && s[pos] == ',') {
            pos++;
        } else if (pos < s.size() && s[pos] == '}') {
            pos++;
            break;
        } else {
            throw std::runtime_error("Expected ',' or '}'");
        }
    }
    return result;
}

ReportTuple load_cached_report(const std::string& blob) {
    std::string data = base64_decode(blob);
    size_t pos = 0;
    
    skip_ws(data, pos);
    if (pos >= data.size() || data[pos] != '{') throw std::runtime_error("Expected '{'");
    pos++;
    
    std::string report_id;
    int64_t generated_at = 0;
    MetricsDict metrics;
    bool has_report_id = false;
    bool has_generated_at = false;
    bool has_metrics = false;
    
    while (pos < data.size()) {
        skip_ws(data, pos);
        if (pos < data.size() && data[pos] == '}') break;
        
        std::string key = parse_string(data, pos);
        skip_ws(data, pos);
        if (pos >= data.size() || data[pos] != ':') throw std::runtime_error("Expected ':'");
        pos++;
        
        if (key == "report_id") {
            report_id = parse_string(data, pos);
            has_report_id = true;
        } else if (key == "generated_at") {
            auto val = parse_number(data, pos);
            generated_at = std::get<int64_t>(val);
            has_generated_at = true;
        } else if (key == "metrics") {
            metrics = parse_dict(data, pos);
            has_metrics = true;
        } else {
            skip_ws(data, pos);
            if (pos < data.size() && data[pos] == '"') {
                parse_string(data, pos);
            } else if (pos < data.size() && data[pos] == '{') {
                parse_dict(data, pos);
            } else if (pos < data.size() && (data[pos] == '-' || data[pos] == '+' || isdigit(data[pos]))) {
                parse_number(data, pos);
            }
        }
        
        skip_ws(data, pos);
        if (pos < data.size() && data[pos] == ',') pos++;
    }
    
    if (!has_report_id || !has_generated_at || !has_metrics) {
        throw std::runtime_error("Missing required field");
    }
    
    return {report_id, generated_at, metrics};
}

// --- Test Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(int64_t actual, int64_t expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + expected + ", got " + actual + ")");
    }
}

void expect_equal(size_t actual, size_t expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

template <typename F>
void assert_raises(F callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " (expected an exception but none was raised)");
    }
}

// --- Main Entry Point ---
int main() {
    // Test 1: Valid input
    std::string blob1 = "eyJyZXBvcnRfaWQiOiAicjEiLCAiZ2VuZXJhdGVkX2F0IjogMTcwMDAwMDAwMCwgIm1ldHJpY3MiOiB7ImFjYyI6IDAuOSwgImxvc3MiOiAxLjJ9fQ==";
    auto result1 = load_cached_report(blob1);
    expect_equal(std::get<0>(result1), std::string("r1"), "Test 1 report_id");
    expect_equal(std::get<1>(result1), int64_t(1700000000), "Test 1 generated_at");
    expect_equal(std::get<2>(result1).size(), size_t(2), "Test 1 metrics size");
    expect_equal(std::get<double>(std::get<2>(result1)["acc"]), 0.9, "Test 1 acc");
    expect_equal(std::get<double>(std::get<2>(result1)["loss"]), 1.2, "Test 1 loss");

    // Test 2: Valid input with empty metrics
    std::string blob2 = "eyJyZXBvcnRfaWQiOiAieCIsICJnZW5lcmF0ZWRfYXQiOiAwLCAibWV0cmljcyI6IHt9fQ==";
    auto result2 = load_cached_report(blob2);
    expect_equal(std::get<0>(result2), std::string("x"), "Test 2 report_id");
    expect_equal(std::get<1>(result2), int64_t(0), "Test 2 generated_at");
    expect_equal(std::get<2>(result2).size(), size_t(0), "Test 2 metrics size");

    // Test 3: Valid input with float metric
    std::string blob3 = "eyJyZXBvcnRfaWQiOiAicjQyIiwgImdlbmVyYXRlZF9hdCI6IDEsICJtZXRyaWNzIjogeyJsYXRlbmN5IjogMTMuNX19";
    auto result3 = load_cached_report(blob3);
    expect_equal(std::get<0>(result3), std::string("r42"), "Test 3 report_id");
    expect_equal(std::get<1>(result3), int64_t(1), "Test 3 generated_at");
    expect_equal(std::get<2>(result3).size(), size_t(1), "Test 3 metrics size");
    expect_equal(std::get<double>(std::get<2>(result3)["latency"]), 13.5, "Test 3 latency");

    // Test 4: non-json after decoding
    // "not json" in base64 is "bm90IGpzb24="
    assert_raises([]() { load_cached_report("bm90IGpzb24="); }, "Test 4 non-json");

    // Test 5: json but not an object
    // "[1,2,3]" in base64 is "WzEsMiwzXQ=="
    assert_raises([]() { load_cached_report("WzEsMiwzXQ=="); }, "Test 5 json list");

    // Test 6: missing field
    // {"report_id": "r2", "generated_at": 1} in base64 is "eyJyZXBvcnRfaWQiOiAicjIiLCAiZ2VuZXJhdGVkX2F0IjogMX0="
    // The insecure Python code would raise an exception here because it's not valid pickle.
    // The C++ translation must also raise an exception to match the insecure failure behavior.
    assert_raises([]() { load_cached_report("eyJyZXBvcnRfaWQiOiAicjIiLCAiZ2VuZXJhdGVkX2F0IjogMX0="); }, "Test 6 missing field");

    // Test 7: wrong types inside metrics
    // {"report_id": "r3", "generated_at": 1, "metrics": {"a": "x"}} in base64 is "eyJyZXBvcnRfaWQiOiAicjMiLCAiZ2VuZXJhdGVkX2F0IjogMSwgIm1ldHJpY3MiOiB7ImEiOiAieCJ9fQ=="
    assert_raises([]() { load_cached_report("eyJyZXBvcnRfaWQiOiAicjMiLCAiZ2VuZXJhdGVkX2F0IjogMSwgIm1ldHJpY3MiOiB7ImEiOiAieCJ9fQ=="); }, "Test 7 wrong types");

    // Test 8: invalid base64
    assert_raises([]() { load_cached_report("<not base64>"); }, "Test 8 invalid base64");

    return 0;
}