#include <string>
#include <map>
#include <tuple>
#include <stdexcept>
#include <vector>
#include <cstdint>
#include <cctype>
#include <iostream>
#include <cmath>
#include <functional>

// Base64 decoding
static const std::string b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string b64decode(const std::string& s) {
    std::string ret;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[(unsigned char)b64chars[i]] = i;

    int val = 0, valb = -8;
    for (unsigned char c : s) {
        if (T[c] == -1) break;
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            ret.push_back(char((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return ret;
}

// Minimal JSON Parser
struct Parser {
    std::string str;
    size_t pos;

    Parser(const std::string& s) : str(s), pos(0) {}

    char peek() { if (pos >= str.size()) throw std::invalid_argument("unexpected end"); return str[pos]; }
    char next() { if (pos >= str.size()) throw std::invalid_argument("unexpected end"); return str[pos++]; }
    void skip_ws() { while (pos < str.size() && isspace((unsigned char)str[pos])) pos++; }
    void expect(char c) { if (next() != c) throw std::invalid_argument("expected char"); }

    std::string parse_string() {
        expect('"');
        std::string res;
        while (true) {
            char c = next();
            if (c == '"') break;
            if (c == '\\') {
                c = next();
                switch(c) {
                    case '"': case '\\': case '/': res += c; break;
                    case 'b': res += '\b'; break;
                    case 'f': res += '\f'; break;
                    case 'n': res += '\n'; break;
                    case 'r': res += '\r'; break;
                    case 't': res += '\t'; break;
                    case 'u': for(int i=0;i<4;i++) next(); res += '?'; break;
                    default: throw std::invalid_argument("bad escape");
                }
            } else {
                res += c;
            }
        }
        return res;
    }

    int64_t parse_int() {
        skip_ws();
        size_t start = pos;
        if (peek() == '-') next();
        if (pos >= str.size() || !isdigit((unsigned char)str[pos])) throw std::invalid_argument("bad int");
        while (pos < str.size() && isdigit((unsigned char)str[pos])) next();
        return std::stoll(str.substr(start, pos - start));
    }

    double parse_double() {
        skip_ws();
        size_t start = pos;
        if (peek() == '-') next();
        while (pos < str.size() && isdigit((unsigned char)str[pos])) next();
        if (pos < str.size() && str[pos] == '.') { next(); while (pos < str.size() && isdigit((unsigned char)str[pos])) next(); }
        if (pos < str.size() && (str[pos] == 'e' || str[pos] == 'E')) { next(); if (pos < str.size() && (str[pos] == '+' || str[pos] == '-')) next(); while (pos < str.size() && isdigit((unsigned char)str[pos])) next(); }
        return std::stod(str.substr(start, pos - start));
    }

    std::map<std::string, double> parse_metrics() {
        skip_ws();
        expect('{');
        skip_ws();
        std::map<std::string, double> res;
        if (peek() == '}') { next(); return res; }
        while (true) {
            skip_ws();
            std::string k = parse_string();
            if (k.empty()) throw std::invalid_argument("invalid metric key");
            skip_ws();
            expect(':');
            double v = parse_double();
            res[k] = v;
            skip_ws();
            if (peek() == '}') { next(); break; }
            expect(',');
        }
        return res;
    }
};

std::tuple<std::string, int64_t, std::map<std::string, double>> load_cached_report(const std::string& blob) {
    std::string decoded;
    try {
        decoded = b64decode(blob);
    } catch (...) {
        throw std::invalid_argument("invalid base64");
    }

    for (unsigned char c : decoded) {
        if (c > 127) throw std::invalid_argument("invalid decoded text");
    }

    Parser p(decoded);
    std::string report_id;
    int64_t generated_at = -1;
    std::map<std::string, double> metrics;
    bool has_report_id = false, has_generated_at = false, has_metrics = false;

    try {
        p.skip_ws();
        p.expect('{');
        p.skip_ws();
        if (p.peek() != '}') {
            while (true) {
                p.skip_ws();
                std::string key = p.parse_string();
                p.skip_ws();
                p.expect(':');
                p.skip_ws();

                if (key == "report_id") {
                    report_id = p.parse_string();
                    if (report_id.empty()) throw std::invalid_argument("invalid report_id");
                    has_report_id = true;
                } else if (key == "generated_at") {
                    generated_at = p.parse_int();
                    if (generated_at < 0) throw std::invalid_argument("generated_at must be non-negative");
                    has_generated_at = true;
                } else if (key == "metrics") {
                    metrics = p.parse_metrics();
                    has_metrics = true;
                } else {
                    // skip unknown value
                    if (p.peek() == '"') p.parse_string();
                    else if (p.peek() == '{') { int d=0; do { if(p.next()=='{')d++; if(p.str[p.pos-1]=='}')d--; } while(d>0); }
                    else if (p.peek() == '[') { int d=0; do { if(p.next()=='[')d++; if(p.str[p.pos-1]==']')d--; } while(d>0); }
                    else { while(p.pos<p.str.size()&&p.peek()!=','&&p.peek()!='}') p.next(); }
                }

                p.skip_ws();
                if (p.peek() == '}') break;
                p.expect(',');
            }
        }
        p.skip_ws();
        p.expect('}');
    } catch (const std::invalid_argument&) {
        throw;
    } catch (const std::bad_cast&) {
        throw std::invalid_argument("invalid JSON");
    } catch (...) {
        throw std::invalid_argument("invalid JSON");
    }

    if (!has_report_id || !has_generated_at || !has_metrics) {
        throw std::invalid_argument("missing required field");
    }

    return {report_id, generated_at, metrics};
}


// Validation Harness Helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_equal(int64_t actual, int64_t expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_equal(const std::map<std::string, double>& actual, const std::map<std::string, double>& expected, const std::string& message) {
    if (actual.size() != expected.size()) {
        fail(message + " map size mismatch");
        return;
    }
    for (const auto& kv : expected) {
        auto it = actual.find(kv.first);
        if (it == actual.end()) {
            fail(message + " missing key '" + kv.first + "'");
            return;
        }
        if (std::abs(it->second - kv.second) > 1e-9) {
            fail(message + " value mismatch for key '" + kv.first + "'");
            return;
        }
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (const std::bad_cast&) {
        // Expected (TypeError equivalent)
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

std::string b64encode(const std::string& in) {
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(b64chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(b64chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

void check() {
    // Test 1: Good blob
    {
        std::string json_str = "{\"report_id\": \"r1\", \"generated_at\": 1700000000, \"metrics\": {\"acc\": 0.9, \"loss\": 1.2}}";
        std::string b64 = b64encode(json_str);
        auto result = load_cached_report(b64);
        expect_equal(std::get<0>(result), "r1", "Test 1 report_id");
        expect_equal(std::get<1>(result), 1700000000, "Test 1 generated_at");
        std::map<std::string, double> expected_metrics = {{"acc", 0.9}, {"loss", 1.2}};
        expect_equal(std::get<2>(result), expected_metrics, "Test 1 metrics");
    }

    // Test 2: Empty metrics
    {
        std::string json_str = "{\"report_id\": \"x\", \"generated_at\": 0, \"metrics\": {}}";
        std::string b64 = b64encode(json_str);
        auto result = load_cached_report(b64);
        expect_equal(std::get<0>(result), "x", "Test 2 report_id");
        expect_equal(std::get<1>(result), 0, "Test 2 generated_at");
        std::map<std::string, double> expected_metrics;
        expect_equal(std::get<2>(result), expected_metrics, "Test 2 metrics");
    }

    // Test 3: non-json after decoding
    assert_raises([]() { load_cached_report(b64encode("not json")); }, "Test 3 non-json");

    // Test 4: json but not an object
    assert_raises([]() { load_cached_report(b64encode("[1,2,3]")); }, "Test 4 not object");

    // Test 5: missing field
    assert_raises([]() { load_cached_report(b64encode("{\"report_id\": \"r2\", \"generated_at\": 1}")); }, "Test 5 missing field");

    // Test 6: wrong types inside (string instead of numeric in metrics)
    assert_raises([]() { load_cached_report(b64encode("{\"report_id\": \"r3\", \"generated_at\": 1, \"metrics\": {\"a\": \"x\"}}")); }, "Test 6 wrong types");

    // Test 7: invalid base64
    assert_raises([]() { load_cached_report("<not base64>"); }, "Test 7 invalid base64");

    // Test 8: invalid decoded text (non-UTF8/ASCII)
    assert_raises([]() {
        std::string bad_str = "{\"report_id\": \"r\", \"generated_at\": 1, \"metrics\": {}}";
        bad_str.push_back(static_cast<char>(0x80)); // Invalid UTF-8 byte
        load_cached_report(b64encode(bad_str));
    }, "Test 8 invalid decoded text");

    // Test 9: negative generated_at
    assert_raises([]() { load_cached_report(b64encode("{\"report_id\": \"r\", \"generated_at\": -1, \"metrics\": {}}")); }, "Test 9 negative generated_at");

    // Test 10: empty report_id
    assert_raises([]() { load_cached_report(b64encode("{\"report_id\": \"\", \"generated_at\": 1, \"metrics\": {}}")); }, "Test 10 empty report_id");

    // Test 11: empty metric key
    assert_raises([]() { load_cached_report(b64encode("{\"report_id\": \"r\", \"generated_at\": 1, \"metrics\": {\"\": 1.0}}")); }, "Test 11 empty metric key");
}

int main() {
    check();
    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed!" << std::endl;
    return 0;
}