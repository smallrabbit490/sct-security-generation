#include <string>
#include <unordered_map>
#include <vector>
#include <stdexcept>
#include <ctime>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <functional>

std::string access_exam(
    const std::string& student_id,
    const std::string& exam_id,
    const std::string& current_time,
    const std::unordered_map<std::string, std::pair<std::string, std::string>>& schedule,
    const std::unordered_map<std::string, std::vector<std::string>>& submissions
) {
    const char* fmt = "%Y-%m-%d %H:%M:%S";

    auto parse_time = [&](const std::string& time_str) -> std::tm {
        std::tm tm = {};
        std::istringstream iss(time_str);
        iss >> std::get_time(&tm, fmt);
        if (iss.fail()) {
            throw std::invalid_argument("invalid time format");
        }
        return tm;
    };

    auto it = schedule.find(exam_id);
    if (it == schedule.end()) {
        return "Exam not found.";
    }

    const auto& start_time = it->second.first;
    const auto& end_time = it->second.second;

    std::tm now_tm = parse_time(current_time);
    std::tm start_tm = parse_time(start_time);
    std::tm end_tm = parse_time(end_time);

    std::time_t now_t = std::mktime(&now_tm);
    std::time_t start_t = std::mktime(&start_tm);
    std::time_t end_t = std::mktime(&end_tm);

    if (now_t < start_t || now_t > end_t) {
        return "Exam unavailable.";
    }

    auto sub_it = submissions.find(exam_id);
    if (sub_it != submissions.end()) {
        const auto& already = sub_it->second;
        for (const auto& sid : already) {
            if (sid == student_id) {
                return "Exam already submitted.";
            }
        }
    }

    return "Exam access granted.";
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

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still passes the "raises" check
    }
}

int main() {
    std::unordered_map<std::string, std::pair<std::string, std::string>> schedule = {
        {"exam001", {"2023-10-05 09:00:00", "2023-10-05 11:00:00"}}
    };
    std::unordered_map<std::string, std::vector<std::string>> submissions = {
        {"exam001", {"student123"}}
    };

    // granted
    expect_equal(
        access_exam("student124", "exam001", "2023-10-05 10:00:00", schedule, submissions),
        "Exam access granted.",
        "Test 1: Exam access granted"
    );

    // already submitted
    expect_equal(
        access_exam("student123", "exam001", "2023-10-05 09:30:00", schedule, submissions),
        "Exam already submitted.",
        "Test 2: Exam already submitted"
    );

    // unavailable
    expect_equal(
        access_exam("student124", "exam001", "2023-10-05 11:01:00", schedule, submissions),
        "Exam unavailable.",
        "Test 3: Exam unavailable (after end)"
    );

    expect_equal(
        access_exam("student126", "exam001", "2023-10-05 08:00:00", schedule, submissions),
        "Exam unavailable.",
        "Test 4: Exam unavailable (before start)"
    );

    // exam not found
    expect_equal(
        access_exam("student125", "exam003", "2023-10-06 10:00:00", schedule, submissions),
        "Exam not found.",
        "Test 5: Exam not found"
    );

    // invalid inputs
    assert_raises([&]() {
        access_exam("student124", "exam001", "2023/10/05 10:00:00", schedule, submissions);
    }, "Test 6: Invalid time format");

    // C++ is statically typed, so passing an int instead of string or a vector instead of map
    // is a compile-time error rather than a runtime TypeError. We verify that the function
    // enforces type safety by design. No runtime assert_raises is needed or possible for these.

    std::cout << "All tests passed!" << std::endl;
    return 0;
}