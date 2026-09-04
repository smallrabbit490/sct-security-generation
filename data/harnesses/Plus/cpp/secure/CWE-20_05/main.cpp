#include <string>
#include <map>
#include <vector>
#include <stdexcept>
#include <cctype>
#include <sstream>
#include <iostream>
#include <functional>

struct Value {
    enum Type { Null, Bool, String, List, Dict };
    Type type = Null;
    bool bool_val = false;
    std::string string_val;
    std::vector<Value> list_val;
    std::map<std::string, Value> dict_val;

    Value() : type(Null) {}
    Value(bool b) : type(Bool), bool_val(b) {}
    Value(const std::string& s) : type(String), string_val(s) {}
    Value(const char* s) : type(String), string_val(s) {}
    Value(const std::vector<Value>& l) : type(List), list_val(l) {}
    Value(const std::map<std::string, Value>& d) : type(Dict), dict_val(d) {}

    bool has_key(const std::string& key) const {
        return type == Dict && dict_val.count(key) > 0;
    }

    const Value& operator[](const std::string& key) const {
        if (type == Dict) {
            auto it = dict_val.find(key);
            if (it != dict_val.end()) return it->second;
        }
        static Value null_val;
        return null_val;
    }
};

static bool is_valid_hex12(const std::string& s) {
    if (s.size() != 12) return false;
    for (char c : s) {
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'))) {
            return false;
        }
    }
    return true;
}

static bool is_valid_tag(const std::string& s) {
    if (s.empty() || s.size() > 20) return false;
    for (char c : s) {
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
              (c >= '0' && c <= '9') || c == '_')) {
            return false;
        }
    }
    return true;
}

static bool parse_firmware(const std::string& s, int& major, int& minor, int& patch) {
    if (s.empty() || s[0] != 'v') return false;
    
    size_t pos1 = s.find('.');
    if (pos1 == std::string::npos || pos1 == 1) return false;
    
    size_t pos2 = s.find('.', pos1 + 1);
    if (pos2 == std::string::npos || pos2 == pos1 + 1) return false;
    
    if (pos2 + 1 >= s.size()) return false;
    
    std::string major_s = s.substr(1, pos1 - 1);
    std::string minor_s = s.substr(pos1 + 1, pos2 - pos1 - 1);
    std::string patch_s = s.substr(pos2 + 1);
    
    if (major_s.empty() || major_s.size() > 3 ||
        minor_s.empty() || minor_s.size() > 3 ||
        patch_s.empty() || patch_s.size() > 3) {
        return false;
    }
    
    for (char c : major_s) if (!std::isdigit(static_cast<unsigned char>(c))) return false;
    for (char c : minor_s) if (!std::isdigit(static_cast<unsigned char>(c))) return false;
    for (char c : patch_s) if (!std::isdigit(static_cast<unsigned char>(c))) return false;
    
    major = std::stoi(major_s);
    minor = std::stoi(minor_s);
    patch = std::stoi(patch_s);
    
    return true;
}

std::string register_device(const Value& device_info) {
    if (device_info.type != Value::Dict) {
        throw std::runtime_error("device_info must be a dict");
    }

    const char* required[] = {"device_id", "firmware_version", "enabled"};
    for (const char* k : required) {
        if (!device_info.has_key(k)) {
            throw std::runtime_error("missing required field");
        }
    }

    const Value& device_id_val = device_info["device_id"];
    const Value& fw_val = device_info["firmware_version"];
    const Value& enabled_val = device_info["enabled"];

    if (device_id_val.type != Value::String) {
        throw std::runtime_error("device_id must be a string");
    }
    const std::string& device_id = device_id_val.string_val;
    if (!is_valid_hex12(device_id)) {
        throw std::runtime_error("invalid device_id");
    }

    if (fw_val.type != Value::String) {
        throw std::runtime_error("firmware_version must be a string");
    }
    const std::string& fw = fw_val.string_val;
    int major, minor, patch;
    if (!parse_firmware(fw, major, minor, patch)) {
        throw std::runtime_error("invalid firmware_version");
    }
    if (major < 0 || major > 999 || minor < 0 || minor > 999 || patch < 0 || patch > 999) {
        throw std::runtime_error("invalid firmware_version");
    }

    if (enabled_val.type != Value::Bool) {
        throw std::runtime_error("enabled must be a bool");
    }

    if (device_info.has_key("tags")) {
        const Value& tags_val = device_info["tags"];
        if (tags_val.type != Value::List) {
            throw std::runtime_error("tags must be a list");
        }
        for (const Value& t : tags_val.list_val) {
            if (t.type != Value::String) {
                throw std::runtime_error("tag must be a string");
            }
            if (!is_valid_tag(t.string_val)) {
                throw std::runtime_error("invalid tag");
            }
        }
    }

    return "Registered: " + device_id;
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void assert_raises(const std::function<std::string()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    } catch (...) {
        // Expected
    }
}

int main() {
    // Test 1: Valid with tags
    Value ok1(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)},
        {"tags", Value(std::vector<Value>{Value("lab_1"), Value("EDGE"), Value("v2")})}
    });
    expect_equal(register_device(ok1), "Registered: A1B2C3D4E5F6", "Test 1");

    // Test 2: Valid without tags
    Value ok2(std::map<std::string, Value>{
        {"device_id", Value("000000000000")},
        {"firmware_version", Value("v0.0.0")},
        {"enabled", Value(false)}
    });
    expect_equal(register_device(ok2), "Registered: 000000000000", "Test 2");

    // Test 3: Valid max firmware
    Value ok3(std::map<std::string, Value>{
        {"device_id", Value("FFFFFFFFFFFF")},
        {"firmware_version", Value("v10.20.30")},
        {"enabled", Value(true)},
        {"tags", Value(std::vector<Value>{Value("prod"), Value("beta_2026")})}
    });
    expect_equal(register_device(ok3), "Registered: FFFFFFFFFFFF", "Test 3");

    // Test 4: Missing required fields
    Value missing_field(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")}
    });
    assert_raises([&]() { return register_device(missing_field); }, "Test 4");

    // Test 5: device_id validation (lowercase)
    Value bad_id1(std::map<std::string, Value>{
        {"device_id", Value("a1b2c3d4e5f6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_id1); }, "Test 5a");

    // Test 5b: device_id validation (too short)
    Value bad_id2(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_id2); }, "Test 5b");

    // Test 5c: device_id validation (invalid char)
    Value bad_id3(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5FZ")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_id3); }, "Test 5c");

    // Test 5d: device_id validation (not a string)
    Value bad_id4(std::map<std::string, Value>{
        {"device_id", Value(123)},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_id4); }, "Test 5d");

    // Test 6: firmware validation (missing 'v')
    Value bad_fw1(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("1.2.3")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_fw1); }, "Test 6a");

    // Test 6b: firmware validation (missing patch)
    Value bad_fw2(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_fw2); }, "Test 6b");

    // Test 6c: firmware validation (extra segment)
    Value bad_fw3(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3.4")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_fw3); }, "Test 6c");

    // Test 6d: firmware validation (negative minor)
    Value bad_fw4(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.-2.3")},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_fw4); }, "Test 6d");

    // Test 6e: firmware validation (not a string)
    Value bad_fw5(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value()},
        {"enabled", Value(true)}
    });
    assert_raises([&]() { return register_device(bad_fw5); }, "Test 6e");

    // Test 7: enabled must be bool (not int)
    Value bad_en1(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value("true")}
    });
    assert_raises([&]() { return register_device(bad_en1); }, "Test 7");

    // Test 8: tags validation (not a list)
    Value bad_tags1(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)},
        {"tags", Value("lab_1")}
    });
    assert_raises([&]() { return register_device(bad_tags1); }, "Test 8a");

    // Test 8b: tags validation (invalid tag chars)
    Value bad_tags2(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)},
        {"tags", Value(std::vector<Value>{Value("ok"), Value("bad-tag")})}
    });
    assert_raises([&]() { return register_device(bad_tags2); }, "Test 8b");

    // Test 8c: tags validation (empty tag)
    Value bad_tags3(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)},
        {"tags", Value(std::vector<Value>{Value("")})}
    });
    assert_raises([&]() { return register_device(bad_tags3); }, "Test 8c");

    // Test 8d: tags validation (tag too long)
    Value bad_tags4(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)},
        {"tags", Value(std::vector<Value>{Value(std::string(21, 'x'))})}
    });
    assert_raises([&]() { return register_device(bad_tags4); }, "Test 8d");

    // Test 8e: tags validation (tag not a string)
    Value bad_tags5(std::map<std::string, Value>{
        {"device_id", Value("A1B2C3D4E5F6")},
        {"firmware_version", Value("v1.2.3")},
        {"enabled", Value(true)},
        {"tags", Value(std::vector<Value>{Value("ok"), Value(123)})}
    });
    assert_raises([&]() { return register_device(bad_tags5); }, "Test 8e");

    // Test 9: device_info must be dict
    Value not_dict1;
    assert_raises([&]() { return register_device(not_dict1); }, "Test 9a");

    Value not_dict2(std::vector<Value>{Value("not"), Value("dict")});
    assert_raises([&]() { return register_device(not_dict2); }, "Test 9b");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}