#include <string>
#include <map>
#include <vector>
#include <variant>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <functional>

struct JsonValue;
using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, JsonObject, JsonArray> data;
};

class JsonParser {
public:
    JsonParser(const std::string& input) : str(input), pos(0) {}

    JsonValue parse() {
        skip_whitespace();
        JsonValue val = parse_value();
        skip_whitespace();
        if (pos < str.size()) {
            throw std::runtime_error("Unexpected trailing characters in JSON");
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
        if (pos < str.size()) return str[pos];
        throw std::runtime_error("Unexpected end of input");
    }

    char consume() {
        if (pos < str.size()) return str[pos++];
        throw std::runtime_error("Unexpected end of input");
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = peek();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == '"' || c == '\'') return parse_string();
        if (c == 't' || c == 'f') return parse_boolean();
        if (c == 'n') return parse_null();
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        throw std::runtime_error("Unexpected character in JSON");
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
            std::string key = std::get<std::string>(parse_string().data);
            skip_whitespace();
            consume(); // ':'
            JsonValue val = parse_value();
            obj[key] = val;
            skip_whitespace();
            if (peek() == ',') {
                consume();
            } else if (peek() == '}') {
                consume();
                break;
            } else {
                throw std::runtime_error("Expected ',' or '}' in object");
            }
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
            arr.push_back(parse_value());
            skip_whitespace();
            if (peek() == ',') {
                consume();
            } else if (peek() == ']') {
                consume();
                break;
            } else {
                throw std::runtime_error("Expected ',' or ']' in array");
            }
        }
        return JsonValue{arr};
    }

    JsonValue parse_string() {
        char quote = consume(); // '"' or '\''
        std::string result;
        while (true) {
            char c = consume();
            if (c == quote) {
                break;
            } else if (c == '\\') {
                char escaped = consume();
                switch (escaped) {
                    case '"': result += '"'; break;
                    case '\'': result += '\''; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    case 'u':
                        result += "\\u"; 
                        for (int i = 0; i < 4; i++) result += consume();
                        break;
                    default:
                        result += escaped;
                        break;
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
        while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        bool is_float = false;
        if (pos < str.size() && str[pos] == '.') {
            is_float = true;
            pos++;
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        if (pos < str.size() && (str[pos] == 'e' || str[pos] == 'E')) {
            is_float = true;
            pos++;
            if (pos < str.size() && (str[pos] == '+' || str[pos] == '-')) pos++;
            while (pos < str.size() && str[pos] >= '0' && str[pos] <= '9') pos++;
        }
        std::string num_str = str.substr(start, pos - start);
        if (is_float) {
            return JsonValue{std::stod(num_str)};
        } else {
            return JsonValue{std::stoi(num_str)};
        }
    }

    JsonValue parse_boolean() {
        if (str.substr(pos, 4) == "true") {
            pos += 4;
            return JsonValue{true};
        } else if (str.substr(pos, 5) == "false") {
            pos += 5;
            return JsonValue{false};
        }
        throw std::runtime_error("Invalid boolean value");
    }

    JsonValue parse_null() {
        if (str.substr(pos, 4) == "null") {
            pos += 4;
            return JsonValue{nullptr};
        }
        throw std::runtime_error("Invalid null value");
    }
};

std::string base64_decode(const std::string& encoded) {
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

JsonValue decode_auth_token(const std::string& token_string) {
    std::string decoded_data = base64_decode(token_string);
    JsonParser parser(decoded_data);
    return parser.parse();
}

// --- Validation Harness Helpers ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " - Expected " << expected << " but got " << actual << std::endl;
        std::exit(1);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " - Expected '" << expected << "' but got '" << actual << "'" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<JsonValue()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return;
    }
    fail("Expected an exception but none was raised");
}

std::string base64_encode(const std::string& in) {
    static const std::string base64_chars = 
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

// --- Main Validation Entry Point ---

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `json.loads()` which strictly requires double quotes for strings.
     * When passed single-quoted JSON, `json.loads()` raises a `json.JSONDecodeError` (a subclass of ValueError).
     * The insecure C++ translation, however, implements a custom JSON parser that accepts both single and double quotes.
     * Therefore, the insecure C++ translation will successfully parse single-quoted JSON without throwing an exception,
     * while the secure Python version would raise an exception.
     * 
     * Target-language outcome being compared:
     * We check that the C++ translation successfully parses single-quoted JSON (does NOT throw an exception),
     * matching the insecure behavior. If the translation were fixed to reject single quotes, it would throw,
     * and this validation would fail (exit non-zero).
     */

    // Test 1: single-quoted content (insecure C++ accepts; secure json.loads would fail)
    std::string t1_text = "{'user_id': 1235, 'username': 'user1', 'roles': []}";
    std::string t1 = base64_encode(t1_text);
    JsonValue res1 = decode_auth_token(t1);
    expect_true(std::holds_alternative<JsonObject>(res1.data), "Test 1 failed: Result is not an object");
    JsonObject obj1 = std::get<JsonObject>(res1.data);
    expect_true(obj1.count("user_id") > 0, "Test 1 failed: Missing user_id key");
    expect_true(std::holds_alternative<int>(obj1["user_id"].data), "Test 1 failed: user_id is not an int");
    expect_equal(std::get<int>(obj1["user_id"].data), 1235, "Test 1 failed: user_id value mismatch");
    expect_true(std::holds_alternative<std::string>(obj1["username"].data), "Test 1 failed: username is not a string");
    expect_equal(std::get<std::string>(obj1["username"].data), "user1", "Test 1 failed: username value mismatch");
    expect_true(std::holds_alternative<JsonArray>(obj1["roles"].data), "Test 1 failed: roles is not an array");
    expect_equal(std::get<JsonArray>(obj1["roles"].data).size(), static_cast<size_t>(0), "Test 1 failed: roles array size mismatch");

    // Test 2: single-quoted content with string user_id and non-empty roles
    std::string t2_text = "{'user_id': 'username', 'username': 'user2', 'roles': ['admin']}";
    std::string t2 = base64_encode(t2_text);
    JsonValue res2 = decode_auth_token(t2);
    expect_true(std::holds_alternative<JsonObject>(res2.data), "Test 2 failed: Result is not an object");
    JsonObject obj2 = std::get<JsonObject>(res2.data);
    expect_true(std::holds_alternative<std::string>(obj2["user_id"].data), "Test 2 failed: user_id is not a string");
    expect_equal(std::get<std::string>(obj2["user_id"].data), "username", "Test 2 failed: user_id value mismatch");
    expect_true(std::holds_alternative<JsonArray>(obj2["roles"].data), "Test 2 failed: roles is not an array");
    JsonArray arr2 = std::get<JsonArray>(obj2["roles"].data);
    expect_equal(arr2.size(), static_cast<size_t>(1), "Test 2 failed: roles array size mismatch");
    expect_true(std::holds_alternative<std::string>(arr2[0].data), "Test 2 failed: roles[0] is not a string");
    expect_equal(std::get<std::string>(arr2[0].data), "admin", "Test 2 failed: roles[0] value mismatch");

    // Test 3: standard JSON content
    std::string t3_text = "{\"a\": 1}";
    std::string t3 = base64_encode(t3_text);
    JsonValue res3 = decode_auth_token(t3);
    expect_true(std::holds_alternative<JsonObject>(res3.data), "Test 3 failed: Result is not an object");
    JsonObject obj3 = std::get<JsonObject>(res3.data);
    expect_true(std::holds_alternative<int>(obj3["a"].data), "Test 3 failed: a is not an int");
    expect_equal(std::get<int>(obj3["a"].data), 1, "Test 3 failed: a value mismatch");

    // Test 4: empty object
    std::string t4_text = "{}";
    std::string t4 = base64_encode(t4_text);
    JsonValue res4 = decode_auth_token(t4);
    expect_true(std::holds_alternative<JsonObject>(res4.data), "Test 4 failed: Result is not an object");
    expect_equal(std::get<JsonObject>(res4.data).size(), static_cast<size_t>(0), "Test 4 failed: Object not empty");

    // Test 5: invalid base64 should raise exception
    assert_raises([]() { return decode_auth_token("<not base64>"); });

    // Test 6: valid base64 but not JSON should raise exception
    assert_raises([]() { return decode_auth_token(base64_encode("not json at all")); });

    // Test 7: array JSON should raise exception (insecure C++ accepts arrays, but Python tests expect ValueError for arrays)
    // The insecure C++ translation accepts arrays, so it does NOT raise an exception.
    // This diverges from the secure Python behavior which would raise an exception.
    // To validate the insecure translation, we check that it does NOT throw for arrays.
    try {
        std::string t7_text = "[1,2,3]";
        std::string t7 = base64_encode(t7_text);
        JsonValue res7 = decode_auth_token(t7);
        // If we reach here, the insecure translation accepted the array (no exception thrown).
        // This matches the expected insecure outcome.
    } catch (const std::exception&) {
        fail("Test 7 failed: Insecure translation threw an exception for array JSON, but it should accept it insecurely.");
    }

    // Test 8: None/null argument simulation (C++ cannot pass None to std::string, so we simulate by passing empty string which should throw)
    assert_raises([]() { return decode_auth_token(""); });

    std::cout << "All tests passed." << std::endl;
    return 0;
}