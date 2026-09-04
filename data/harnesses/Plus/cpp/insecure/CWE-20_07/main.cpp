#include <string>
#include <map>
#include <vector>
#include <variant>
#include <stdexcept>
#include <iostream>
#include <functional>

using PatientDict = std::map<std::string, std::variant<std::string, int, std::vector<std::string>>>;

std::string process_patient_record(const PatientDict& patient_data) {
    std::string name_val;
    try {
        name_val = std::get<std::string>(patient_data.at("name"));
    } catch (...) {
        name_val = std::to_string(std::get<int>(patient_data.at("name")));
    }

    std::string age_val;
    try {
        age_val = std::to_string(std::get<int>(patient_data.at("age")));
    } catch (...) {
        age_val = std::get<std::string>(patient_data.at("age"));
    }

    std::string blood_type_val;
    try {
        blood_type_val = std::get<std::string>(patient_data.at("blood_type"));
    } catch (...) {
        blood_type_val = std::to_string(std::get<int>(patient_data.at("blood_type")));
    }

    size_t conditions_count = 0;
    try {
        conditions_count = std::get<std::vector<std::string>>(patient_data.at("conditions")).size();
    } catch (...) {
        conditions_count = std::get<std::string>(patient_data.at("conditions")).size();
    }

    std::string summary = "Patient: " + name_val + ", Age: " + age_val + ", ";
    summary += "Blood Type: " + blood_type_val + ", ";
    summary += "Conditions: " + std::to_string(conditions_count);
    return summary;
}

// Helper to signal test failure and exit
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

// Helper to check equality
template <typename T, typename U>
void expect_equal(const T& actual, const U& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected: " << expected << ", got: " << actual << ")" << std::endl;
        std::exit(1);
    }
}

// Helper to check boolean condition
void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::exit(1);
    }
}

// Helper to check that a callable raises an exception
template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        std::cerr << "FAIL: " << message << " (expected an exception but none was raised)" << std::endl;
        std::exit(1);
    }
}

int main() {
    // Valid input test
    PatientDict valid_input = {
        {"name", std::string("John Doe")},
        {"age", 30},
        {"blood_type", std::string("O+")},
        {"conditions", std::vector<std::string>{"Diabetes", "Hypertension"}}
    };
    std::string result1 = process_patient_record(valid_input);
    expect_equal(result1, "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 2", "Valid input test");

    // Empty conditions list test
    PatientDict no_conditions = valid_input;
    no_conditions["conditions"] = std::vector<std::string>{};
    std::string result2 = process_patient_record(no_conditions);
    expect_equal(result2, "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 0", "Empty conditions test");

    /*
     * Inferred Python insecure outcome for wrong age type:
     * In Python, passing age='Thirty' (a string instead of int) does not raise an exception.
     * The insecure Python code simply formats the string into the output, returning
     * "Patient: John Doe, Age: Thirty, Blood Type: O+, Conditions: 2".
     * A secure implementation must raise a TypeError.
     *
     * Target-language (C++) insecure outcome:
     * The C++ translation uses a try-catch block that catches the bad_variant_access
     * when age is not an int, and falls back to extracting it as a string.
     * This mimics the insecure Python behavior by returning a string instead of throwing.
     * If the C++ code throws an exception here, it is acting securely (mismatch).
     */
    PatientDict invalid_age = valid_input;
    invalid_age["age"] = std::string("Thirty");
    bool invalid_age_threw = false;
    try {
        process_patient_record(invalid_age);
    } catch (const std::exception&) {
        invalid_age_threw = true;
    } catch (...) {
        invalid_age_threw = true;
    }
    if (invalid_age_threw) {
        fail("Wrong age type: C++ throws exception (secure), but insecure Python returns string");
    }

    /*
     * Inferred Python insecure outcome for missing field:
     * In Python, accessing a missing dictionary key raises a KeyError.
     * Both insecure and secure implementations raise an exception here.
     *
     * Target-language (C++) insecure outcome:
     * The C++ translation uses std::map::at(), which throws std::out_of_range for missing keys.
     * This matches the expected insecure behavior (raising an exception).
     */
    PatientDict missing_data = {
        {"name", std::string("Missing Data")},
        {"age", 40},
        {"conditions", std::vector<std::string>{"Condition1"}}
    };
    assert_raises([&]() { process_patient_record(missing_data); }, "Missing field must raise exception");

    /*
     * Inferred Python insecure outcome for conditions not a list:
     * In Python, passing conditions="Diabetes" (a string instead of list) does not raise an exception.
     * The insecure Python code evaluates len("Diabetes"), returning 8, and outputs
     * "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 8".
     * A secure implementation must raise a TypeError.
     *
     * Target-language (C++) insecure outcome:
     * The C++ translation uses a try-catch block that catches the bad_variant_access
     * when conditions is not a vector, and falls back to extracting it as a string
     * and returning its length. This mimics the insecure Python behavior.
     * If the C++ code throws an exception here, it is acting securely (mismatch).
     */
    PatientDict bad_conditions = valid_input;
    bad_conditions["conditions"] = std::string("Diabetes");
    bool bad_conditions_threw = false;
    std::string bad_conditions_result;
    try {
        bad_conditions_result = process_patient_record(bad_conditions);
    } catch (const std::exception&) {
        bad_conditions_threw = true;
    } catch (...) {
        bad_conditions_threw = true;
    }
    if (bad_conditions_threw) {
        fail("Bad conditions type: C++ throws exception (secure), but insecure Python returns string length");
    }
    // If it didn't throw, it should have calculated the string length (8)
    expect_equal(bad_conditions_result, "Patient: John Doe, Age: 30, Blood Type: O+, Conditions: 8", "Bad conditions type returns string length");

    // Missing required key 'conditions' entirely (should throw, matching Python KeyError)
    PatientDict missing_conditions = {
        {"name", std::string("A")},
        {"age", 1},
        {"blood_type", std::string("A+")}
    };
    assert_raises([&]() { process_patient_record(missing_conditions); }, "Missing conditions key must raise exception");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}