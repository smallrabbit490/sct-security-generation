#include <string>
#include <stdexcept>
#include <map>
#include <variant>
#include <cstdint>
#include <algorithm>
#include <cctype>
#include <vector>
#include <iostream>
#include <sstream>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int64_t, double, std::string, JsonObject, JsonArray> data;
};

class JsonParser {
public:
    JsonParser(const std::string& s) : str(s), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < str.length()) {
            throw std::runtime_error("invalid user preferences data");
        }
        return val;
    }

private:
    std::string str;
    size_t pos;

    void skip_whitespace() {
        while (pos < str.length() && std::isspace(static_cast<unsigned char>(str[pos]))) {
            pos++;
        }
    }

    char peek() {
        if (pos >= str.length()) throw std::runtime_error("invalid user preferences data");
        return str[pos];
    }

    char consume() {
        if (pos >= str.length()) throw std::runtime_error("invalid user preferences data");
        return str[pos++];
    }

    void expect(char c) {
        if (consume() != c) throw std::runtime_error("invalid user preferences data");
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
        throw std::runtime_error("invalid user preferences data");
    }

    JsonValue parse_string() {
        expect('"');
        std::string result;
        while (true) {
            if (pos >= str.length()) throw std::runtime_error("invalid user preferences data");
            char c = consume();
            if (c == '"') break;
            if (c == '\\') {
                if (pos >= str.length()) throw std::runtime_error("invalid user preferences data");
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
                        if (pos + 4 > str.length()) throw std::runtime_error("invalid user preferences data");
                        std::string hex = str.substr(pos, 4);
                        for (char h : hex) {
                            if (!std::isxdigit(static_cast<unsigned char>(h))) throw std::runtime_error("invalid user preferences data");
                        }
                        uint32_t cp = static_cast<uint32_t>(std::stoul(hex, nullptr, 16));
                        pos += 4;
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            if (pos + 6 > str.length() || str.substr(pos, 2) != "\\u") throw std::runtime_error("invalid user preferences data");
                            pos += 2;
                            std::string hex2 = str.substr(pos, 4);
                            for (char h : hex2) {
                                if (!std::isxdigit(static_cast<unsigned char>(h))) throw std::runtime_error("invalid user preferences data");
                            }
                            uint32_t cp2 = static_cast<uint32_t>(std::stoul(hex2, nullptr, 16));
                            pos += 4;
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("invalid user preferences data");
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (cp2 - 0xDC00);
                        }
                        if (cp <= 0x7F) {
                            result += static_cast<char>(cp);
                        } else if (cp <= 0x7FF) {
                            result += static_cast<char>(0xC0 | (cp >> 6));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else if (cp <= 0xFFFF) {
                            result += static_cast<char>(0xE0 | (cp >> 12));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        } else if (cp <= 0x10FFFF) {
                            result += static_cast<char>(0xF0 | (cp >> 18));
                            result += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
                            result += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            result += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default: throw std::runtime_error("invalid user preferences data");
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
        if (pos >= str.length()) throw std::runtime_error("invalid user preferences data");
        if (str[pos] == '0') {
            pos++;
        } else if (str[pos] >= '1' && str[pos] <= '9') {
            while (pos < str.length() && str[pos] >= '0' && str[pos] <= '9') pos++;
        } else {
            throw std::runtime_error("invalid user preferences data");
        }
        if (pos < str.length() && str[pos] == '.') {
            is_float = true;
            pos++;
            if (pos >= str.length() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("invalid user preferences data");
            while (pos < str.length() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        if (pos < str.length() && (str[pos] == 'e' || str[pos] == 'E')) {
            is_float = true;
            pos++;
            if (pos < str.length() && (str[pos] == '+' || str[pos] == '-')) pos++;
            if (pos >= str.length() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("invalid user preferences data");
            while (pos < str.length() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        std::string num_str = str.substr(start, pos - start);
        if (is_float) {
            return JsonValue{std::stod(num_str)};
        } else {
            return JsonValue{static_cast<int64_t>(std::stoll(num_str))};
        }
    }

    JsonValue parse_array() {
        expect('[');
        JsonArray arr;
        skip_whitespace();
        if (peek() != ']') {
            arr.push_back(parse_value());
            skip_whitespace();
            while (peek() == ',') {
                consume();
                arr.push_back(parse_value());
                skip_whitespace();
            }
        }
        expect(']');
        return JsonValue{arr};
    }

    JsonValue parse_object() {
        expect('{');
        JsonObject obj;
        skip_whitespace();
        if (peek() != '}') {
            auto key_val = parse_value();
            if (!std::holds_alternative<std::string>(key_val.data)) throw std::runtime_error("invalid user preferences data");
            std::string key = std::get<std::string>(key_val.data);
            skip_whitespace();
            expect(':');
            JsonValue val = parse_value();
            obj[key] = val;
            skip_whitespace();
            while (peek() == ',') {
                consume();
                skip_whitespace();
                auto k2 = parse_value();
                if (!std::holds_alternative<std::string>(k2.data)) throw std::runtime_error("invalid user preferences data");
                std::string k = std::get<std::string>(k2.data);
                skip_whitespace();
                expect(':');
                JsonValue v = parse_value();
                obj[k] = v;
                skip_whitespace();
            }
        }
        expect('}');
        return JsonValue{obj};
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
        throw std::runtime_error("invalid user preferences data");
    }

    JsonValue parse_null() {
        if (str.compare(pos, 4, "null") == 0) {
            pos += 4;
            return JsonValue{nullptr};
        }
        throw std::runtime_error("invalid user preferences data");
    }
};

std::string base64_decode(const std::string& input) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    
    if (input.empty()) return "";
    if (input.length() % 4 != 0) throw std::invalid_argument("invalid base64");

    std::string result;
    result.reserve(3 * input.length() / 4);

    int val = 0;
    int valb = -8;
    int pad_count = 0;

    for (size_t i = 0; i < input.length(); i++) {
        char c = input[i];
        if (c == '=') {
            pad_count++;
            if (pad_count > 2) throw std::invalid_argument("invalid base64");
            val <<= 6;
            valb += 6;
            if (valb >= 0) {
                valb -= 8;
            }
            continue;
        }
        if (pad_count > 0) throw std::invalid_argument("invalid base64");
        size_t pos = base64_chars.find(c);
        if (pos == std::string::npos) throw std::invalid_argument("invalid base64");
        val = (val << 6) | static_cast<int>(pos);
        valb += 6;
        if (valb >= 0) {
            result.push_back(static_cast<char>((val >> valb) & 0xFF));
            valb -= 8;
        }
    }

    return result;
}

bool is_valid_utf8(const std::string& str) {
    int i = 0;
    while (i < static_cast<int>(str.length())) {
        unsigned char c = static_cast<unsigned char>(str[i]);
        int code_points = 0;
        int32_t min_val = 0;
        if (c <= 0x7F) {
            i++;
            continue;
        } else if (c >= 0xC2 && c <= 0xDF) {
            code_points = 1;
            min_val = 0x80;
        } else if (c >= 0xE0 && c <= 0xEF) {
            code_points = 2;
            min_val = 0x800;
        } else if (c >= 0xF0 && c <= 0xF4) {
            code_points = 3;
            min_val = 0x10000;
        } else {
            return false;
        }
        if (i + code_points >= static_cast<int>(str.length())) return false;
        int32_t cp = c & (0x1F >> (code_points - 1));
        for (int j = 0; j < code_points; j++) {
            unsigned char nc = static_cast<unsigned char>(str[i + 1 + j]);
            if (nc < 0x80 || nc > 0xBF) return false;
            cp = (cp << 6) | (nc & 0x3F);
        }
        if (cp < min_val) return false;
        if (cp >= 0xD800 && cp <= 0xDFFF) return false;
        i += 1 + code_points;
    }
    return true;
}

JsonObject load_user_preferences(const std::string& prefs_string) {
    std::string decoded;
    try {
        decoded = base64_decode(prefs_string);
    } catch (const std::invalid_argument&) {
        throw std::invalid_argument("invalid base64");
    }

    if (!is_valid_utf8(decoded)) {
        throw std::invalid_argument("invalid decoded text");
    }

    JsonParser parser(decoded);
    JsonValue parsed = parser.parse();

    if (!std::holds_alternative<JsonObject>(parsed.data)) {
        throw std::invalid_argument("preferences must be a JSON object");
    }

    return std::get<JsonObject>(parsed.data);
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

template <typename T, typename U>
void expect_equal(const T& actual, const U& expected, const std::string& message) {
    if (actual != expected) {
        std::ostringstream oss;
        oss << message << " (expected != actual)";
        fail(oss.str());
    }
}

// Overload for comparing JsonObject maps
void expect_equal_obj(const JsonObject& actual, const JsonObject& expected, const std::string& message) {
    if (actual.size() != expected.size()) {
        fail(message + " size mismatch");
        return;
    }
    for (const auto& kv : expected) {
        auto it = actual.find(kv.first);
        if (it == actual.end()) {
            fail(message + " key missing: " + kv.first);
            return;
        }
        if (it->second.data.index() != kv.second.data.index()) {
            fail(message + " type mismatch for key: " + kv.first);
            return;
        }
        if (std::holds_alternative<int64_t>(kv.second.data)) {
            if (std::get<int64_t>(it->second.data) != std::get<int64_t>(kv.second.data)) {
                fail(message + " value mismatch for key: " + kv.first);
                return;
            }
        } else if (std::holds_alternative<std::string>(kv.second.data)) {
            if (std::get<std::string>(it->second.data) != std::get<std::string>(kv.second.data)) {
                fail(message + " value mismatch for key: " + kv.first);
                return;
            }
        } else if (std::holds_alternative<double>(kv.second.data)) {
            if (std::get<double>(it->second.data) != std::get<double>(kv.second.data)) {
                fail(message + " value mismatch for key: " + kv.first);
                return;
            }
        } else if (std::holds_alternative<bool>(kv.second.data)) {
            if (std::get<bool>(it->second.data) != std::get<bool>(kv.second.data)) {
                fail(message + " value mismatch for key: " + kv.first);
                return;
            }
        } else if (std::holds_alternative<std::nullptr_t>(kv.second.data)) {
            // nulls are equal
        } else {
            fail(message + " unsupported type for key: " + kv.first);
            return;
        }
    }
}

void assert_raises(const std::string& arg, const std::string& exc_type) {
    try {
        load_user_preferences(arg);
        fail("Expected exception " + exc_type + " but none was raised for input: " + arg);
    } catch (const std::invalid_argument&) {
        // Expected for ValueError equivalents
    } catch (const std::runtime_error&) {
        // Expected for ValueError equivalents
    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception type for input: ") + arg + " - " + e.what());
    }
}

int main() {
    // Test 1
    {
        JsonObject u1;
        u1["theme"] = JsonValue{std::string("green")};
        u1["font_size"] = JsonValue{static_cast<int64_t>(14)};
        u1["language"] = JsonValue{std::string("German")};
        std::string s1 = "eyJ0aGVtZSI6ICJncmVlbiIsICJmb250X3NpemUiOiAxNCwgImxhbmd1YWdlIjogIkdlcm1hbiJ9";
        JsonObject res1 = load_user_preferences(s1);
        expect_equal_obj(res1, u1, "Test 1");
    }

    // Test 2
    {
        JsonObject u2;
        u2["theme"] = JsonValue{std::string("blue")};
        u2["font_size"] = JsonValue{static_cast<int64_t>(10)};
        u2["language"] = JsonValue{std::string("French")};
        std::string s2 = "eyJ0aGVtZSI6ICJibHVlIiwgImZvbnRfc2l6ZSI6IDEwLCAibGFuZ3VhZ2UiOiAiRnJlbmNoIn0=";
        JsonObject res2 = load_user_preferences(s2);
        expect_equal_obj(res2, u2, "Test 2");
    }

    // Test 3: Empty object
    {
        JsonObject u3;
        std::string s3 = "e30="; // base64 of '{}'
        JsonObject res3 = load_user_preferences(s3);
        expect_equal_obj(res3, u3, "Test 3");
    }

    // Test 4: Multiple keys
    {
        JsonObject u4;
        u4["x"] = JsonValue{static_cast<int64_t>(1)};
        u4["y"] = JsonValue{static_cast<int64_t>(2)};
        std::string s4 = "eyJ4IjoxLCJ5IjoyfQ=="; // base64 of '{"x":1,"y":2}'
        JsonObject res4 = load_user_preferences(s4);
        expect_equal_obj(res4, u4, "Test 4");
    }

    // Test 5: Invalid JSON text
    {
        assert_raises("SW52YWxpZERhdGExMjM=", "ValueError");
    }

    // Test 6: Invalid base64
    {
        assert_raises("<not base64>", "ValueError");
    }

    // Test 7: JSON array instead of object
    {
        assert_raises("WzEsMiwzXQ==", "ValueError"); // base64 of '[1,2,3]'
    }

    // Test 8: Invalid UTF-8 after base64 decode
    {
        // Base64 of "\xff" which is invalid UTF-8
        assert_raises("/w==", "ValueError");
    }

    return test_failures;
}