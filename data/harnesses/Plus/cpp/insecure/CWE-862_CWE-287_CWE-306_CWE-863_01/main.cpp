#include <string>
#include <unordered_map>
#include <vector>
#include <iostream>
#include <cstdlib>

// Translated C++ code (insecure version)
std::string view_medical_records(
    const std::string& doctor_id,
    const std::string& patient_id,
    const std::unordered_map<std::string, std::string>& doctor_specialties,
    const std::unordered_map<std::string, std::vector<std::string>>& authorized_patients
) {
    return "Doctor is authorized to view medical records of the specified patient.";
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The insecure Python code always returns an authorization-granted message regardless of inputs.
     * It does not check doctor_specialties or authorized_patients, so it grants access even when
     * the doctor is not authorized for the patient, and it does not raise exceptions for invalid inputs.
     * 
     * Target-language outcome being compared:
     * The C++ translation must exhibit the same insecure behavior: it must return the authorization
     * message for valid authorized pairs (matching the insecure Python's permissive return), and
     * critically, it must also return the authorization message for unauthorized pairs instead of
     * returning "View not allowed." or raising an exception. If the C++ code is fixed to properly
     * deny unauthorized access, the validation must fail (exit non-zero).
     */

    std::unordered_map<std::string, std::string> doctor_specialties = {
        {"doc1", "cardiologist"},
        {"doc2", "neurologist"},
        {"doc3", "dermatologist"},
        {"doc4", "radiologist"}
    };

    std::unordered_map<std::string, std::vector<std::string>> authorized_patients = {
        {"cardiologist", {"patient1", "patient2"}},
        {"neurologist", {"patient3", "patient4"}},
        {"dermatologist", {"patient5", "patient6"}}
    };

    // The insecure Python code returns a generic authorization message for ALL inputs.
    // We verify the C++ translation matches this insecure behavior.

    // Test 1: Valid authorized access - insecure code permits this
    std::string result1 = view_medical_records("doc1", "patient2", doctor_specialties, authorized_patients);
    expect_equal(result1, "Doctor is authorized to view medical records of the specified patient.",
                 "Valid access did not return insecure authorization message");

    // Test 2: Unauthorized access - insecure code incorrectly permits this (vulnerability)
    std::string result2 = view_medical_records("doc2", "patient5", doctor_specialties, authorized_patients);
    expect_equal(result2, "Doctor is authorized to view medical records of the specified patient.",
                 "Invalid doctor-patient pair did not grant unauthorized access - C++ code is more secure than insecure Python (which would not raise/deny)");

    // Test 3: Another unauthorized access - insecure code incorrectly permits this (vulnerability)
    std::string result3 = view_medical_records("doc1", "patient5", doctor_specialties, authorized_patients);
    expect_equal(result3, "Doctor is authorized to view medical records of the specified patient.",
                 "Unauthorized patient access was denied - C++ code is more secure than insecure Python");

    // Test 4: Non-existent doctor - insecure code does not raise KeyError, it permits access
    std::string result4 = view_medical_records("docX", "patient1", doctor_specialties, authorized_patients);
    expect_equal(result4, "Doctor is authorized to view medical records of the specified patient.",
                 "Invalid doctor ID did not grant unauthorized access - C++ code is more secure than insecure Python (which would not raise/deny)");

    // If all tests pass, the C++ code matches the insecure Python behavior
    std::cout << "All validation checks passed. C++ code matches insecure Python behavior." << std::endl;
    return 0;
}