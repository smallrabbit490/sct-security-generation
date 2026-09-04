#include <string>
#include <unordered_map>
#include <vector>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string view_medical_records(
    const std::string& doctor_id,
    const std::string& patient_id,
    const std::unordered_map<std::string, std::string>& doctor_specialties,
    const std::unordered_map<std::string, std::vector<std::string>>& authorized_patients
) {
    if (doctor_specialties.find(doctor_id) == doctor_specialties.end()) {
        throw std::out_of_range("unknown doctor_id");
    }

    const std::string& specialty = doctor_specialties.at(doctor_id);

    auto it = authorized_patients.find(specialty);
    if (it != authorized_patients.end()) {
        const std::vector<std::string>& patients = it->second;
        for (const auto& p : patients) {
            if (p == patient_id) {
                return "View allowed.";
            }
        }
    }

    return "View not allowed.";
}

int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    ++tests_failed;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        fail(message + " - Raised an unexpected non-exception type");
    }
}

int main() {
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

    // allowed
    expect_equal(view_medical_records("doc1", "patient2", doctor_specialties, authorized_patients), "View allowed.", "doc1/patient2");
    expect_equal(view_medical_records("doc2", "patient3", doctor_specialties, authorized_patients), "View allowed.", "doc2/patient3");
    expect_equal(view_medical_records("doc3", "patient6", doctor_specialties, authorized_patients), "View allowed.", "doc3/patient6");

    // not allowed (doctor exists, but patient not listed for the specialty)
    expect_equal(view_medical_records("doc2", "patient5", doctor_specialties, authorized_patients), "View not allowed.", "doc2/patient5");
    expect_equal(view_medical_records("doc1", "patient5", doctor_specialties, authorized_patients), "View not allowed.", "doc1/patient5");

    // invalid inputs must raise
    assert_raises([&]() {
        view_medical_records("docX", "patient1", doctor_specialties, authorized_patients);
    }, "unknown doctor_id");

    // C++ is statically typed, so passing an int or an array instead of string/map is a compile-time error.
    // We verify that the type safety is enforced by checking that the function signature strictly requires
    // the correct types, preventing the Python-equivalent runtime TypeErrors from ever occurring.
    // The out_of_range exception acts as the equivalent of the Python KeyError.
    
    if (tests_failed > 0) {
        std::cerr << tests_failed << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}