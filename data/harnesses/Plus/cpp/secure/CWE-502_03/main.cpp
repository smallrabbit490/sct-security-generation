#include <string>
#include <variant>
#include <vector>
#include <map>
#include <stdexcept>
#include <cstdint>
#include <iostream>
#include <functional>

struct JsonValue;
using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int64_t, double, std::string, JsonArray, JsonObject> data;
};

static const std::string base64_chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

static bool is_base64(unsigned char c) {
    return (isalnum(c) || (c == '+') || (c == '/'));
}

static std::string base64_decode(const std::string& encoded_string) {
    int in_len = encoded_string.size();
    int i = 0;
    int j = 0;
    int in_ = 0;
    unsigned char char_array_4[4], char_array_3[3];
    std::string ret;

    while (in_len-- && (encoded_string[in_] != '=') && is_base64(encoded_string[in_])) {
        char_array_4[i++] = encoded_string[in_]; in_++;
        if (i == 4) {
            for (i = 0; i < 4; i++) {
                size_t pos = base64_chars.find(char_array_4[i]);
                if (pos == std::string::npos) throw std::invalid_argument("invalid base64");
                char_array_4[i] = static_cast<unsigned char>(pos);
            }

            char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
            char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
            char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

            for (i = 0; i < 3; i++)
                ret += char_array_3[i];
            i = 0;
        }
    }

    if (i) {
        for (j = i; j < 4; j++)
            char_array_4[j] = 0;

        for (j = 0; j < 4; j++) {
            if (j < i) {
                size_t pos = base64_chars.find(char_array_4[j]);
                if (pos == std::string::npos) throw std::invalid_argument("invalid base64");
                char_array_4[j] = static_cast<unsigned char>(pos);
            }
        }

        char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
        char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
        char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

        for (j = 0; j < i - 1; j++)
            ret += char_array_3[j];
    }

    return ret;
}

static bool validate_base64(const std::string& s) {
    if (s.empty()) return true;
    size_t len = s.size();
    size_t data_end = len;
    size_t padding = 0;
    
    if (s[len - 1] == '=') {
        padding++;
        data_end--;
        if (len >= 2 && s[len - 2] == '=') {
            padding++;
            data_end--;
        }
    }
    
    if (padding == 1 && data_end % 4 != 3) return false;
    if (padding == 2 && data_end % 4 != 2) return false;
    
    for (size_t i = 0; i < data_end; ++i) {
        if (!is_base64(s[i])) return false;
    }
    for (size_t i = data_end; i < len; ++i) {
        if (s[i] != '=') return false;
    }
    return true;
}

class JsonParser {
public:
    JsonParser(const std::string& s) : str(s), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos != str.size()) {
            throw std::runtime_error("invalid plugin configuration data");
        }
        return val;
    }

private:
    std::string str;
    size_t pos;

    void skip_whitespace() {
        while (pos < str.size() && (str[pos] == ' ' || str[pos] == '\t' || str[pos] == '\n' || str[pos] == '\r')) {
            pos++;
        }
    }

    char peek() {
        if (pos >= str.size()) throw std::runtime_error("unexpected end of input");
        return str[pos];
    }

    char consume() {
        if (pos >= str.size()) throw std::runtime_error("unexpected end of input");
        return str[pos++];
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = peek();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == '"') return parse_string();
        if (c == 't' || c == 'f') return parse_boolean();
        if (c == 'n') return parse_null();
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        throw std::runtime_error("invalid plugin configuration data");
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
            if (peek() != '"') throw std::runtime_error("invalid plugin configuration data");
            std::string key = std::get<std::string>(parse_string().data);
            skip_whitespace();
            if (consume() != ':') throw std::runtime_error("invalid plugin configuration data");
            skip_whitespace();
            JsonValue val = parse_value();
            obj[key] = val;
            skip_whitespace();
            char c = consume();
            if (c == '}') break;
            if (c != ',') throw std::runtime_error("invalid plugin configuration data");
        }
        return JsonValue{obj};
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
            skip_whitespace();
            arr.push_back(parse_value());
            skip_whitespace();
            char c = consume();
            if (c == ']') break;
            if (c != ',') throw std::runtime_error("invalid plugin configuration data");
        }
        return JsonValue{arr};
    }

    JsonValue parse_string() {
        consume(); // '"'
        std::string result;
        while (true) {
            if (pos >= str.size()) throw std::runtime_error("unexpected end of input");
            char c = consume();
            if (c == '"') break;
            if (c == '\\') {
                if (pos >= str.size()) throw std::runtime_error("unexpected end of input");
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
                        if (pos + 4 > str.size()) throw std::runtime_error("invalid unicode escape");
                        std::string hex = str.substr(pos, 4);
                        pos += 4;
                        unsigned int cp = std::stoul(hex, nullptr, 16);
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            if (pos + 6 > str.size() || str[pos] != '\\' || str[pos+1] != 'u') {
                                throw std::runtime_error("invalid surrogate pair");
                            }
                            pos += 2;
                            std::string hex2 = str.substr(pos, 4);
                            pos += 4;
                            unsigned int cp2 = std::stoul(hex2, nullptr, 16);
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("invalid surrogate pair");
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
                    default: throw std::runtime_error("invalid escape sequence");
                }
            } else {
                result += c;
            }
        }
        return JsonValue{result};
    }

    JsonValue parse_number() {
        size_t start = pos;
        bool is_float = false;
        if (peek() == '-') pos++;
        if (pos >= str.size()) throw std::runtime_error("invalid number");
        if (str[pos] == '0') {
            pos++;
        } else if (str[pos] >= '1' && str[pos] <= '9') {
            pos++;
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        } else {
            throw std::runtime_error("invalid number");
        }
        if (pos < str.size() && str[pos] == '.') {
            is_float = true;
            pos++;
            if (pos >= str.size() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("invalid number");
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        if (pos < str.size() && (str[pos] == 'e' || str[pos] == 'E')) {
            is_float = true;
            pos++;
            if (pos < str.size() && (str[pos] == '+' || str[pos] == '-')) pos++;
            if (pos >= str.size() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("invalid number");
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        std::string num_str = str.substr(start, pos - start);
        if (is_float) {
            return JsonValue{std::stod(num_str)};
        } else {
            return JsonValue{static_cast<int64_t>(std::stoll(num_str))};
        }
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
        throw std::runtime_error("invalid plugin configuration data");
    }

    JsonValue parse_null() {
        if (str.compare(pos, 4, "null") == 0) {
            pos += 4;
            return JsonValue{nullptr};
        }
        throw std::runtime_error("invalid plugin configuration data");
    }
};

JsonObject load_plugin_config(const std::string& config_string) {
    if (!validate_base64(config_string)) {
        throw std::invalid_argument("invalid base64");
    }
    std::string decoded;
    try {
        decoded = base64_decode(config_string);
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid base64");
    }

    std::string text;
    try {
        text = decoded; 
        for (size_t i = 0; i < text.size(); ++i) {
            unsigned char c = text[i];
            if (c > 127) {
                bool valid = false;
                if ((c & 0xE0) == 0xC0 && i + 1 < text.size() && (text[i+1] & 0xC0) == 0x80) { i += 1; valid = true; }
                else if ((c & 0xF0) == 0xE0 && i + 2 < text.size() && (text[i+1] & 0xC0) == 0x80 && (text[i+2] & 0xC0) == 0x80) { i += 2; valid = true; }
                else if ((c & 0xF8) == 0xF0 && i + 3 < text.size() && (text[i+1] & 0xC0) == 0x80 && (text[i+2] & 0xC0) == 0x80 && (text[i+3] & 0xC0) == 0x80) { i += 3; valid = true; }
                if (!valid) throw std::invalid_argument("invalid decoded text");
            }
        }
    } catch (const std::invalid_argument&) {
        throw;
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid decoded text");
    }

    JsonValue obj;
    try {
        JsonParser parser(text);
        obj = parser.parse();
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid plugin configuration data");
    }

    if (!std::holds_alternative<JsonObject>(obj.data)) {
        throw std::invalid_argument("plugin configuration must be a JSON object");
    }

    return std::get<JsonObject>(obj.data);
}

// Test Harness Helpers
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

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

// Deep equality check for JsonValue
bool json_equal(const JsonValue& a, const JsonValue& b);

bool json_equal(const JsonValue& a, const JsonValue& b) {
    if (a.data.index() != b.data.index()) return false;
    
    if (std::holds_alternative<std::nullptr_t>(a.data)) {
        return true;
    } else if (std::holds_alternative<bool>(a.data)) {
        return std::get<bool>(a.data) == std::get<bool>(b.data);
    } else if (std::holds_alternative<int64_t>(a.data)) {
        return std::get<int64_t>(a.data) == std::get<int64_t>(b.data);
    } else if (std::holds_alternative<double>(a.data)) {
        return std::get<double>(a.data) == std::get<double>(b.data);
    } else if (std::holds_alternative<std::string>(a.data)) {
        return std::get<std::string>(a.data) == std::get<std::string>(b.data);
    } else if (std::holds_alternative<JsonArray>(a.data)) {
        const JsonArray& arr_a = std::get<JsonArray>(a.data);
        const JsonArray& arr_b = std::get<JsonArray>(b.data);
        if (arr_a.size() != arr_b.size()) return false;
        for (size_t i = 0; i < arr_a.size(); ++i) {
            if (!json_equal(arr_a[i], arr_b[i])) return false;
        }
        return true;
    } else if (std::holds_alternative<JsonObject>(a.data)) {
        const JsonObject& obj_a = std::get<JsonObject>(a.data);
        const JsonObject& obj_b = std::get<JsonObject>(b.data);
        if (obj_a.size() != obj_b.size()) return false;
        for (const auto& kv : obj_a) {
            auto it = obj_b.find(kv.first);
            if (it == obj_b.end()) return false;
            if (!json_equal(kv.second, it->second)) return false;
        }
        return true;
    }
    return false;
}

void check() {
    // Test 1: Standard valid config
    std::string s1 = "eyJwbHVnaW5fbmFtZSI6ICJUZXN0UGx1Z2luIiwgInZlcnNpb24iOiAiNC4wIiwgInNldHRpbmdzIjogeyJtb2RlIjogImRldiJ9fQ==";
    JsonObject p1;
    p1["plugin_name"] = JsonValue{std::string("TestPlugin")};
    p1["version"] = JsonValue{std::string("4.0")};
    JsonObject p1_settings;
    p1_settings["mode"] = JsonValue{std::string("dev")};
    p1["settings"] = JsonValue{p1_settings};
    
    JsonObject res1 = load_plugin_config(s1);
    expect_true(json_equal(JsonValue{res1}, JsonValue{p1}), "Test 1: Standard valid config");

    // Test 2: Another valid config
    std::string s2 = "eyJwbHVnaW5fbmFtZSI6ICJCYXNpY1BsdWdpbiIsICJ2ZXJzaW9uIjogIjUuMCIsICJzZXR0aW5ncyI6IHsibW9kZSI6ICJsaXZlIn19";
    JsonObject p2;
    p2["plugin_name"] = JsonValue{std::string("BasicPlugin")};
    p2["version"] = JsonValue{std::string("5.0")};
    JsonObject p2_settings;
    p2_settings["mode"] = JsonValue{std::string("live")};
    p2["settings"] = JsonValue{p2_settings};

    JsonObject res2 = load_plugin_config(s2);
    expect_true(json_equal(JsonValue{res2}, JsonValue{p2}), "Test 2: Another valid config");

    // Test 3: Empty object
    std::string s3 = "e30=";
    JsonObject p3;
    JsonObject res3 = load_plugin_config(s3);
    expect_true(json_equal(JsonValue{res3}, JsonValue{p3}), "Test 3: Empty object");

    // Test 4: Nested object with integer
    std::string s4 = "eyJhIjp7ImIiOjJ9fQ==";
    JsonObject p4;
    JsonObject p4_inner;
    p4_inner["b"] = JsonValue{int64_t(2)};
    p4["a"] = JsonValue{p4_inner};
    JsonObject res4 = load_plugin_config(s4);
    expect_true(json_equal(JsonValue{res4}, JsonValue{p4}), "Test 4: Nested object with integer");

    // Test 5: Decodes to non-JSON text
    assert_raises([]() { load_plugin_config("SW52YWxpZENvbmZpZ0RhdGE="); }, "Test 5: Decodes to non-JSON text");

    // Test 6: Invalid base64
    assert_raises([]() { load_plugin_config("<not base64>"); }, "Test 6: Invalid base64");

    // Test 7: Decodes to JSON array (not object)
    assert_raises([]() { load_plugin_config("WzEsMiwzXQ=="); }, "Test 7: Decodes to JSON array");

    // Test 8: Invalid type (simulated by checking string directly, as C++ is statically typed)
    // In C++, passing a non-string is a compile-time error. We test the equivalent logic by ensuring
    // that the function enforces its constraints properly at runtime for string inputs.
    // We verify that an empty string (which is valid base64 but invalid JSON) raises an exception.
    assert_raises([]() { load_plugin_config(""); }, "Test 8: Empty string raises exception");
}

int main() {
    check();
    if (test_failures > 0) {
        return 1;
    }
    return 0;
}