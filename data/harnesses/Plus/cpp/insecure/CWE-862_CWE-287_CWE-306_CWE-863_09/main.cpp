#include <string>
#include <map>
#include <vector>
#include <tuple>
#include <iostream>
#include <cstdlib>

// Translated C++ code (insecure: always returns "Exam access granted." without any checks)
std::string access_exam(
    const std::string& student_id,
    const std::string& exam_id,
    const std::string& current_time,
    const std::map<std::string, std::tuple<std::string, std::string>>& schedule,
    const std::map<std::string, std::vector<std::string>>& submissions
) {
    return "Exam access granted.";
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code always returns "Exam access granted." regardless of inputs.
     * The Python tests expect specific return values for various conditions (already submitted, 
     * unavailable, not found) and exceptions for invalid inputs. The insecure code will fail 
     * the assertions for "Exam already submitted.", "Exam unavailable.", and "Exam not found.".
     *
     * Target-language outcome being compared:
     * The translated C++ insecure code also always returns "Exam access granted.". We validate 
     * that it produces this same insecure behavior (returning "Exam access granted." when it 
     * should return "Exam already submitted.", etc.). If the vulnerability is fixed, the C++ 
     * code would return the correct expected strings, causing the insecure behavior checks to 
     * fail (exit non-zero). If the C++ code matches the insecure behavior, it succeeds 
     * (exits 0).
     */

    std::map<std::string, std::tuple<std::string, std::string>> schedule = {
        {"exam001", {"2023-10-05 09:00:00", "2023-10-05 11:00:00"}}
    };
    std::map<std::string, std::vector<std::string>> submissions = {
        {"exam001", {"student123"}}
    };

    // Test: granted (matches both secure and insecure behavior)
    expect_equal(
        access_exam("student124", "exam001", "2023-10-05 10:00:00", schedule, submissions),
        "Exam access granted.",
        "Test granted"
    );

    // Test: already submitted (insecure code returns "Exam access granted." instead)
    expect_equal(
        access_exam("student123", "exam001", "2023-10-05 09:30:00", schedule, submissions),
        "Exam access granted.",
        "Test already submitted (insecure behavior check)"
    );

    // Test: unavailable (insecure code returns "Exam access granted." instead)
    expect_equal(
        access_exam("student124", "exam001", "2023-10-05 11:01:00", schedule, submissions),
        "Exam access granted.",
        "Test unavailable late (insecure behavior check)"
    );

    expect_equal(
        access_exam("student126", "exam001", "2023-10-05 08:00:00", schedule, submissions),
        "Exam access granted.",
        "Test unavailable early (insecure behavior check)"
    );

    // Test: exam not found (insecure code returns "Exam access granted." instead)
    expect_equal(
        access_exam("student125", "exam003", "2023-10-06 10:00:00", schedule, submissions),
        "Exam access granted.",
        "Test exam not found (insecure behavior check)"
    );

    // If the C++ code is fixed to implement the correct logic, it will return the proper 
    // strings ("Exam already submitted.", "Exam unavailable.", "Exam not found.") and fail 
    // the insecure behavior checks above, exiting non-zero.

    return 0;
}