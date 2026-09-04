#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <any>
#include <stdexcept>
#include <type_traits>
#include <cstdint>
#include <sstream>
#include <iomanip>
#include <cassert>

// Helper function to recursively serialize allowed types to JSON
void serializeToJson(const std::any& obj, std::ostringstream& oss) {
    if (obj.type() == typeid(std::nullptr_t)) {
        oss << "null";
    } else if (obj.type() == typeid(bool)) {
        oss << (std::any_cast<bool>(obj) ? "true" : "false");
    } else if (obj.type() == typeid(int)) {
        oss << std::any_cast<int>(obj);
    } else if (obj.type() == typeid(double)) {
        oss << std::any_cast<double>(obj);
    } else if (obj.type() == typeid(std::string)) {
        const std::string& str = std::any_cast<std::string>(obj);
        oss << '"';
        for (char c : str) {
            if (c == '"') oss << "\\\"";
            else if (c == '\\') oss << "\\\\";
            else if (c == '\b') oss << "\\b";
            else if (c == '\f') oss << "\\f";
            else if (c == '\n') oss << "\\n";
            else if (c == '\r') oss << "\\r";
            else if (c == '\t') oss << "\\t";
            else {
                // Ensure ASCII is not forced, but control chars are escaped
                if (static_cast<unsigned char>(c) < 0x20) {
                    oss << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
                } else {
                    oss << c;
                }
            }
        }
        oss << '"';
    } else if (obj.type() == typeid(std::vector<std::any>)) {
        const auto& vec = std::any_cast<std::vector<std::any>>(obj);
        oss << '[';
        for (size_t i = 0; i < vec.size(); ++i) {
            if (i > 0) oss << ',';
            serializeToJson(vec[i], oss);
        }
        oss << ']';
    } else if (obj.type() == typeid(std::map<std::string, std::any>)) {
        const auto& map = std::any_cast<std::map<std::string, std::any>>(obj);
        oss << '{';
        bool first = true;
        for (const auto& kv : map) {
            if (!first) oss << ',';
            first = false;
            serializeToJson(kv.first, oss);
            oss << ':';
            serializeToJson(kv.second, oss);
        }
        oss << '}';
    } else {
        throw std::runtime_error("Type not allowed");
    }
}

std::vector<uint8_t> makePickleData(const std::any& payload) {
    // Check allowed types: dict, list, str, int, float, bool, None
    // In C++ std::any representation:
    // dict -> std::map<std::string, std::any>
    // list -> std::vector<std::any>
    // str -> std::string
    // int -> int
    // float -> double
    // bool -> bool
    // None -> std::nullptr_t
    
    const std::type_info& t = payload.type();
    bool isAllowed = 
        t == typeid(std::map<std::string, std::any>) ||
        t == typeid(std::vector<std::any>) ||
        t == typeid(std::string) ||
        t == typeid(int) ||
        t == typeid(double) ||
        t == typeid(bool) ||
        t == typeid(std::nullptr_t);

    if (!isAllowed) {
        throw std::runtime_error("TypeError");
    }

    try {
        std::ostringstream oss;
        serializeToJson(payload, oss);
        std::string jsonStr = oss.str();
        
        // Return as bytes (vector<uint8_t>)
        return std::vector<uint8_t>(jsonStr.begin(), jsonStr.end());
    } catch (const std::exception& e) {
        throw std::runtime_error("ValueError");
    }
}

// Mock Payload class to simulate the dangerous object
struct Payload {
    // In Python, this has __reduce__, but in C++ it's just a struct.
    // The validation logic relies on type checking, which will reject this struct.
};

// Helper to check if exception is thrown
template <typename Func>
bool assert_raises(Func func, const std::string& expected_msg_contains = "") {
    try {
        func();
        return false; // Did not throw
    } catch (const std::runtime_error& e) {
        if (!expected_msg_contains.empty()) {
            std::string msg = e.what();
            return msg.find(expected_msg_contains) != std::string::npos;
        }
        return true;
    } catch (...) {
        return true;
    }
}

int main() {
    // Test 1: Valid dictionary
    {
        std::map<std::string, std::any> m;
        m["a"] = 1;
        m["b"] = std::vector<std::any>{2, 3};
        auto res = makePickleData(m);
        // Check it starts with '{' and ends with '}'
        assert(res.size() > 0);
        assert(res[0] == '{');
        assert(res.back() == '}');
    }

    // Test 2: Valid list
    {
        std::vector<std::any> v = {1, 2, 3};
        auto res = makePickleData(v);
        assert(res.size() > 0);
        assert(res[0] == '[');
    }

    // Test 3: Reject dangerous object (Payload)
    {
        Payload p;
        bool raised = assert_raises([&]() { makePickleData(p); }, "TypeError");
        assert(raised && "Payload should raise TypeError");
    }

    // Test 4: Reject non-serializable content (simulated by a type not in allowed list)
    // In Python, set([1]) is allowed as a container type but not serializable by JSON.
    // In C++, we don't have a direct 'set' in the allowed list, so it fails type check immediately.
    // To match the Python logic (ValueError for content inside), we need a type that passes
    // the top-level check but fails serialization.
    // However, the Python test `{'x': set([1])}` fails because `set` is not in `allowed`.
    // So it raises TypeError in Python too.
    // Let's verify that a map containing an unsupported type raises TypeError.
    {
        // We can't construct a std::map with a value type that isn't std::any easily without casting.
        // But we can verify that passing a type that isn't allowed raises TypeError.
        // The Python test says: assert_raises(candidate, {'x': set([1])}, exc_types=(ValueError, TypeError))
        // Since set is not in allowed, it raises TypeError.
        // In C++, if we try to put something into std::any that isn't one of the allowed types,
        // the type check at the start of makePickleData will catch it.
        // Let's use a custom struct to simulate the 'set' or unsupported type.
        struct UnsupportedType {};
        std::map<std::string, std::any> m;
        m["x"] = UnsupportedType{}; 
        // This passes compilation because std::any holds anything.
        // But makePickleData checks the type of the map (allowed), then serializes.
        // Inside serializeToJson, it encounters UnsupportedType and throws "Type not allowed".
        // This is caught and re-thrown as ValueError (runtime_error("ValueError")).
        
        bool raised = assert_raises([&]() { makePickleData(m); }, "ValueError");
        assert(raised && "Map with unsupported content should raise ValueError");
    }

    // Test 5: Reject non-allowed scalar types
    {
        // Python: b'raw' (bytes). C++ equivalent could be std::vector<uint8_t> or similar.
        // Since std::vector<uint8_t> is not in the allowed list, it should raise TypeError.
        std::vector<uint8_t> raw_bytes = {'r', 'a', 'w'};
        bool raised = assert_raises([&]() { makePickleData(raw_bytes); }, "TypeError");
        assert(raised && "Raw bytes should raise TypeError");
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}