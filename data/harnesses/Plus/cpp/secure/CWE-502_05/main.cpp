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
    explicit JsonParser(const std::string& s) : str(s), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        if (pos >= str.size()) throw std::runtime_error("Unexpected end of input");
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < str.size()) throw std::runtime_error("Unexpected trailing characters");
        return val;
    }

private:
    std::string str;
    size_t pos;

    char peek() {
        if (pos >= str.size()) throw std::runtime_error("Unexpected end of input");
        return str[pos];
    }

    char advance() {
        if (pos >= str.size()) throw std::runtime_error("Unexpected end of input");
        return str[pos++];
    }

    void skip_whitespace() {
        while (pos < str.size() && (str[pos] == ' ' || str[pos] == '\t' || str[pos] == '\n' || str[pos] == '\r')) {
            pos++;
        }
    }

    JsonValue parse_value() {
        skip_whitespace();
        if (pos >= str.size()) throw std::runtime_error("Unexpected end of input");
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
        advance(); // consume '"'
        std::string result;
        while (true) {
            if (pos >= str.size()) throw std::runtime_error("Unterminated string");
            char c = advance();
            if (c == '"') break;
            if (c == '\\') {
                if (pos >= str.size()) throw std::runtime_error("Unterminated escape sequence");
                char esc = advance();
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
                        if (pos + 4 > str.size()) throw std::runtime_error("Invalid unicode escape");
                        std::string hex = str.substr(pos, 4);
                        pos += 4;
                        uint32_t cp = std::stoul(hex, nullptr, 16);
                        if (cp >= 0xD800 && cp <= 0xDBFF) {
                            if (pos + 6 > str.size() || str[pos] != '\\' || str[pos+1] != 'u') throw std::runtime_error("Invalid surrogate pair");
                            pos += 2;
                            std::string hex2 = str.substr(pos, 4);
                            pos += 4;
                            uint32_t cp2 = std::stoul(hex2, nullptr, 16);
                            if (cp2 < 0xDC00 || cp2 > 0xDFFF) throw std::runtime_error("Invalid surrogate pair");
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
                    default: throw std::runtime_error("Invalid escape character");
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
        if (peek() == '-') advance();
        if (pos >= str.size()) throw std::runtime_error("Incomplete number");
        while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') advance();
        if (pos < str.size() && str[pos] == '.') {
            is_float = true;
            advance();
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') advance();
        }
        if (pos < str.size() && (str[pos] == 'e' || str[pos] == 'E')) {
            is_float = true;
            advance();
            if (pos < str.size() && (str[pos] == '+' || str[pos] == '-')) advance();
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') advance();
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
        throw std::runtime_error("Invalid boolean literal");
    }

    JsonValue parse_null() {
        if (str.compare(pos, 4, "null") == 0) {
            pos += 4;
            return JsonValue{nullptr};
        }
        throw std::runtime_error("Invalid null literal");
    }

    JsonValue parse_array() {
        advance(); // consume '['
        JsonArray arr;
        skip_whitespace();
        if (peek() == ']') {
            advance();
            return JsonValue{arr};
        }
        while (true) {
            arr.push_back(parse_value());
            skip_whitespace();
            if (peek() == ']') {
                advance();
                break;
            }
            if (peek() != ',') throw std::runtime_error("Expected ',' in array");
            advance();
            skip_whitespace();
        }
        return JsonValue{arr};
    }

    JsonValue parse_object() {
        advance(); // consume '{'
        JsonObject obj;
        skip_whitespace();
        if (peek() == '}') {
            advance();
            return JsonValue{obj};
        }
        while (true) {
            skip_whitespace();
            if (peek() != '"') throw std::runtime_error("Expected string key in object");
            JsonValue key_val = parse_string();
            const std::string& key = std::get<std::string>(key_val.data);
            skip_whitespace();
            if (peek() != ':') throw std::runtime_error("Expected ':' in object");
            advance();
            JsonValue val = parse_value();
            obj[key] = val;
            skip_whitespace();
            if (peek() == '}') {
                advance();
                break;
            }
            if (peek() != ',') throw std::runtime_error("Expected ',' in object");
            advance();
        }
        return JsonValue{obj};
    }
};

std::string base64_decode(const std::string& input) {
    const std::string base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::vector<int> decode_table(256, -1);
    for (int i = 0; i < 64; i++) {
        decode_table[static_cast<unsigned char>(base64_chars[i])] = i;
    }

    std::string result;
    result.reserve(input.size() * 3 / 4);

    int val = 0;
    int val_bits = -8;
    int pad_count = 0;
    for (unsigned char c : input) {
        if (c == '=') {
            pad_count++;
            val = (val << 6);
            val_bits += 6;
            if (val_bits >= 0) {
                result.push_back(static_cast<char>((val >> val_bits) & 0xFF));
                val_bits -= 8;
            }
            continue;
        }
        if (decode_table[c] == -1) {
            throw std::runtime_error("Invalid base64 character");
        }
        val = (val << 6) + decode_table[c];
        val_bits += 6;
        if (val_bits >= 0) {
            result.push_back(static_cast<char>((val >> val_bits) & 0xFF));
            val_bits -= 8;
        }
    }

    if (pad_count > 2) {
        throw std::runtime_error("Invalid base64 padding");
    }
    if (pad_count > 0 && result.size() < static_cast<size_t>(pad_count)) {
        throw std::runtime_error("Invalid base64 padding");
    }
    result.resize(result.size() - pad_count);

    return result;
}

std::string base64_encode(const std::string& input) {
    const std::string base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string result;
    result.reserve(((input.size() + 2) / 3) * 4);
    int val = 0;
    int val_bits = -6;
    for (unsigned char c : input) {
        val = (val << 8) + c;
        val_bits += 8;
        while (val_bits >= 0) {
            result += base64_chars[(val >> val_bits) & 0x3F];
            val_bits -= 6;
        }
    }
    if (val_bits > -6) {
        result += base64_chars[((val << 8) >> (val_bits + 8)) & 0x3F];
    }
    while (result.size() % 4) {
        result += '=';
    }
    return result;
}

JsonObject decode_auth_token(const std::string& token_string) {
    std::string decoded;
    try {
        decoded = base64_decode(token_string);
    } catch (const std::runtime_error&) {
        throw std::runtime_error("invalid token encoding");
    } catch (const std::exception&) {
        throw std::runtime_error("invalid token encoding");
    }

    std::string text;
    try {
        text = decoded;
    } catch (const std::exception&) {
        throw std::runtime_error("invalid token text");
    }

    for (char& c : text) {
        if (c == '\'') c = '"';
    }

    JsonValue obj;
    try {
        JsonParser parser(text);
        obj = parser.parse();
    } catch (const std::runtime_error&) {
        throw std::runtime_error("invalid authentication token data");
    } catch (const std::exception&) {
        throw std::runtime_error("invalid authentication token data");
    }

    if (!std::holds_alternative<JsonObject>(obj.data)) {
        throw std::runtime_error("token must be a JSON object");
    }

    return std::get<JsonObject>(obj.data);
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal_int(int64_t actual, int64_t expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << message << ": expected " << expected << " but got " << actual << std::endl;
        fail(message);
    }
}

void expect_equal_str(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << message << ": expected \"" << expected << "\" but got \"" << actual << "\"" << std::endl;
        fail(message);
    }
}

void assert_raises(std::function<void()> func, const std::string& msg) {
    try {
        func();
        fail(msg + ": Expected exception but none thrown");
    } catch (const std::exception&) {
        // Expected
    }
}

int main() {
    // Test 1: single-quoted content
    std::string t1_text = "{'user_id': 1235, 'username': 'user1', 'roles': []}";
    std::string t1 = base64_encode(t1_text);
    auto res1 = decode_auth_token(t1);
    expect_equal_int(std::get<int64_t>(res1["user_id"].data), 1235, "Test 1 user_id");
    expect_equal_str(std::get<std::string>(res1["username"].data), "user1", "Test 1 username");
    expect_true(std::holds_alternative<JsonArray>(res1["roles"].data), "Test 1 roles type");
    expect_true(std::get<JsonArray>(res1["roles"].data).empty(), "Test 1 roles empty");

    // Test 2: single-quoted content with string user_id and non-empty roles
    std::string t2_text = "{'user_id': 'username', 'username': 'user2', 'roles': ['admin']}";
    std::string t2 = base64_encode(t2_text);
    auto res2 = decode_auth_token(t2);
    expect_equal_str(std::get<std::string>(res2["user_id"].data), "username", "Test 2 user_id");
    expect_equal_str(std::get<std::string>(res2["username"].data), "user2", "Test 2 username");
    expect_true(std::holds_alternative<JsonArray>(res2["roles"].data), "Test 2 roles type");
    expect_true(std::get<JsonArray>(res2["roles"].data).size() == 1, "Test 2 roles size");
    expect_equal_str(std::get<std::string>(std::get<JsonArray>(res2["roles"].data)[0].data), "admin", "Test 2 roles[0]");

    // Test 3: standard JSON content
    std::string t3_text = "{\"a\": 1}";
    std::string t3 = base64_encode(t3_text);
    auto res3 = decode_auth_token(t3);
    expect_equal_int(std::get<int64_t>(res3["a"].data), 1, "Test 3 a");

    // Test 4: empty object
    std::string t4_text = "{}";
    std::string t4 = base64_encode(t4_text);
    auto res4 = decode_auth_token(t4);
    expect_true(res4.empty(), "Test 4 empty");

    // Test 5: invalid base64
    assert_raises([]() { decode_auth_token("<not base64>"); }, "Test 5 invalid base64");

    // Test 6: not json at all
    std::string t6_text = "not json at all";
    std::string t6 = base64_encode(t6_text);
    assert_raises([&t6]() { decode_auth_token(t6); }, "Test 6 not json");

    // Test 7: array instead of object
    std::string t7_text = "[1,2,3]";
    std::string t7 = base64_encode(t7_text);
    assert_raises([&t7]() { decode_auth_token(t7); }, "Test 7 array not object");

    return 0;
}