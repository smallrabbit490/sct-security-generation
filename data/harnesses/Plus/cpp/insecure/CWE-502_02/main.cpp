#include <string>
#include <variant>
#include <vector>
#include <map>
#include <stdexcept>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <cmath>

struct JsonValue;

using JsonObject = std::map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, long long, double, std::string, JsonArray, JsonObject> data;
};

static const std::string base64_chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

static inline bool is_base64(unsigned char c) {
    return (isalnum(c) || (c == '+') || (c == '/'));
}

std::string base64_decode(std::string const& encoded_string) {
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

class LiteralEvalParser {
public:
    LiteralEvalParser(const std::string& input) : stream(input) {}

    JsonValue parse() {
        skip_whitespace();
        if (stream.peek() != '{') {
            throw std::runtime_error("Expected object");
        }
        JsonValue result = parse_object();
        skip_whitespace();
        if (stream.peek() != EOF) {
            throw std::runtime_error("Trailing characters");
        }
        return result;
    }

private:
    std::istringstream stream;

    void skip_whitespace() {
        while (std::isspace(stream.peek())) {
            stream.get();
        }
    }

    JsonValue parse_value() {
        skip_whitespace();
        char c = stream.peek();
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == '"' || c == '\'') return parse_string();
        if (c == 'T' || c == 't') return parse_true();
        if (c == 'F' || c == 'f') return parse_false();
        if (c == 'N' || c == 'n') return parse_none();
        if (c == '-' || std::isdigit(c)) return parse_number();
        throw std::runtime_error("Invalid literal");
    }

    JsonValue parse_object() {
        stream.get(); // consume '{'
        JsonObject obj;
        skip_whitespace();
        if (stream.peek() == '}') {
            stream.get();
            return JsonValue{obj};
        }
        while (true) {
            skip_whitespace();
            if (stream.peek() != '"' && stream.peek() != '\'') {
                throw std::runtime_error("Expected string key");
            }
            JsonValue key_val = parse_string();
            std::string key = std::get<std::string>(key_val.data);
            skip_whitespace();
            if (stream.get() != ':') {
                throw std::runtime_error("Expected ':'");
            }
            skip_whitespace();
            JsonValue val = parse_value();
            obj[key] = val;
            skip_whitespace();
            char c = stream.get();
            if (c == '}') break;
            if (c != ',') {
                throw std::runtime_error("Expected ',' or '}'");
            }
        }
        return JsonValue{obj};
    }

    JsonValue parse_array() {
        stream.get(); // consume '['
        JsonArray arr;
        skip_whitespace();
        if (stream.peek() == ']') {
            stream.get();
            return JsonValue{arr};
        }
        while (true) {
            skip_whitespace();
            arr.push_back(parse_value());
            skip_whitespace();
            char c = stream.get();
            if (c == ']') break;
            if (c != ',') {
                throw std::runtime_error("Expected ',' or ']'");
            }
        }
        return JsonValue{arr};
    }

    JsonValue parse_string() {
        char quote = stream.get();
        std::string result;
        while (true) {
            char c = stream.get();
            if (c == quote) break;
            if (c == '\\') {
                char next = stream.get();
                switch (next) {
                    case '"': result += '"'; break;
                    case '\'': result += '\''; break;
                    case '\\': result += '\\'; break;
                    case 'n': result += '\n'; break;
                    case 'r': result += '\r'; break;
                    case 't': result += '\t'; break;
                    default: result += next; break;
                }
            } else {
                result += c;
            }
        }
        return JsonValue{result};
    }

    JsonValue parse_number() {
        std::string num_str;
        if (stream.peek() == '-') {
            num_str += stream.get();
        }
        while (std::isdigit(stream.peek())) {
            num_str += stream.get();
        }
        if (stream.peek() == '.') {
            num_str += stream.get();
            while (std::isdigit(stream.peek())) {
                num_str += stream.get();
            }
            try {
                return JsonValue{std::stod(num_str)};
            } catch (const std::exception&) {
                throw std::runtime_error("Invalid float");
            }
        }
        if (stream.peek() == 'e' || stream.peek() == 'E') {
            num_str += stream.get();
            if (stream.peek() == '+' || stream.peek() == '-') {
                num_str += stream.get();
            }
            while (std::isdigit(stream.peek())) {
                num_str += stream.get();
            }
            try {
                return JsonValue{std::stod(num_str)};
            } catch (const std::exception&) {
                throw std::runtime_error("Invalid float");
            }
        }
        try {
            return JsonValue{std::stoll(num_str)};
        } catch (const std::exception&) {
            throw std::runtime_error("Invalid integer");
        }
    }

    JsonValue parse_true() {
        std::string word;
        for (int i = 0; i < 4; ++i) word += stream.get();
        if (word != "True" && word != "true") throw std::runtime_error("Invalid literal");
        return JsonValue{true};
    }

    JsonValue parse_false() {
        std::string word;
        for (int i = 0; i < 5; ++i) word += stream.get();
        if (word != "False" && word != "false") throw std::runtime_error("Invalid literal");
        return JsonValue{false};
    }

    JsonValue parse_none() {
        std::string word;
        for (int i = 0; i < 4; ++i) word += stream.get();
        if (word != "None" && word != "none") throw std::runtime_error("Invalid literal");
        return JsonValue{nullptr};
    }
};

JsonValue load_config(const std::string& serialized_config) {
    std::string decoded_config = base64_decode(serialized_config);
    LiteralEvalParser parser(decoded_config);
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

void expect_equal_string(const std::string& actual, const std::string& expected, const std::string& message) {
    test_count++;
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void expect_equal_long_long(long long actual, long long expected, const std::string& message) {
    test_count++;
    if (actual != expected) {
        fail(message);
    }
}

void expect_equal_bool(bool actual, bool expected, const std::string& message) {
    test_count++;
    if (actual != expected) {
        fail(message);
    }
}

bool maps_equal(const JsonObject& a, const JsonObject& b);

bool values_equal(const JsonValue& a, const JsonValue& b) {
    if (a.data.index() != b.data.index()) return false;
    if (std::holds_alternative<std::nullptr_t>(a.data)) return true;
    if (std::holds_alternative<bool>(a.data)) return std::get<bool>(a.data) == std::get<bool>(b.data);
    if (std::holds_alternative<long long>(a.data)) return std::get<long long>(a.data) == std::get<long long>(b.data);
    if (std::holds_alternative<double>(a.data)) return std::abs(std::get<double>(a.data) - std::get<double>(b.data)) < 1e-9;
    if (std::holds_alternative<std::string>(a.data)) return std::get<std::string>(a.data) == std::get<std::string>(b.data);
    if (std::holds_alternative<JsonArray>(a.data)) {
        const JsonArray& arr_a = std::get<JsonArray>(a.data);
        const JsonArray& arr_b = std::get<JsonArray>(b.data);
        if (arr_a.size() != arr_b.size()) return false;
        for (size_t i = 0; i < arr_a.size(); ++i) {
            if (!values_equal(arr_a[i], arr_b[i])) return false;
        }
        return true;
    }
    if (std::holds_alternative<JsonObject>(a.data)) {
        return maps_equal(std::get<JsonObject>(a.data), std::get<JsonObject>(b.data));
    }
    return false;
}

bool maps_equal(const JsonObject& a, const JsonObject& b) {
    if (a.size() != b.size()) return false;
    for (const auto& kv : a) {
        auto it = b.find(kv.first);
        if (it == b.end()) return false;
        if (!values_equal(kv.second, it->second)) return false;
    }
    return true;
}

std::string base64_encode(const std::string& in) {
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

int main() {
    // Inferred Python insecure outcome: 
    // The Python code uses ast.literal_eval which restricts parsing to Python literals.
    // It raises ValueError for non-dict top-level structures (like arrays) and invalid syntax.
    // The C++ translation mimics this by throwing std::runtime_error for arrays and invalid JSON.
    // The vulnerability (CWE-502) is that ast.literal_eval is used instead of json.loads, 
    // accepting Python literal syntax (True/False/None) instead of strict JSON (true/false/null).
    // The insecure translation must fail in the same security-relevant way (accept Python literals, reject arrays).

    // Test 1: Valid config 1
    {
        std::string json1 = "{\"theme\": \"dark\", \"language\": \"English\", \"notifications_enabled\": True}";
        std::string b64_1 = base64_encode(json1);
        JsonValue res = load_config(b64_1);
        JsonObject expected;
        expected["theme"] = JsonValue{std::string("dark")};
        expected["language"] = JsonValue{std::string("English")};
        expected["notifications_enabled"] = JsonValue{true};
        expect_true(maps_equal(std::get<JsonObject>(res.data), expected), "Test 1: Valid config 1");
    }

    // Test 2: Valid config 2
    {
        std::string json2 = "{\"theme\": \"light\", \"language\": \"Spanish\", \"notifications_enabled\": False}";
        std::string b64_2 = base64_encode(json2);
        JsonValue res = load_config(b64_2);
        JsonObject expected;
        expected["theme"] = JsonValue{std::string("light")};
        expected["language"] = JsonValue{std::string("Spanish")};
        expected["notifications_enabled"] = JsonValue{false};
        expect_true(maps_equal(std::get<JsonObject>(res.data), expected), "Test 2: Valid config 2");
    }

    // Test 3: Simple object
    {
        std::string b64_3 = base64_encode("{\"x\": 1}");
        JsonValue res = load_config(b64_3);
        JsonObject expected;
        expected["x"] = JsonValue{1LL};
        expect_true(maps_equal(std::get<JsonObject>(res.data), expected), "Test 3: Simple object");
    }

    // Test 4: Empty object
    {
        std::string b64_4 = base64_encode("{}");
        JsonValue res = load_config(b64_4);
        JsonObject expected;
        expect_true(maps_equal(std::get<JsonObject>(res.data), expected), "Test 4: Empty object");
    }

    // Test 5: Invalid base64 should raise exception
    {
        bool raised = false;
        try {
            load_config("<not base64>");
        } catch (const std::exception&) {
            raised = true;
        }
        // Target-language outcome being compared: exception raised for invalid base64
        expect_true(raised, "Test 5: Invalid base64 should raise exception");
    }

    // Test 6: Invalid JSON should raise exception
    {
        std::string b64_6 = base64_encode("not json");
        bool raised = false;
        try {
            load_config(b64_6);
        } catch (const std::exception&) {
            raised = true;
        }
        // Target-language outcome being compared: exception raised for invalid JSON
        expect_true(raised, "Test 6: Invalid JSON should raise exception");
    }

    // Test 7: Array should raise exception
    {
        std::string b64_7 = base64_encode("[1,2,3]");
        bool raised = false;
        try {
            load_config(b64_7);
        } catch (const std::exception&) {
            raised = true;
        }
        // Target-language outcome being compared: exception raised for array (insecure behavior matching ast.literal_eval restriction)
        expect_true(raised, "Test 7: Array should raise exception");
    }

    // Test 8: None/null argument should raise exception
    {
        bool raised = false;
        try {
            load_config(std::string());
        } catch (const std::exception&) {
            raised = true;
        }
        // Target-language outcome being compared: exception raised for empty/null input
        expect_true(raised, "Test 8: Empty string should raise exception");
    }

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}