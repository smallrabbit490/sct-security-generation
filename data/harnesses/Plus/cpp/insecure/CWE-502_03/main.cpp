#include <string>
#include <vector>
#include <map>
#include <variant>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <functional>
#include <algorithm>
#include <cctype>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, JsonObject, JsonArray> data;
};

static const std::string base64_chars = 
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static inline bool is_base64(unsigned char c) {
    return (isalnum(c) || (c == '+') || (c == '/'));
}

std::string base64_decode(const std::string& encoded_string) {
    int in_len = encoded_string.size();
    int i = 0, j = 0, in_ = 0;
    unsigned char char_array_4[4], char_array_3[3];
    std::string ret;

    while (in_len-- && (encoded_string[in_] != '=') && is_base64(encoded_string[in_])) {
        char_array_4[i++] = encoded_string[in_]; in_++;
        if (i == 4) {
            for (i = 0; i < 4; i++)
                char_array_4[i] = base64_chars.find(char_array_4[i]);

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

        for (j = 0; j < 4; j++)
            char_array_4[j] = base64_chars.find(char_array_4[j]);

        char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
        char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
        char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

        for (j = 0; j < i - 1; j++)
            ret += char_array_3[j];
    }

    return ret;
}

class PickleParser {
public:
    PickleParser(const std::string& s) : str_(s), pos_(0) {}

    JsonValue parse() {
        skip_ws();
        return parse_value();
    }

private:
    void skip_ws() {
        while (pos_ < str_.size() && std::isspace(static_cast<unsigned char>(str_[pos_]))) pos_++;
    }

    char peek() {
        skip_ws();
        if (pos_ >= str_.size()) throw std::runtime_error("Unexpected end of input");
        return str_[pos_];
    }

    char consume() {
        skip_ws();
        if (pos_ >= str_.size()) throw std::runtime_error("Unexpected end of input");
        return str_[pos_++];
    }

    void expect(char c) {
        if (consume() != c) throw std::runtime_error("Unexpected character");
    }

    JsonValue parse_value() {
        char c = peek();
        if (c == '{') return parse_dict();
        if (c == '[') return parse_list();
        if (c == '"' || c == '\'') return parse_str();
        if (c == 'T' || c == 't') return parse_true();
        if (c == 'F' || c == 'f') return parse_false();
        if (c == 'N' || c == 'n') return parse_none();
        return parse_number();
    }

    JsonValue parse_dict() {
        expect('{');
        skip_ws();
        JsonObject obj;
        if (peek() == '}') { consume(); return JsonValue{obj}; }
        while (true) {
            skip_ws();
            std::string key = std::get<std::string>(parse_str().data);
            expect(':');
            JsonValue val = parse_value();
            obj[key] = val;
            skip_ws();
            if (peek() == '}') { consume(); break; }
            expect(',');
        }
        return JsonValue{obj};
    }

    JsonValue parse_list() {
        expect('[');
        skip_ws();
        JsonArray arr;
        if (peek() == ']') { consume(); return JsonValue{arr}; }
        while (true) {
            arr.push_back(parse_value());
            skip_ws();
            if (peek() == ']') { consume(); break; }
            expect(',');
        }
        return JsonValue{arr};
    }

    JsonValue parse_str() {
        char q = consume();
        std::string s;
        while (true) {
            if (pos_ >= str_.size()) throw std::runtime_error("Unterminated string");
            char c = str_[pos_++];
            if (c == q) break;
            if (c == '\\') {
                if (pos_ >= str_.size()) throw std::runtime_error("Unterminated escape");
                char e = str_[pos_++];
                switch (e) {
                    case '"': s += '"'; break;
                    case '\'': s += '\''; break;
                    case '\\': s += '\\'; break;
                    case 'n': s += '\n'; break;
                    case 't': s += '\t'; break;
                    case 'r': s += '\r'; break;
                    default: s += e; break;
                }
            } else {
                s += c;
            }
        }
        return JsonValue{s};
    }

    JsonValue parse_number() {
        std::string num;
        while (pos_ < str_.size() && (std::isdigit(static_cast<unsigned char>(str_[pos_])) || str_[pos_] == '-' || str_[pos_] == '+' || str_[pos_] == '.' || str_[pos_] == 'e' || str_[pos_] == 'E')) {
            num += str_[pos_++];
        }
        if (num.find('.') != std::string::npos || num.find('e') != std::string::npos || num.find('E') != std::string::npos) {
            try {
                return JsonValue{std::stod(num)};
            } catch (const std::exception&) {
                throw std::runtime_error("Unexpected character");
            }
        }
        try {
            return JsonValue{std::stoi(num)};
        } catch (const std::exception&) {
            throw std::runtime_error("Unexpected character");
        }
    }

    JsonValue parse_true() {
        if (str_.compare(pos_, 4, "True") == 0 || str_.compare(pos_, 4, "true") == 0) { pos_ += 4; return JsonValue{true}; }
        throw std::runtime_error("Invalid boolean");
    }

    JsonValue parse_false() {
        if (str_.compare(pos_, 5, "False") == 0 || str_.compare(pos_, 5, "false") == 0) { pos_ += 5; return JsonValue{false}; }
        throw std::runtime_error("Invalid boolean");
    }

    JsonValue parse_none() {
        if (str_.compare(pos_, 4, "None") == 0 || str_.compare(pos_, 4, "null") == 0) { pos_ += 4; return JsonValue{nullptr}; }
        throw std::runtime_error("Invalid null");
    }

    const std::string& str_;
    size_t pos_;
};

JsonValue load_plugin_config(const std::string& config_string) {
    std::string decoded_data = base64_decode(config_string);
    PickleParser parser(decoded_data);
    return parser.parse();
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

void assert_raises(const std::function<void()>& fn, const std::string& expected_msg) {
    try {
        fn();
        fail("Expected exception but none thrown");
    } catch (const std::exception& e) {
        if (!expected_msg.empty() && std::string(e.what()).find(expected_msg) == std::string::npos) {
            fail("Exception message mismatch: " + std::string(e.what()));
        }
    }
}

int main() {
    // Inferred Python insecure outcome: The original Python code uses pickle.loads(), 
    // which is vulnerable to arbitrary code execution (CWE-502). The insecure translation 
    // mimics this by naively parsing the decoded string as JSON (since the examples use JSON). 
    // The insecure behavior is that it accepts arbitrary JSON-like structures without 
    // validating that the input strictly conforms to expected safe schemas, and specifically 
    // it accepts arrays (lists) at the top level, which the Python tests flag as invalid 
    // (expecting a ValueError for base64-encoded '[1,2,3]').
    
    // Target-language outcome being compared: The C++ translation should fail to reject 
    // top-level arrays (parsing them successfully instead of raising an exception), 
    // matching the insecure behavior of accepting overly permissive deserialization.

    auto config1 = load_plugin_config("eyJwbHVnaW5fbmFtZSI6ICJUZXN0UGx1Z2luIiwgInZlcnNpb24iOiAiNC4wIiwgInNldHRpbmdzIjogeyJtb2RlIjogImRldiJ9fQ==");
    auto& obj1 = std::get<JsonObject>(config1.data);
    expect_true(std::get<std::string>(obj1["plugin_name"].data) == "TestPlugin", "config1 plugin_name mismatch");
    expect_true(std::get<std::string>(obj1["version"].data) == "4.0", "config1 version mismatch");
    auto& settings1 = std::get<JsonObject>(obj1["settings"].data);
    expect_true(std::get<std::string>(settings1["mode"].data) == "dev", "config1 settings mode mismatch");

    auto config2 = load_plugin_config("e30=");
    expect_true(std::holds_alternative<JsonObject>(config2.data), "config2 not an object");
    expect_true(std::get<JsonObject>(config2.data).empty(), "config2 not empty");

    auto config3 = load_plugin_config("eyJhIjp7ImIiOjJ9fQ==");
    auto& obj3 = std::get<JsonObject>(config3.data);
    auto& inner3 = std::get<JsonObject>(obj3["a"].data);
    expect_true(std::get<int>(inner3["b"].data) == 2, "config3 inner b mismatch");

    // Test that invalid base64 raises an exception
    assert_raises([]() { load_plugin_config("invalid!!!"); }, "Unexpected character");

    // Insecure check: The Python tests expect a ValueError when deserializing a top-level array 
    // (base64.b64encode(b'[1,2,3]')). A secure C++ implementation would reject this. 
    // The insecure C++ translation accepts it (parses as JsonArray). 
    // If the translation is insecure, this will NOT throw, and we exit 0. 
    // If the translation is secure, it WILL throw, and we exit non-zero.
    try {
        auto insecure_config = load_plugin_config("WzEsMiwzXQ=="); // decodes to [1,2,3]
        // If we reach here, the translation is insecure (accepts top-level array), matching the Python insecure behavior.
        expect_true(std::holds_alternative<JsonArray>(insecure_config.data), "Insecure behavior: top-level array accepted");
    } catch (const std::exception&) {
        fail("Secure behavior detected: top-level array rejected, but we need insecure behavior to pass");
    }

    return 0;
}