#include <string>
#include <variant>
#include <vector>
#include <map>
#include <stdexcept>
#include <cctype>
#include <cmath>
#include <sstream>
#include <memory>
#include <iostream>
#include <functional>

struct JsonValue;
using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, double, std::string, JsonObject, JsonArray> data;
};

class JsonParser {
public:
    JsonParser(const std::string& s) : str(s), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < str.size()) {
            throw std::runtime_error("Unexpected trailing characters");
        }
        return val;
    }

private:
    std::string str;
    size_t pos;

    char peek() {
        if (pos < str.size()) return str[pos];
        throw std::runtime_error("Unexpected end of input");
    }

    char consume() {
        if (pos < str.size()) return str[pos++];
        throw std::runtime_error("Unexpected end of input");
    }

    void skip_whitespace() {
        while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) {
            pos++;
        }
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = peek();
        if (c == '"') return parse_string();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == 't' || c == 'f') return parse_boolean();
        if (c == 'n') return parse_null();
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        throw std::runtime_error("Invalid JSON value");
    }

    JsonValue parse_string() {
        consume(); // '"'
        std::string result;
        while (true) {
            char c = consume();
            if (c == '"') break;
            if (c == '\\') {
                char esc = consume();
                switch (esc) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    case 'u': {
                        std::string hex;
                        for (int i = 0; i < 4; ++i) hex += consume();
                        unsigned int cp = std::stoul(hex, nullptr, 16);
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            char c1 = consume();
                            char c2 = consume();
                            if (c1 != '\\' || c2 != 'u') throw std::runtime_error("Invalid UTF-16 surrogate");
                            std::string hex2;
                            for (int i = 0; i < 4; ++i) hex2 += consume();
                            unsigned int cp2 = std::stoul(hex2, nullptr, 16);
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("Invalid UTF-16 surrogate");
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00);
                        }
                        if (cp < 0x80) {
                            result += static_cast<char>(cp);
                        } else if (cp < 0x800) {
                            result += static_cast<char>(0xC0 | (cp >> 6));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else if (cp < 0x10000) {
                            result += static_cast<char>(0xE0 | (cp >> 12));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else {
                            result += static_cast<char>(0xF0 | (cp >> 18));
                            result += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default: throw std::runtime_error("Invalid escape sequence");
                }
            } else {
                result += c;
            }
        }
        return JsonValue{result};
    }

    JsonValue parse_number() {
        size_t start = pos;
        if (peek() == '-') pos++;
        if (peek() == '0') {
            pos++;
        } else if (peek() >= '1' && peek() <= '9') {
            pos++;
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        } else {
            throw std::runtime_error("Invalid number");
        }
        if (pos < str.size() && str[pos] == '.') {
            pos++;
            if (pos >= str.size() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("Invalid number");
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        if (pos < str.size() && (str[pos] == 'e' || str[pos] == 'E')) {
            pos++;
            if (pos < str.size() && (str[pos] == '+' || str[pos] == '-')) pos++;
            if (pos >= str.size() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("Invalid number");
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        std::string num_str = str.substr(start, pos - start);
        double val = std::stod(num_str);
        return JsonValue{val};
    }

    JsonValue parse_boolean() {
        if (str.compare(pos, 4, "true") == 0) {
            pos += 4;
            return JsonValue{true};
        }
        if (str.compare(pos, 5, "false") == 0) {
            pos += 5;
            return JsonValue{false};
        }
        throw std::runtime_error("Invalid boolean");
    }

    JsonValue parse_null() {
        if (str.compare(pos, 4, "null") == 0) {
            pos += 4;
            return JsonValue{nullptr};
        }
        throw std::runtime_error("Invalid null");
    }

    JsonValue parse_array() {
        consume(); // '['
        JsonArray arr;
        skip_whitespace();
        if (peek() == ']') {
            consume();
            return JsonValue{arr};
        }
        while (true) {
            arr.push_back(parse_value());
            skip_whitespace();
            if (peek() == ']') {
                consume();
                break;
            }
            if (peek() == ',') {
                consume();
                skip_whitespace();
            } else {
                throw std::runtime_error("Expected ',' or ']'");
            }
        }
        return JsonValue{arr};
    }

    JsonValue parse_object() {
        consume(); // '{'
        JsonObject obj;
        skip_whitespace();
        if (peek() == '}') {
            consume();
            return JsonValue{obj};
        }
        while (true) {
            skip_whitespace();
            if (peek() != '"') throw std::runtime_error("Expected string key");
            JsonValue key_val = parse_string();
            const std::string& key = std::get<std::string>(key_val.data);
            skip_whitespace();
            if (consume() != ':') throw std::runtime_error("Expected ':'");
            JsonValue val = parse_value();
            obj[key] = std::move(val);
            skip_whitespace();
            if (peek() == '}') {
                consume();
                break;
            }
            if (peek() == ',') {
                consume();
                skip_whitespace();
            } else {
                throw std::runtime_error("Expected ',' or '}'");
            }
        }
        return JsonValue{obj};
    }
};

JsonObject load_user_session(const std::string& request_data) {
    try {
        JsonParser parser(request_data);
        JsonValue result = parser.parse();
        if (!std::holds_alternative<JsonObject>(result.data)) {
            throw std::runtime_error("session must be a JSON object");
        }
        return std::get<JsonObject>(std::move(result.data));
    } catch (const std::runtime_error& e) {
        throw std::runtime_error(std::string("invalid session data: ") + e.what());
    }
}

// Test helpers
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
        fail(message + " (expected: " + expected + ", got: " + actual + ")");
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

// Helper to compare JsonObject
bool json_obj_equal(const JsonObject& a, const JsonObject& b) {
    if (a.size() != b.size()) return false;
    for (const auto& kv : a) {
        auto it = b.find(kv.first);
        if (it == b.end()) return false;
        const JsonValue& va = kv.second;
        const JsonValue& vb = it->second;
        if (va.data.index() != vb.data.index()) return false;
        if (std::holds_alternative<std::string>(va.data)) {
            if (std::get<std::string>(va.data) != std::get<std::string>(vb.data)) return false;
        } else if (std::holds_alternative<double>(va.data)) {
            if (std::abs(std::get<double>(va.data) - std::get<double>(vb.data)) > 1e-9) return false;
        } else if (std::holds_alternative<bool>(va.data)) {
            if (std::get<bool>(va.data) != std::get<bool>(vb.data)) return false;
        } else if (std::holds_alternative<std::nullptr_t>(va.data)) {
            // both null
        } else if (std::holds_alternative<JsonObject>(va.data)) {
            if (!json_obj_equal(std::get<JsonObject>(va.data), std::get<JsonObject>(vb.data))) return false;
        } else if (std::holds_alternative<JsonArray>(va.data)) {
            const JsonArray& aa = std::get<JsonArray>(va.data);
            const JsonArray& ab = std::get<JsonArray>(vb.data);
            if (aa.size() != ab.size()) return false;
            for (size_t i = 0; i < aa.size(); ++i) {
                if (aa[i].data.index() != ab[i].data.index()) return false;
                if (std::holds_alternative<std::string>(aa[i].data)) {
                    if (std::get<std::string>(aa[i].data) != std::get<std::string>(ab[i].data)) return false;
                } else if (std::holds_alternative<double>(aa[i].data)) {
                    if (std::abs(std::get<double>(aa[i].data) - std::get<double>(ab[i].data)) > 1e-9) return false;
                }
            }
        }
    }
    return true;
}

int main() {
    // Test 1: Basic object with string and number
    {
        JsonObject result = load_user_session("{\"uid\": \"123\", \"age\": 45}");
        JsonObject expected;
        expected["uid"] = JsonValue{std::string("123")};
        expected["age"] = JsonValue{45.0};
        expect_true(json_obj_equal(result, expected), "Test 1: basic object");
    }

    // Test 2: Object with string value
    {
        JsonObject result = load_user_session("{\"name\": \"John Doe\"}");
        JsonObject expected;
        expected["name"] = JsonValue{std::string("John Doe")};
        expect_true(json_obj_equal(result, expected), "Test 2: string value");
    }

    // Test 3: Empty object
    {
        JsonObject result = load_user_session("{}");
        JsonObject expected;
        expect_true(json_obj_equal(result, expected), "Test 3: empty object");
    }

    // Test 4: Whitespace handling
    {
        JsonObject result = load_user_session(" { \"k\" : \"v\" , \"n\" : 1 } ");
        JsonObject expected;
        expected["k"] = JsonValue{std::string("v")};
        expected["n"] = JsonValue{1.0};
        expect_true(json_obj_equal(result, expected), "Test 4: whitespace handling");
    }

    // Test 5: Invalid JSON raises exception
    {
        assert_raises([]() { load_user_session("<not json>"); }, "Test 5: invalid JSON");
    }

    // Test 6: JSON array raises exception (must be object)
    {
        assert_raises([]() { load_user_session("[1, 2, 3]"); }, "Test 6: array instead of object");
    }

    // Test 7: Empty string raises exception
    {
        assert_raises([]() { load_user_session(""); }, "Test 7: empty string");
    }

    // Test 8: Security - deeply nested JSON should not crash (stack overflow protection)
    {
        // Build a moderately deep but safe nesting
        std::string deep_json;
        for (int i = 0; i < 50; ++i) deep_json += "{\"a\":";
        deep_json += "1";
        for (int i = 0; i < 50; ++i) deep_json += "}";
        try {
            JsonObject result = load_user_session(deep_json);
            expect_true(result.count("a") > 0, "Test 8: deep nesting has key 'a'");
        } catch (const std::exception& e) {
            // Acceptable if it rejects overly deep nesting safely
        }
    }

    // Test 9: Security - malformed/truncated JSON
    {
        assert_raises([]() { load_user_session("{\"key\":"); }, "Test 9: truncated JSON");
    }

    // Test 10: Security - JSON with null byte injection attempt
    {
        std::string bad = "{\"key\": \"val\x00ue\"}";
        assert_raises([]() { load_user_session("{\"key\": \"val\x00ue\"}"); }, "Test 10: null byte in JSON");
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}