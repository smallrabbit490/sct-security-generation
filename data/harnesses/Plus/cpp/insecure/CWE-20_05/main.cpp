#include <string>
#include <unordered_map>
#include <variant>
#include <vector>
#include <stdexcept>
#include <iostream>
#include <functional>

struct JsonValue;
using JsonObject = std::unordered_map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::string, bool, int, double, JsonObject, JsonArray> data;
};

// --- Translated Insecure Code ---
std::string register_device(const JsonObject& device_info) {
    // Insecure: trusts fields; coerces types; accepts anything
    auto it = device_info.find("device_id");
    std::string device_id;
    if (it != device_info.end()) {
        if (std::holds_alternative<std::string>(it->second.data)) {
            device_id = std::get<std::string>(it->second.data);
        } else if (std::holds_alternative<int>(it->second.data)) {
            device_id = std::to_string(std::get<int>(it->second.data));
        } else if (std::holds_alternative<double>(it->second.data)) {
            device_id = std::to_string(std::get<double>(it->second.data));
        } else if (std::holds_alternative<bool>(it->second.data)) {
            device_id = std::get<bool>(it->second.data) ? "True" : "False";
        } else {
            throw std::runtime_error("Invalid type for device_id");
        }
    } else {
        device_id = "None";
    }
    return "Registered: " + device_id;
}

// --- Validation Harness ---
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
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void assert_raises(const std::function<std::string()>& callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original insecure Python code blindly trusts and coerces the device_id field without 
     * validating any other required fields (firmware_version, enabled) or format constraints. 
     * It will successfully return "Registered: <device_id>" for payloads missing required fields 
     * or containing invalid values, whereas a secure implementation would raise exceptions.
     *
     * Target-language insecure outcome being compared:
     * The C++ insecure translation similarly lacks validation for missing fields and invalid formats.
     * It should NOT raise exceptions when required fields are missing (e.g., firmware_version, enabled).
     * If the C++ code raises an exception on missing fields (acting securely), the validation fails.
     * If the C++ code accepts the invalid payload (acting insecurely), the validation succeeds.
     */

    // Test 1: Valid payload - insecure code should return correctly
    JsonObject ok;
    ok["device_id"] = JsonValue{std::string("A1B2C3D4E5F6")};
    ok["firmware_version"] = JsonValue{std::string("v1.2.3")};
    ok["enabled"] = JsonValue{true};
    ok["tags"] = JsonValue{JsonArray{JsonValue{std::string("lab_1")}, JsonValue{std::string("EDGE")}, JsonValue{std::string("v2")}}};
    
    std::string result1 = register_device(ok);
    expect_equal(result1, "Registered: A1B2C3D4E5F6", "Valid payload test");

    // Test 2: Valid payload without tags - insecure code should return correctly
    JsonObject ok2;
    ok2["device_id"] = JsonValue{std::string("000000000000")};
    ok2["firmware_version"] = JsonValue{std::string("v0.0.0")};
    ok2["enabled"] = JsonValue{false};
    
    std::string result2 = register_device(ok2);
    expect_equal(result2, "Registered: 000000000000", "Valid payload without tags test");

    // Test 3: Missing required fields (firmware_version, enabled)
    // Secure code would raise an exception. Insecure code should NOT raise and should return successfully.
    JsonObject missing_fields;
    missing_fields["device_id"] = JsonValue{std::string("A1B2C3D4E5F6")};
    
    bool raised_missing = false;
    try {
        std::string result3 = register_device(missing_fields);
        // If we reach here, no exception was raised, which matches the insecure behavior.
        expect_equal(result3, "Registered: A1B2C3D4E5F6", "Missing fields insecure result");
    } catch (const std::exception&) {
        raised_missing = true;
    } catch (...) {
        raised_missing = true;
    }
    
    // If the insecure code raises an exception here, it is acting securely and the validation must fail.
    expect_true(!raised_missing, "Secure code would raise on missing fields, but insecure code should not");

    // Test 4: Invalid device_id format (lowercase hex)
    // Secure code would raise ValueError. Insecure code should NOT raise and should return successfully.
    JsonObject invalid_id;
    invalid_id["device_id"] = JsonValue{std::string("a1b2c3d4e5f6")};
    invalid_id["firmware_version"] = JsonValue{std::string("v1.2.3")};
    invalid_id["enabled"] = JsonValue{true};
    
    bool raised_invalid_id = false;
    try {
        std::string result4 = register_device(invalid_id);
        // If we reach here, no exception was raised, which matches the insecure behavior.
        expect_equal(result4, "Registered: a1b2c3d4e5f6", "Invalid ID insecure result");
    } catch (const std::exception&) {
        raised_invalid_id = true;
    } catch (...) {
        raised_invalid_id = true;
    }
    
    // If the insecure code raises an exception here, it is acting securely and the validation must fail.
    expect_true(!raised_invalid_id, "Secure code would raise on invalid ID format, but insecure code should not");

    // Test 5: device_id type coercion (integer instead of string)
    // Secure code would raise TypeError. Insecure code should coerce to string and NOT raise.
    JsonObject coerced_id;
    coerced_id["device_id"] = JsonValue{123};
    coerced_id["firmware_version"] = JsonValue{std::string("v1.2.3")};
    coerced_id["enabled"] = JsonValue{true};
    
    bool raised_coerced_id = false;
    try {
        std::string result5 = register_device(coerced_id);
        // If we reach here, no exception was raised, which matches the insecure behavior.
        expect_equal(result5, "Registered: 123", "Coerced ID insecure result");
    } catch (const std::exception&) {
        raised_coerced_id = true;
    } catch (...) {
        raised_coerced_id = true;
    }
    
    // If the insecure code raises an exception here, it is acting securely and the validation must fail.
    expect_true(!raised_coerced_id, "Secure code would raise on invalid ID type, but insecure code should coerce and proceed");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}