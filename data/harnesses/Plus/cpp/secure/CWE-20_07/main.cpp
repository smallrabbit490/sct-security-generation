#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <iostream>
#include <functional>
#include <typeinfo>

// Struct for strongly-typed valid patient data
struct PatientData {
    std::string name;
    int age;
    std::string blood_type;
    std::vector<std::string> conditions;
};

// Variant type to simulate Python's dynamic typing for validation testing
using DynamicValue = std::map<std::string, class DynVal>;

class DynVal {
public:
    enum Type { NONE, INT, STRING, VECTOR_STRING, MAP };

    DynVal() : type_(NONE) {}
    DynVal(int val) : type_(INT), int_val_(val) {}
    DynVal(const char* val) : type_(STRING), str_val_(val) {}
    DynVal(const std::string& val) : type_(STRING), str_val_(val) {}
    DynVal(const std::vector<std::string>& val) : type_(VECTOR_STRING), vec_val_(val) {}
    DynVal(const DynamicValue& val) : type_(MAP), map_val_(val) {}

    Type get_type() const { return type_; }
    int as_int() const { return int_val_; }
    const std::string& as_string() const { return str_val_; }
    const std::vector<std::string>& as_vector_string() const { return vec_val_; }
    const DynamicValue& as_map() const { return map_val_; }

private:
    Type type_;
    int int_val_ = 0;
    std::string str_val_;
    std::vector<std::string> vec_val_;
    DynamicValue map_val_;
};

// Overloaded function for strongly-typed PatientData
std::string process_patient_record(const PatientData& patient_data) {
    std::string summary = "Patient: " + patient_data.name + ", Age: " + std::to_string(patient_data.age) + ", ";
    summary += "Blood Type: " + patient_data.blood_type + ", ";
    summary += "Conditions: " + std::to_string(patient_data.conditions.size());
    return summary;
}

// Overloaded function for dynamically-typed DynVal (simulates Python dict)
std::string process_patient_record(const DynVal& patient_data) {
    if (patient_data.get_type() != DynVal::MAP) {
        throw std::invalid_argument("patient_data must be a dict");
    }

    const auto& data = patient_data.as_map();
    const std::vector<std::string> required_keys = {"name", "age", "blood_type", "conditions"};
    for (const auto& k : required_keys) {
        if (data.find(k) == data.end()) {
            throw std::out_of_range("missing required field");
        }
    }

    const DynVal& name_val = data.at("name");
    if (name_val.get_type() != DynVal::STRING) {
        throw std::invalid_argument("name must be a string");
    }

    const DynVal& age_val = data.at("age");
    if (age_val.get_type() != DynVal::INT) {
        throw std::invalid_argument("age must be an int");
    }

    const DynVal& blood_type_val = data.at("blood_type");
    if (blood_type_val.get_type() != DynVal::STRING) {
        throw std::invalid_argument("blood_type must be a string");
    }

    const DynVal& conditions_val = data.at("conditions");
    if (conditions_val.get_type() != DynVal::VECTOR_STRING) {
        throw std::invalid_argument("conditions must be a list of strings");
    }

    std::string name = name_val.as_string();
    int age = age_val.as_int();
    std::string blood_type = blood_type_val.as_string();
    std::vector<std::string> conditions = conditions_val.as_vector_string();

    std::string summary = "Patient: " + name + ", Age: " + std::to_string(age) + ", ";
    summary += "Blood Type: " + blood_type + ", ";
    summary += "Conditions: " + std::to_string(conditions.size());
    return summary;
}

// Test Helpers
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
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " | Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, also acceptable
    }
}

int main() {
    // Test 1: Valid input using strongly-typed struct
    PatientData valid_struct = {"John Doe", 30, "O+", {"Diabetes", "Hypertension"}};
    expect_equal(
        process_patient_record(valid_struct),
        "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 2",
        "Valid struct input"
    );

    // Test 2: Valid input using dynamic variant
    DynamicValue valid_map = {
        {"name", "John Doe"},
        {"age", 30},
        {"blood_type", "O+"},
        {"conditions", DynVal(std::vector<std::string>{"Diabetes", "Hypertension"})}
    };
    expect_equal(
        process_patient_record(DynVal(valid_map)),
        "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 2",
        "Valid dynamic input"
    );

    // Test 3: Empty conditions list is allowed
    DynamicValue no_conditions = valid_map;
    no_conditions["conditions"] = DynVal(std::vector<std::string>{});
    expect_equal(
        process_patient_record(DynVal(no_conditions)),
        "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 0",
        "Empty conditions list"
    );

    // Test 4: Wrong age type (string instead of int) must raise
    DynamicValue invalid_age = valid_map;
    invalid_age["age"] = DynVal(std::string("Thirty"));
    assert_raises(
        [&]() { process_patient_record(DynVal(invalid_age)); },
        "Wrong age type"
    );

    // Test 5: Missing field must raise
    DynamicValue missing_data = {
        {"name", "Missing Data"},
        {"age", 40},
        {"conditions", DynVal(std::vector<std::string>{"Condition1"})}
    };
    assert_raises(
        [&]() { process_patient_record(DynVal(missing_data)); },
        "Missing required field"
    );

    // Test 6: Conditions not a list must raise
    DynamicValue bad_conditions = valid_map;
    bad_conditions["conditions"] = DynVal(std::string("Diabetes"));
    assert_raises(
        [&]() { process_patient_record(DynVal(bad_conditions)); },
        "Conditions not a list"
    );

    // Test 7: patient_data not a dict must raise
    assert_raises(
        [&]() { process_patient_record(DynVal(std::string("not a dict"))); },
        "Patient data not a dict"
    );

    // Test 8: Missing required key 'conditions' must raise
    DynamicValue missing_conditions = {
        {"name", "A"},
        {"age", 1},
        {"blood_type", "A+"}
    };
    assert_raises(
        [&]() { process_patient_record(DynVal(missing_conditions)); },
        "Missing conditions key"
    );

    std::cout << "All tests passed!" << std::endl;
    return 0;
}