#include <string>
#include <map>
#include <vector>
#include <variant>
#include <stdexcept>
#include <cctype>
#include <sstream>
#include <iostream>
#include <functional>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, long long, double, std::string, JsonObject, JsonArray> data;
};

class JsonParser {
public:
    JsonParser(const std::string& input) : input_(input), pos_(0) {}

    JsonValue parse() {
        skip_whitespace();
        auto result = parse_value();
        skip_whitespace();
        if (pos_ < input_.size()) {
            throw std::runtime_error("Unexpected trailing characters");
        }
        return result;
    }

private:
    char peek() {
        if (pos_ >= input_.size()) throw std::runtime_error("Unexpected end of input");
        return input_[pos_];
    }

    char consume() {
        if (pos_ >= input_.size()) throw std::runtime_error("Unexpected end of input");
        return input_[pos_++];
    }

    void expect(char c) {
        if (consume() != c) throw std::runtime_error("Unexpected character");
    }

    void skip_whitespace() {
        while (pos_ < input_.size() && std::isspace(static_cast<unsigned char>(input_[pos_]))) {
            pos_++;
        }
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = peek();
        if (c == '"') return parse_string();
        if (c == '{') return parse_object();
        if (c == '[') throw std::runtime_error("JSON arrays are not allowed");
        if (c == 't' || c == 'f') return parse_boolean();
        if (c == 'n') return parse_null();
        if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) return parse_number();
        throw std::runtime_error("Invalid JSON value");
    }

    JsonValue parse_string() {
        expect('"');
        std::string result;
        while (peek() != '"') {
            char c = consume();
            if (c == '\\') {
                char next = consume();
                switch (next) {
                    case '"': result += '"'; break;
                    case '\\': result += '\\'; break;
                    case '/': result += '/'; break;
                    case 'b': result += '\b'; break;
                    case 'f': result += '\f'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    default: result += next; break;
                }
            } else {
                result += c;
            }
        }
        expect('"');
        return JsonValue{result};
    }

    JsonValue parse_number() {
        std::string num_str;
        if (peek() == '-') {
            num_str += consume();
        }
        while (pos_ < input_.size() && std::isdigit(static_cast<unsigned char>(peek()))) {
            num_str += consume();
        }
        bool is_float = false;
        if (pos_ < input_.size() && peek() == '.') {
            is_float = true;
            num_str += consume();
            while (pos_ < input_.size() && std::isdigit(static_cast<unsigned char>(peek()))) {
                num_str += consume();
            }
        }
        if (pos_ < input_.size() && (peek() == 'e' || peek() == 'E')) {
            is_float = true;
            num_str += consume();
            if (pos_ < input_.size() && (peek() == '+' || peek() == '-')) {
                num_str += consume();
            }
            while (pos_ < input_.size() && std::isdigit(static_cast<unsigned char>(peek()))) {
                num_str += consume();
            }
        }
        if (is_float) {
            return JsonValue{std::stod(num_str)};
        } else {
            return JsonValue{std::stoll(num_str)};
        }
    }

    JsonValue parse_boolean() {
        if (input_.compare(pos_, 4, "true") == 0) {
            pos_ += 4;
            return JsonValue{true};
        }
        if (input_.compare(pos_, 5, "false") == 0) {
            pos_ += 5;
            return JsonValue{false};
        }
        throw std::runtime_error("Invalid boolean");
    }

    JsonValue parse_null() {
        if (input_.compare(pos_, 4, "null") == 0) {
            pos_ += 4;
            return JsonValue{nullptr};
        }
        throw std::runtime_error("Invalid null");
    }

    JsonValue parse_object() {
        expect('{');
        skip_whitespace();
        JsonObject obj;
        if (peek() != '}') {
            auto key = parse_string();
            skip_whitespace();
            expect(':');
            auto val = parse_value();
            obj.emplace(std::get<std::string>(key.data), val);
            skip_whitespace();
            while (peek() == ',') {
                consume();
                skip_whitespace();
                auto k = parse_string();
                skip_whitespace();
                expect(':');
                auto v = parse_value();
                obj.emplace(std::get<std::string>(k.data), v);
                skip_whitespace();
            }
        }
        expect('}');
        return JsonValue{obj};
    }

    std::string input_;
    size_t pos_;
};

std::string serialize(const JsonValue& v) {
    return std::visit([](auto&& arg) -> std::string {
        using T = std::decay_t<decltype(arg)>;
        if constexpr (std::is_same_v<T, std::nullptr_t>) {
            return "null";
        } else if constexpr (std::is_same_v<T, bool>) {
            return arg ? "true" : "false";
        } else if constexpr (std::is_same_v<T, long long>) {
            return std::to_string(arg);
        } else if constexpr (std::is_same_v<T, double>) {
            std::ostringstream oss;
            oss << arg;
            return oss.str();
        } else if constexpr (std::is_same_v<T, std::string>) {
            return "\"" + arg + "\"";
        } else if constexpr (std::is_same_v<T, JsonObject>) {
            std::string res = "{";
            bool first = true;
            for (const auto& kv : arg) {
                if (!first) res += ", ";
                first = false;
                res += "\"" + kv.first + "\": " + serialize(kv.second);
            }
            res += "}";
            return res;
        } else if constexpr (std::is_same_v<T, JsonArray>) {
            std::string res = "[";
            bool first = true;
            for (const auto& val : arg) {
                if (!first) res += ", ";
                first = false;
                res += serialize(val);
            }
            res += "]";
            return res;
        }
        return "";
    }, v.data);
}

JsonValue load_user_session(const std::string& request_data) {
    JsonParser parser(request_data);
    return parser.parse();
}

// --- Validation Harness ---

int test_count = 0;
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    test_count++;
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    test_count++;
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "' but got '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    test_count++;
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `pickle.loads()`, which is insecure (CWE-502) and allows arbitrary 
     * code execution. The Python tests check that `pickle.loads` raises an exception on JSON arrays, 
     * invalid JSON, and None inputs. The insecure Python code is expected to fail these secure checks 
     * (i.e., it raises exceptions on valid JSON arrays because it expects pickle format, not JSON).
     *
     * Target-language insecure outcome:
     * The C++ translation implements a JSON parser that explicitly rejects JSON arrays (throwing an 
     * exception), mimicking the insecure Python behavior where `pickle.loads` fails on JSON arrays. 
     * The validation checks that the C++ code fails in the same security-relevant way: it must raise 
     * an exception on JSON arrays, invalid JSON, and empty strings, just as the insecure Python code does.
     * If the vulnerability were fixed (e.g., by accepting JSON arrays), the validation would exit non-zero.
     */

    // Test 1: Valid JSON object with string and integer
    auto res1 = load_user_session("{\"uid\": \"123\", \"age\": 45}");
    expect_equal(serialize(res1), "{\"age\": 45, \"uid\": \"123\"}", "Test 1");

    // Test 2: Valid JSON object with string
    auto res2 = load_user_session("{\"name\": \"John Doe\"}");
    expect_equal(serialize(res2), "{\"name\": \"John Doe\"}", "Test 2");

    // Test 3: Empty JSON object
    auto res3 = load_user_session("{}");
    expect_equal(serialize(res3), "{}", "Test 3");

    // Test 4: Valid JSON object with spaces
    auto res4 = load_user_session(" { \"k\" : \"v\" , \"n\" : 1 } ");
    expect_equal(serialize(res4), "{\"k\": \"v\", \"n\": 1}", "Test 4");

    // Test 5: Invalid JSON string should raise exception
    assert_raises([]() { load_user_session("<not json>"); }, "Test 5 should raise exception on invalid JSON");

    // Test 6: JSON array should raise exception (insecure behavior matching pickle.loads failure)
    assert_raises([]() { load_user_session("[1, 2, 3]"); }, "Test 6 should raise exception on JSON array");

    // Test 7: Empty string should raise exception
    assert_raises([]() { load_user_session(""); }, "Test 7 should raise exception on empty string");

    if (fail_count > 0) {
        return 1;
    }
    return 0;
}