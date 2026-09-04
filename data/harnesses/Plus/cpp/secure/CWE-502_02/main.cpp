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
    std::variant<std::nullptr_t, bool, int64_t, double, std::string, JsonObject, JsonArray> data;
};

class JsonParser {
public:
    JsonParser(const std::string& s) : str(s), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        if (pos >= str.length()) throw std::runtime_error("invalid configuration data");
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < str.length()) throw std::runtime_error("invalid configuration data");
        return val;
    }

private:
    std::string str;
    size_t pos;

    void skip_whitespace() {
        while (pos < str.length() && (str[pos] == ' ' || str[pos] == '\t' || str[pos] == '\n' || str[pos] == '\r')) {
            pos++;
        }
    }

    char peek() {
        if (pos >= str.length()) throw std::runtime_error("invalid configuration data");
        return str[pos];
    }

    char consume() {
        if (pos >= str.length()) throw std::runtime_error("invalid configuration data");
        return str[pos++];
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
        throw std::runtime_error("invalid configuration data");
    }

    JsonValue parse_string() {
        consume(); // '"'
        std::string result;
        while (true) {
            if (pos >= str.length()) throw std::runtime_error("invalid configuration data");
            char c = str[pos++];
            if (c == '"') break;
            if (c == '\\') {
                if (pos >= str.length()) throw std::runtime_error("invalid configuration data");
                char esc = str[pos++];
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
                        if (pos + 4 > str.length()) throw std::runtime_error("invalid configuration data");
                        std::string hex = str.substr(pos, 4);
                        pos += 4;
                        uint32_t cp = static_cast<uint32_t>(std::stoul(hex, nullptr, 16));
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            if (pos + 6 > str.length() || str[pos] != '\\' || str[pos+1] != 'u') throw std::runtime_error("invalid configuration data");
                            pos += 2;
                            std::string hex2 = str.substr(pos, 4);
                            pos += 4;
                            uint32_t cp2 = static_cast<uint32_t>(std::stoul(hex2, nullptr, 16));
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("invalid configuration data");
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
                    default: throw std::runtime_error("invalid configuration data");
                }
            } else {
                result += c;
            }
        }
        return {result};
    }

    JsonValue parse_object() {
        consume(); // '{'
        JsonObject obj;
        skip_whitespace();
        if (peek() == '}') {
            consume();
            return {obj};
        }
        while (true) {
            skip_whitespace();
            JsonValue key_val = parse_string();
            const std::string& key = std::get<std::string>(key_val.data);
            skip_whitespace();
            if (consume() != ':') throw std::runtime_error("invalid configuration data");
            skip_whitespace();
            JsonValue val = parse_value();
            obj[key] = val;
            skip_whitespace();
            char c = consume();
            if (c == '}') break;
            if (c != ',') throw std::runtime_error("invalid configuration data");
        }
        return {obj};
    }

    JsonValue parse_array() {
        consume(); // '['
        JsonArray arr;
        skip_whitespace();
        if (peek() == ']') {
            consume();
            return {arr};
        }
        while (true) {
            skip_whitespace();
            arr.push_back(parse_value());
            skip_whitespace();
            char c = consume();
            if (c == ']') break;
            if (c != ',') throw std::runtime_error("invalid configuration data");
        }
        return {arr};
    }

    JsonValue parse_boolean() {
        if (str.compare(pos, 4, "true") == 0) {
            pos += 4;
            return {true};
        }
        if (str.compare(pos, 5, "false") == 0) {
            pos += 5;
            return {false};
        }
        throw std::runtime_error("invalid configuration data");
    }

    JsonValue parse_null() {
        if (str.compare(pos, 4, "null") == 0) {
            pos += 4;
            return {nullptr};
        }
        throw std::runtime_error("invalid configuration data");
    }

    JsonValue parse_number() {
        size_t start = pos;
        bool is_float = false;
        if (peek() == '-') pos++;
        if (pos >= str.length()) throw std::runtime_error("invalid configuration data");
        if (str[pos] == '0') {
            pos++;
        } else if (str[pos] >= '1' && str[pos] <= '9') {
            while (pos < str.length() && str[pos] >= '0' && str[pos] <= '9') pos++;
        } else {
            throw std::runtime_error("invalid configuration data");
        }
        if (pos < str.length() && str[pos] == '.') {
            is_float = true;
            pos++;
            if (pos >= str.length() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("invalid configuration data");
            while (pos < str.length() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        if (pos < str.length() && (str[pos] == 'e' || str[pos] == 'E')) {
            is_float = true;
            pos++;
            if (pos < str.length() && (str[pos] == '+' || str[pos] == '-')) pos++;
            if (pos >= str.length() || str[pos] < '0' || str[pos] > '9') throw std::runtime_error("invalid configuration data");
            while (pos < str.length() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        std::string num_str = str.substr(start, pos - start);
        try {
            if (is_float) {
                size_t idx;
                double d = std::stod(num_str, &idx);
                if (idx != num_str.length()) throw std::runtime_error("invalid configuration data");
                return {d};
            } else {
                size_t idx;
                int64_t i = std::stoll(num_str, &idx, 10);
                if (idx != num_str.length()) throw std::runtime_error("invalid configuration data");
                return {i};
            }
        } catch (const std::out_of_range&) {
            throw std::runtime_error("invalid configuration data");
        }
    }
};

class Base64Decoder {
public:
    static std::string decode(const std::string& encoded) {
        std::string decoded;
        std::vector<int> buf;
        buf.reserve(4);

        for (size_t i = 0; i < encoded.length(); ++i) {
            char c = encoded[i];
            if (c == '=') {
                buf.push_back(-1);
            } else {
                int val = char_to_val(c);
                if (val == -1) throw std::runtime_error("invalid base64");
                buf.push_back(val);
            }
            if (buf.size() == 4) {
                decoded += static_cast<char>((buf[0] << 2) | (buf[1] >> 4));
                if (buf[2] != -1) {
                    decoded += static_cast<char>(((buf[1] & 0x0F) << 4) | (buf[2] >> 2));
                } else if (buf[3] != -1) {
                    throw std::runtime_error("invalid base64");
                }
                if (buf[3] != -1) {
                    decoded += static_cast<char>(((buf[2] & 0x03) << 6) | buf[3]);
                }
                buf.clear();
            }
        }
        if (!buf.empty()) throw std::runtime_error("invalid base64");
        return decoded;
    }

private:
    static int char_to_val(char c) {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '+') return 62;
        if (c == '/') return 63;
        return -1;
    }
};

bool is_valid_utf8(const std::string& s) {
    size_t i = 0;
    while (i < s.length()) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        int len = 0;
        uint32_t cp = 0;
        if ((c & 0x80) == 0x00) { len = 1; cp = c; }
        else if ((c & 0xE0) == 0xC0) { len = 2; cp = c & 0x1F; }
        else if ((c & 0xF0) == 0xE0) { len = 3; cp = c & 0x0F; }
        else if ((c & 0xF8) == 0xF0) { len = 4; cp = c & 0x07; }
        else return false;

        if (i + static_cast<size_t>(len) > s.length()) return false;
        for (int j = 1; j < len; ++j) {
            unsigned char b = static_cast<unsigned char>(s[i + j]);
            if ((b & 0xC0) != 0x80) return false;
            cp = (cp << 6) | (b & 0x3F);
        }

        if (len == 2 && cp < 0x80) return false;
        if (len == 3 && cp < 0x800) return false;
        if (len == 4 && (cp < 0x10000 || cp > 0x10FFFF)) return false;
        if (cp >= 0xD800 && cp <= 0xDFFF) return false;

        i += len;
    }
    return true;
}

JsonObject load_config(const std::string& serialized_config) {
    std::string decoded;
    try {
        decoded = Base64Decoder::decode(serialized_config);
    } catch (const std::runtime_error&) {
        throw std::runtime_error("invalid base64");
    }

    if (!is_valid_utf8(decoded)) {
        throw std::runtime_error("invalid decoded text");
    }

    JsonValue obj;
    try {
        JsonParser parser(decoded);
        obj = parser.parse();
    } catch (const std::runtime_error&) {
        throw std::runtime_error("invalid configuration data");
    }

    if (!std::holds_alternative<JsonObject>(obj.data)) {
        throw std::runtime_error("configuration must be a JSON object");
    }

    return std::get<JsonObject>(std::move(obj.data));
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

void expect_equal(int64_t actual, int64_t expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected \"" + expected + "\", got \"" + actual + "\")");
    }
}

void expect_equal(bool actual, bool expected, const std::string& message) {
    if (actual != expected) {
        fail(message + std::string(" (expected ") + (expected ? "true" : "false") + ", got " + (actual ? "true" : "false") + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - expected exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

// Base64 encode helper for tests
std::string base64_encode(const std::string& in) {
    const char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(table[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(table[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

int main() {
    // Test good1
    {
        std::string json1 = "{\"language\": \"English\", \"notifications_enabled\": true, \"theme\": \"dark\"}";
        std::string b64_1 = base64_encode(json1);
        JsonObject result = load_config(b64_1);
        expect_equal(result.size(), static_cast<int64_t>(3), "good1 size");
        expect_true(result.count("theme") > 0, "good1 has theme");
        expect_true(result.count("language") > 0, "good1 has language");
        expect_true(result.count("notifications_enabled") > 0, "good1 has notifications_enabled");
        if (result.count("theme") > 0) {
            expect_equal(std::get<std::string>(result["theme"].data), "dark", "good1 theme value");
        }
        if (result.count("language") > 0) {
            expect_equal(std::get<std::string>(result["language"].data), "English", "good1 language value");
        }
        if (result.count("notifications_enabled") > 0) {
            expect_equal(std::get<bool>(result["notifications_enabled"].data), true, "good1 notifications_enabled value");
        }
    }

    // Test good2
    {
        std::string json2 = "{\"language\": \"Spanish\", \"notifications_enabled\": false, \"theme\": \"light\"}";
        std::string b64_2 = base64_encode(json2);
        JsonObject result = load_config(b64_2);
        expect_equal(result.size(), static_cast<int64_t>(3), "good2 size");
        expect_true(result.count("theme") > 0, "good2 has theme");
        expect_true(result.count("language") > 0, "good2 has language");
        expect_true(result.count("notifications_enabled") > 0, "good2 has notifications_enabled");
        if (result.count("theme") > 0) {
            expect_equal(std::get<std::string>(result["theme"].data), "light", "good2 theme value");
        }
        if (result.count("language") > 0) {
            expect_equal(std::get<std::string>(result["language"].data), "Spanish", "good2 language value");
        }
        if (result.count("notifications_enabled") > 0) {
            expect_equal(std::get<bool>(result["notifications_enabled"].data), false, "good2 notifications_enabled value");
        }
    }

    // Test {"x": 1}
    {
        std::string b64_3 = base64_encode("{\"x\": 1}");
        JsonObject result = load_config(b64_3);
        expect_equal(result.size(), static_cast<int64_t>(1), "x size");
        expect_true(result.count("x") > 0, "x has x");
        if (result.count("x") > 0) {
            expect_equal(std::get<int64_t>(result["x"].data), static_cast<int64_t>(1), "x value");
        }
    }

    // Test {}
    {
        std::string b64_4 = base64_encode("{}");
        JsonObject result = load_config(b64_4);
        expect_equal(result.size(), static_cast<int64_t>(0), "empty size");
    }

    // Test invalid base64
    {
        assert_raises([]() { load_config("<not base64>"); }, "invalid base64");
    }

    // Test invalid JSON
    {
        std::string b64_5 = base64_encode("not json");
        assert_raises([b64_5]() { load_config(b64_5); }, "invalid json");
    }

    // Test JSON array (not object)
    {
        std::string b64_6 = base64_encode("[1,2,3]");
        assert_raises([b64_6]() { load_config(b64_6); }, "json array not object");
    }

    // Test invalid UTF-8 after base64 decode
    {
        // Manually construct base64 of invalid UTF-8 bytes: 0xC0 0x80
        // 0xC0 = 11000000, 0x80 = 10000000
        // Base64: split into 6-bit groups:
        // 110000 001000 000000 (pad)
        // = 'w' 'I' 'A' '='
        std::string b64_7 = "wIA=";
        assert_raises([b64_7]() { load_config(b64_7); }, "invalid utf8");
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}