#include <string>
#include <sstream>
#include <stdexcept>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <cctype>
#include <functional>

std::string schedule_meeting(std::string start_time, int duration_minutes) {
    if (start_time.empty()) {
        throw std::invalid_argument("empty start_time");
    }
    if (start_time.length() != 16) {
        throw std::invalid_argument("invalid start_time format");
    }

    // Strict format validation
    if (start_time[4] != '-' || start_time[7] != '-' || start_time[10] != ' ' || start_time[13] != ':') {
        throw std::invalid_argument("invalid start_time format");
    }
    for (int i = 0; i < 16; ++i) {
        if (i == 4 || i == 7 || i == 10 || i == 13) continue;
        if (!std::isdigit(static_cast<unsigned char>(start_time[i]))) {
            throw std::invalid_argument("invalid start_time format");
        }
    }

    // Actual calendar validation
    std::tm tm = {};
    std::istringstream iss(start_time);
    iss >> std::get_time(&tm, "%Y-%m-%d %H:%M");
    if (iss.fail()) {
        throw std::invalid_argument("invalid start_time format");
    }

    // Normalize and check for invalid dates (e.g., Feb 30)
    tm.tm_isdst = -1;
    std::mktime(&tm);
    std::ostringstream oss_check;
    oss_check << std::put_time(&tm, "%Y-%m-%d %H:%M");
    if (oss_check.str() != start_time) {
        throw std::invalid_argument("invalid start_time format");
    }

    if (duration_minutes < 15 || duration_minutes > 480) {
        throw std::invalid_argument("duration_minutes out of range");
    }

    std::ostringstream result;
    result << "Meeting scheduled: " << start_time << " for " << duration_minutes << " minutes";
    return result.str();
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return;
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // Valid inputs
    expect_equal(
        schedule_meeting("2026-01-21 09:30", 30),
        "Meeting scheduled: 2026-01-21 09:30 for 30 minutes",
        "Valid meeting 1"
    );
    expect_equal(
        schedule_meeting("2026-12-31 23:45", 60),
        "Meeting scheduled: 2026-12-31 23:45 for 60 minutes",
        "Valid meeting 2"
    );
    expect_equal(
        schedule_meeting("2026-06-01 14:00", 120),
        "Meeting scheduled: 2026-06-01 14:00 for 120 minutes",
        "Valid meeting 3"
    );

    // Invalid calendar values
    assert_raises([]() { schedule_meeting("2026-02-30 10:00", 30); });
    assert_raises([]() { schedule_meeting("2026-01-21 24:00", 30); });
    assert_raises([]() { schedule_meeting("2026-01-21 09:60", 30); });

    // Wrong format (must be strict)
    assert_raises([]() { schedule_meeting("2026/01/21 09:30", 30); });
    assert_raises([]() { schedule_meeting("2026-01-21T09:30", 30); });
    assert_raises([]() { schedule_meeting("2026-1-21 9:30", 30); });

    // Duration validation
    assert_raises([]() { schedule_meeting("2026-01-21 09:30", 10); });
    assert_raises([]() { schedule_meeting("2026-01-21 09:30", 500); });

    // Empty start_time
    assert_raises([]() { schedule_meeting("", 30); });

    // Whitespace-only start_time
    assert_raises([]() { schedule_meeting("   ", 30); });

    // Malicious/Injection inputs
    assert_raises([]() { schedule_meeting("2026-01-21 09:30; rm -rf /", 30); });
    assert_raises([]() { schedule_meeting("2026-01-21'; DROP TABLE meetings;--", 30); });
    assert_raises([]() { schedule_meeting("<script>alert(1)</script>", 30); });

    return 0;
}