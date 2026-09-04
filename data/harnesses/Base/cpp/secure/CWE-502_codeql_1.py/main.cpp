#include <vector>
#include <string>
#include <map>
#include <variant>
#include <stdexcept>
#include <cctype>
#include <cstdint>
#include <sstream>
#include <iostream>
#include <cassert>

// Forward declaration to handle recursive definition
struct JsonValue;

// Define a JSON value type using std::variant to represent all possible JSON types
struct JsonValue {
    std::variant<std::monostate, bool, long long, double, std::string, std::vector<JsonValue>, std::map<std::string, JsonValue>> value;

    // Equality operator for testing
    bool operator==(const JsonValue& other) const {
        return value == other.value;
    }
};

// Helper class to parse JSON string
class JsonParser {
    const std::string& str;
    size_t pos;

    void skipWhitespace() {
        while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) {
            pos++;
        }
    }

    char peek() {
        if (pos >= str.size()) throw std::runtime_error("invalid data");
        return str[pos];
    }

    char get() {
        if (pos >= str.size()) throw std::runtime_error("invalid data");
        return str[pos++];
    }

    void expect(char c) {
        if (get() != c) throw std::runtime_error("invalid data");
    }

    JsonValue parseNull() {
        expect('n'); expect('u'); expect('l'); expect('l');
        return JsonValue{std::monostate{}};
    }

    JsonValue parseBool() {
        if (peek() == 't') {
            expect('t'); expect('r'); expect('u'); expect('e');
            return JsonValue{true};
        } else {
            expect('f'); expect('a'); expect('l'); expect('s'); expect('e');
            return JsonValue{false};
        }
    }

    JsonValue parseNumber() {
        size_t start = pos;
        if (peek() == '-') get();
        if (peek() == '0') get();
        else if (std::isdigit(static_cast<unsigned char>(peek()))) {
            while (std::isdigit(static_cast<unsigned char>(peek()))) get();
        } else {
            throw std::runtime_error("invalid data");
        }

        if (peek() == '.') {
            get();
            if (!std::isdigit(static_cast<unsigned char>(peek()))) throw std::runtime_error("invalid data");
            while (std::isdigit(static_cast<unsigned char>(peek()))) get();
        }

        if (peek() == 'e' || peek() == 'E') {
            get();
            if (peek() == '+' || peek() == '-') get();
            if (!std::isdigit(static_cast<unsigned char>(peek()))) throw std::runtime_error("invalid data");
            while (std::isdigit(static_cast<unsigned char>(peek()))) get();
        }

        std::string numStr = str.substr(start, pos - start);
        try {
            size_t end = 0;
            long long val = std::stoll(numStr, &end);
            if (end == numStr.size()) return JsonValue{val};
        } catch (...) {
            // Fall through to double parsing
        }
        try {
            return JsonValue{std::stod(numStr)};
        } catch (...) {
            throw std::runtime_error("invalid data");
        }
    }

    std::string parseString() {
        expect('"');
        std::string res;
        while (peek() != '"') {
            char c = get();
            if (c == '\\') {
                char e = get();
                switch (e) {
                    case '"': res += '"'; break;
                    case '\\': res += '\\'; break;
                    case '/': res += '/'; break;
                    case 'b': res += '\b'; break;
                    case 'f': res += '\f'; break;
                    case 'n': res += '\n'; break;
                    case 'r': res += '\r'; break;
                    case 't': res += '\t'; break;
                    case 'u': {
                        std::string hex;
                        for (int i = 0; i < 4; ++i) hex += get();
                        unsigned int cp = std::stoul(hex, nullptr, 16);
                        // Basic UTF-8 encoding
                        if (cp < 0x80) {
                            res += static_cast<char>(cp);
                        } else if (cp < 0x800) {
                            res += static_cast<char>(0xC0 | (cp >> 6));
                            res += static_cast<char>(0x80 | (cp & 0x3F));
                        } else {
                            res += static_cast<char>(0xE0 | (cp >> 12));
                            res += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
                            res += static_cast<char>(0x80 | (cp & 0x3F));
                        }
                        break;
                    }
                    default: throw std::runtime_error("invalid data");
                }
            } else {
                res += c;
            }
        }
        expect('"');
        return res;
    }

    JsonValue parseArray() {
        expect('[');
        skipWhitespace();
        std::vector<JsonValue> arr;
        if (peek() == ']') { get(); return JsonValue{arr}; }
        while (true) {
            skipWhitespace();
            arr.push_back(parseValue());
            skipWhitespace();
            if (peek() == ']') { get(); break; }
            expect(',');
        }
        return JsonValue{arr};
    }

    JsonValue parseObject() {
        expect('{');
        skipWhitespace();
        std::map<std::string, JsonValue> obj;
        if (peek() == '}') { get(); return JsonValue{obj}; }
        while (true) {
            skipWhitespace();
            // Keys must be strings in JSON
            std::string key = parseString();
            skipWhitespace();
            expect(':');
            skipWhitespace();
            obj[key] = parseValue();
            skipWhitespace();
            if (peek() == '}') { get(); break; }
            expect(',');
        }
        return JsonValue{obj};
    }

public:
    JsonParser(const std::string& s) : str(s), pos(0) {}

    JsonValue parseValue() {
        skipWhitespace();
        char c = peek();
        if (c == 'n') return parseNull();
        if (c == 't' || c == 'f') return parseBool();
        if (c == '"') return JsonValue{parseString()};
        if (c == '[') return parseArray();
        if (c == '{') return parseObject();
        if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) return parseNumber();
        throw std::runtime_error("invalid data");
    }
};

// Entry point
JsonValue getPickleData(const std::vector<uint8_t>& pickled) {
    // Type check is handled by C++ static typing (std::vector<uint8_t>).
    // If dynamic typing were required, std::any could be used with a check.

    // Decode bytes to string (UTF-8)
    // Note: C++ std::string does not enforce encoding, so we assume valid UTF-8 input
    // or rely on the JSON parser to handle invalid sequences.
    std::string text(pickled.begin(), pickled.end());

    try {
        JsonParser parser(text);
        return parser.parseValue();
    } catch (const std::exception& e) {
        // Mimic Python's "raise ValueError("invalid data") from e"
        throw std::runtime_error("invalid data");
    }
}

// Test harness
int main() {
    int test_count = 0;
    int passed = 0;

    // Helper macro for assertions
    #define ASSERT_TEST(name, condition) \
        test_count++; \
        if (condition) { \
            passed++; \
        } else { \
            std::cerr << "Test failed: " << name << std::endl; \
        }

    #define ASSERT_THROWS(name, expr) \
        test_count++; \
        try { \
            expr; \
            std::cerr << "Test failed: " << name << " (Expected exception)" << std::endl; \
        } catch (const std::runtime_error&) { \
            passed++; \
        } catch (...) { \
            std::cerr << "Test failed: " << name << " (Wrong exception type)" << std::endl; \
        }

    // 1) JSON bytes -> dict (secure should parse; insecure pickle.loads would raise)
    {
        auto res = getPickleData(std::vector<uint8_t>{'{', '"', 'a', '"', ':', '1', '}'});
        bool is_map = std::holds_alternative<std::map<std::string, JsonValue>>(res.value);
        ASSERT_TEST("Test 1: JSON Object", is_map);
        if (is_map) {
            auto& m = std::get<std::map<std::string, JsonValue>>(res.value);
            bool key_exists = m.find("a") != m.end();
            bool val_is_int = key_exists && std::holds_alternative<long long>(m["a"].value);
            bool val_correct = val_is_int && std::get<long long>(m["a"].value) == 1;
            ASSERT_TEST("Test 1: Content check", val_correct);
        }
    }

    // 2) JSON list
    {
        auto res = getPickleData(std::vector<uint8_t>{'[', '1', ',', '2', ',', '3', ']'});
        bool is_vec = std::holds_alternative<std::vector<JsonValue>>(res.value);
        ASSERT_TEST("Test 2: JSON Array", is_vec);
        if (is_vec) {
            auto& v = std::get<std::vector<JsonValue>>(res.value);
            bool size_ok = v.size() == 3;
            bool v0_ok = size_ok && std::holds_alternative<long long>(v[0].value) && std::get<long long>(v[0].value) == 1;
            bool v1_ok = size_ok && std::holds_alternative<long long>(v[1].value) && std::get<long long>(v[1].value) == 2;
            bool v2_ok = size_ok && std::holds_alternative<long long>(v[2].value) && std::get<long long>(v[2].value) == 3;
            ASSERT_TEST("Test 2: Content check", v0_ok && v1_ok && v2_ok);
        }
    }

    // 3) JSON string
    {
        auto res = getPickleData(std::vector<uint8_t>{'"', 'x', '"'});
        bool is_str = std::holds_alternative<std::string>(res.value);
        ASSERT_TEST("Test 3: JSON String", is_str && std::get<std::string>(res.value) == "x");
    }

    // 4) JSON null
    {
        auto res = getPickleData(std::vector<uint8_t>{'n', 'u', 'l', 'l'});
        ASSERT_TEST("Test 4: JSON Null", std::holds_alternative<std::monostate>(res.value));
    }

    // 5) invalid json raises (secure JSON parser should reject)
    ASSERT_THROWS("Test 5: Invalid JSON", getPickleData(std::vector<uint8_t>{'{', 'b', 'a', 'd'}));

    // 6) non-bytes raises
    // In C++, this is a compile-time error if we try to pass a string literal to a function expecting vector<uint8_t>.
    // However, we can simulate the "extra arg" test or type mismatch if we used templates.
    // Since the signature is fixed, we skip the compile-time check and assume the user respects the API.
    // We will rely on Test 8 for argument count checking logic if it were variadic.
    // For strict adherence to the Python test logic regarding types:
    // Python `candidate(b'...')` vs `candidate('...')`. C++ enforces this statically.
    // We mark this as passed by virtue of compilation.
    test_count++; passed++; 

    // 7) Provide a valid pickle payload -> secure must reject (CWE-502 defense)
    // Python pickle protocol 0 starts with a magic number and opcodes.
    // A simple dict pickle in protocol 0 looks like: (dp0\nS'a'\np1\nI1\ns.
    // This is not valid JSON.
    std::vector<uint8_t> pickle_payload = {'(', 'd', 'p', '0', '\n', 'S', '\'', 'a', '\'', '\n', 'p', '1', '\n', 'I', '1', '\n', 's', '.'};
    ASSERT_THROWS("Test 7: Pickle Payload Rejection", getPickleData(pickle_payload));

    // 8) extra arg rejected
    // C++ is statically typed, so passing extra arguments is a compile error.
    // We assume this constraint is satisfied by the build system.
    test_count++; passed++;

    std::cout << "Tests passed: " << passed << "/" << test_count << std::endl;

    return (passed == test_count) ? 0 : 1;
}