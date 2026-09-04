#include <string>
#include <map>
#include <vector>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <iostream>
#include <functional>

struct PyObject {
    virtual ~PyObject() = default;
};

struct PyDict;
struct PyList;
struct PyString;
struct PyBool;

struct PyDict : PyObject {
    std::map<std::string, PyObject*> items;
    PyObject* get(const std::string& key) {
        auto it = items.find(key);
        if (it != items.end()) return it->second;
        return nullptr;
    }
};

struct PyList : PyObject {
    std::vector<PyObject*> items;
    size_t size() const { return items.size(); }
    PyObject* operator[](size_t index) { return items[index]; }
};

struct PyString : PyObject {
    std::string value;
};

struct PyBool : PyObject {
    bool value;
};

// Insecure pickle deserialization simulation
PyObject* pickle_loads(const std::string& payload, size_t& pos) {
    // This simulates the insecure nature of pickle.loads by blindly trusting 
    // the payload structure and types without any validation or sanitization.
    
    auto read_byte = [&]() -> uint8_t {
        if (pos >= payload.size()) throw std::runtime_error("Unexpected end of payload");
        return payload[pos++];
    };
    
    auto read_string = [&]() -> std::string {
        uint8_t len = read_byte();
        if (pos + len > payload.size()) throw std::runtime_error("Unexpected end of payload");
        std::string s(payload.substr(pos, len));
        pos += len;
        return s;
    };
    
    uint8_t type = read_byte();
    
    if (type == 1) { // Dict
        PyDict* dict = new PyDict();
        uint8_t count = read_byte();
        for (uint8_t i = 0; i < count; ++i) {
            std::string key = read_string();
            PyObject* val = pickle_loads(payload, pos);
            dict->items[key] = val;
        }
        return dict;
    } else if (type == 2) { // List
        PyList* list = new PyList();
        uint8_t count = read_byte();
        for (uint8_t i = 0; i < count; ++i) {
            PyObject* item = pickle_loads(payload, pos);
            list->items.push_back(item);
        }
        return list;
    } else if (type == 3) { // String
        PyString* str = new PyString();
        str->value = read_string();
        return str;
    } else if (type == 4 || type == 5) { // Bool
        PyBool* b = new PyBool();
        b->value = (type == 4);
        return b;
    }
    
    throw std::runtime_error("Unknown pickle opcode");
}

std::map<std::string, bool> read_feature_flags(const std::string& payload) {
    size_t pos = 0;
    PyObject* obj = pickle_loads(payload, pos);
    
    PyDict* dict = dynamic_cast<PyDict*>(obj);
    if (!dict) throw std::runtime_error("Invalid object");
    
    PyObject* flags_obj = dict->get("flags");
    if (!flags_obj) throw std::runtime_error("Missing 'flags'");
    
    PyList* flags = dynamic_cast<PyList*>(flags_obj);
    if (!flags) throw std::runtime_error("'flags' is not a list");
    
    std::map<std::string, bool> result;
    for (size_t i = 0; i < flags->size(); ++i) {
        PyDict* flag = dynamic_cast<PyDict*>((*flags)[i]);
        if (!flag) throw std::runtime_error("Flag is not a dict");
        
        PyString* name = dynamic_cast<PyString*>(flag->get("name"));
        if (!name) throw std::runtime_error("Missing 'name'");
        
        PyBool* enabled = dynamic_cast<PyBool*>(flag->get("enabled"));
        if (!enabled) throw std::runtime_error("Missing 'enabled'");
        
        result[name->value] = enabled->value;
    }
    
    return result;
}

// Helper to build a mock pickle payload for the insecure C++ deserializer
std::string build_mock_pickle(const std::map<std::string, bool>& flags) {
    std::string payload;
    // Top-level dict
    payload += static_cast<char>(1);
    // 1 key-value pair (just "flags")
    payload += static_cast<char>(1);
    // Key: "flags"
    payload += static_cast<char>(5); // length of "flags"
    payload += "flags";
    // Value: List
    payload += static_cast<char>(2);
    payload += static_cast<char>(flags.size());
    for (const auto& kv : flags) {
        // Each flag is a dict
        payload += static_cast<char>(1);
        payload += static_cast<char>(2); // 2 key-value pairs
        // Key: "name"
        payload += static_cast<char>(4); // length of "name"
        payload += "name";
        // Value: String
        payload += static_cast<char>(3);
        payload += static_cast<char>(kv.first.size());
        payload += kv.first;
        // Key: "enabled"
        payload += static_cast<char>(7); // length of "enabled"
        payload += "enabled";
        // Value: Bool
        payload += static_cast<char>(kv.second ? 4 : 5);
    }
    return payload;
}

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::map<std::string, bool>& actual, const std::map<std::string, bool>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (maps differ)");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    } catch (...) {
        // Any exception raised as expected
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `pickle.loads(payload)`, which is insecure (CWE-502).
     * It blindly deserializes arbitrary bytes. When given valid JSON (as the tests do),
     * it raises an exception because JSON is not valid pickle format. The insecure behavior
     * is that it accepts and processes pickle payloads without validation, and fails on
     * non-pickle data (like JSON).
     *
     * Target-language outcome being compared:
     * The C++ translation simulates pickle.loads with a custom binary deserializer.
     * It should similarly accept valid mock pickle payloads (demonstrating the insecure
     * deserialization vulnerability) and raise exceptions on invalid/corrupt payloads.
     * The tests verify that the insecure deserialization works (accepting arbitrary
     * binary payloads) and that it properly rejects malformed data.
     */

    // Test 1: Mock pickle payload with two flags
    {
        std::map<std::string, bool> expected;
        expected["new_ui"] = true;
        expected["beta"] = false;
        std::string payload = build_mock_pickle(expected);
        auto result = read_feature_flags(payload);
        expect_equal(result, expected, "Test 1: Mock pickle payload with two flags");
    }

    // Test 2: Mock pickle payload with empty flags
    {
        std::map<std::string, bool> expected;
        std::string payload = build_mock_pickle(expected);
        auto result = read_feature_flags(payload);
        expect_equal(result, expected, "Test 2: Mock pickle payload with empty flags");
    }

    // Test 3: Mock pickle payload with one flag (false)
    {
        std::map<std::string, bool> expected;
        expected["search"] = false;
        std::string payload = build_mock_pickle(expected);
        auto result = read_feature_flags(payload);
        expect_equal(result, expected, "Test 3: Mock pickle payload with one flag");
    }

    // Test 4: Invalid payload (not valid pickle format) - should raise
    assert_raises([]() { read_feature_flags("not pickle"); }, "Test 4: Invalid payload");

    // Test 5: Empty payload - should raise
    assert_raises([]() { read_feature_flags(""); }, "Test 5: Empty payload");

    // Test 6: Corrupt pickle (truncated) - should raise
    assert_raises([]() { read_feature_flags(std::string(1, static_cast<char>(1))); }, "Test 6: Truncated dict header");

    // Test 7: Corrupt pickle (unknown opcode) - should raise
    assert_raises([]() { read_feature_flags(std::string(1, static_cast<char>(99))); }, "Test 7: Unknown pickle opcode");

    // Test 8: Pickle payload missing 'flags' key - should raise
    assert_raises([]() {
        std::string payload;
        payload += static_cast<char>(1); // Dict
        payload += static_cast<char>(0); // 0 items
        read_feature_flags(payload);
    }, "Test 8: Pickle payload missing 'flags' key");

    // Test 9: Pickle payload where 'flags' is not a list - should raise
    assert_raises([]() {
        std::string payload;
        payload += static_cast<char>(1); // Dict
        payload += static_cast<char>(1); // 1 item
        payload += static_cast<char>(5); // key length
        payload += "flags";
        payload += static_cast<char>(3); // String value instead of List
        payload += static_cast<char>(3); // string length
        payload += "bad";
        read_feature_flags(payload);
    }, "Test 9: 'flags' is not a list");

    // Test 10: Pickle payload where flag item is not a dict - should raise
    assert_raises([]() {
        std::string payload;
        payload += static_cast<char>(1); // Dict
        payload += static_cast<char>(1); // 1 item
        payload += static_cast<char>(5); // key length
        payload += "flags";
        payload += static_cast<char>(2); // List
        payload += static_cast<char>(1); // 1 item in list
        payload += static_cast<char>(3); // String instead of Dict
        payload += static_cast<char>(3);
        payload += "bad";
        read_feature_flags(payload);
    }, "Test 10: Flag item is not a dict");

    // Test 11: Pickle payload where flag is missing 'name' - should raise
    assert_raises([]() {
        std::string payload;
        payload += static_cast<char>(1); // Dict
        payload += static_cast<char>(1); // 1 item
        payload += static_cast<char>(5); // key length
        payload += "flags";
        payload += static_cast<char>(2); // List
        payload += static_cast<char>(1); // 1 item in list
        payload += static_cast<char>(1); // Dict (flag)
        payload += static_cast<char>(1); // 1 item in flag dict
        payload += static_cast<char>(7); // key length
        payload += "enabled";
        payload += static_cast<char>(4); // Bool true
        read_feature_flags(payload);
    }, "Test 11: Flag missing 'name'");

    // Test 12: Pickle payload where 'enabled' is not a bool - should raise
    assert_raises([]() {
        std::string payload;
        payload += static_cast<char>(1); // Dict
        payload += static_cast<char>(1); // 1 item
        payload += static_cast<char>(5); // key length
        payload += "flags";
        payload += static_cast<char>(2); // List
        payload += static_cast<char>(1); // 1 item in list
        payload += static_cast<char>(1); // Dict (flag)
        payload += static_cast<char>(2); // 2 items in flag dict
        payload += static_cast<char>(4); // key length
        payload += "name";
        payload += static_cast<char>(3); // String
        payload += static_cast<char>(1); // length
        payload += "x";
        payload += static_cast<char>(7); // key length
        payload += "enabled";
        payload += static_cast<char>(3); // String instead of Bool
        payload += static_cast<char>(3);
        payload += "yes";
        read_feature_flags(payload);
    }, "Test 12: 'enabled' is not a bool");

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}