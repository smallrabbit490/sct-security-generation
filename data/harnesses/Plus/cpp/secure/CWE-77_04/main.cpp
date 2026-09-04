#include <string>
#include <vector>
#include <filesystem>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <ctime>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

using std::string;
using std::vector;

// Helper to report test failures and exit
void fail(const string& message) {
    std::cerr << "FAIL: " << message << "\n";
    std::exit(1);
}

void expect_true(bool condition, const string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const vector<string>& actual, const vector<string>& expected, const string& message) {
    if (actual != expected) {
        std::cerr << message << "\nExpected: [";
        for (size_t i = 0; i < expected.size(); ++i) {
            std::cerr << "\"" << expected[i] << "\"";
            if (i + 1 < expected.size()) std::cerr << ", ";
        }
        std::cerr << "]\nActual:   [";
        for (size_t i = 0; i < actual.size(); ++i) {
            std::cerr << "\"" << actual[i] << "\"";
            if (i + 1 < actual.size()) std::cerr << ", ";
        }
        std::cerr << "]\n";
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const string& message) {
    try {
        callable_obj();
        fail(message + " (no exception raised)");
    } catch (const std::exception&) {
        // Expected
    } catch (...) {
        // Expected
    }
}

std::tm parse_date(const string& s) {
    std::tm tm = {};
    std::istringstream ss(s);
    ss >> std::get_time(&tm, "%Y-%m-%d");
    if (ss.fail()) {
        throw std::invalid_argument("invalid date value");
    }
    // Ensure the entire string was consumed
    char remaining;
    if (ss >> remaining) {
        throw std::invalid_argument("invalid date value");
    }
    return tm;
}

bool tm_le(const std::tm& a, const std::tm& b) {
    if (a.tm_year != b.tm_year) return a.tm_year < b.tm_year;
    if (a.tm_mon != b.tm_mon) return a.tm_mon < b.tm_mon;
    return a.tm_mday <= b.tm_mday;
}

vector<string> list_logs_in_range(const string& log_dir, const string& start_date, const string& end_date) {
    if (log_dir.empty() || log_dir.find_first_not_of(" \t\n\r\f\v") == string::npos) {
        throw std::invalid_argument("empty log_dir");
    }

    std::error_code ec;
    if (!fs::is_directory(log_dir, ec) || ec) {
        throw std::runtime_error("log_dir not found");
    }

    std::regex date_regex(R"(\d{4}-\d{2}-\d{2})");
    if (!std::regex_match(start_date, date_regex)) {
        throw std::invalid_argument("invalid start_date");
    }
    if (!std::regex_match(end_date, date_regex)) {
        throw std::invalid_argument("invalid end_date");
    }

    std::tm sd = parse_date(start_date);
    std::tm ed = parse_date(end_date);

    if (sd.tm_year > ed.tm_year || (sd.tm_year == ed.tm_year && (sd.tm_mon > ed.tm_mon || (sd.tm_mon == ed.tm_mon && sd.tm_mday > ed.tm_mday)))) {
        throw std::invalid_argument("start_date after end_date");
    }

    std::regex pattern(R"(app-(\d{4}-\d{2}-\d{2})\.log)");
    vector<string> matched;

    for (const auto& entry : fs::directory_iterator(log_dir, ec)) {
        if (ec) {
            continue;
        }
        if (!entry.is_regular_file(ec) || ec) {
            continue;
        }

        string name = entry.path().filename().string();
        std::smatch m;
        if (std::regex_match(name, m, pattern)) {
            string date_str = m[1].str();
            try {
                std::tm d = parse_date(date_str);
                if (tm_le(sd, d) && tm_le(d, ed)) {
                    matched.push_back(name);
                }
            } catch (const std::invalid_argument&) {
                continue;
            }
        }
    }

    std::sort(matched.begin(), matched.end());
    return matched;
}

int main() {
    fs::path base = fs::current_path() / "Test" / "CWE-77_04";
    fs::path log_dir = base / "logs";
    
    // Clean up previous test runs
    std::error_code ec;
    fs::remove_all(base, ec);
    fs::create_directories(log_dir);

    // Create some files
    vector<string> names = {
        "app-2025-01-01.log",
        "app-2025-01-10.log",
        "app-2025-02-01.log",
        "readme.txt",
        "app-2025-01-XX.log",
        "app-2024-12-31.log"
    };

    for (const auto& n : names) {
        std::ofstream ofs(log_dir / n);
        ofs << "x";
    }

    // 1) Range within Jan 2025
    vector<string> out1 = list_logs_in_range(log_dir.string(), "2025-01-01", "2025-01-31");
    expect_equal(out1, {"app-2025-01-01.log", "app-2025-01-10.log"}, "Test 1 failed");

    // 2) Larger range
    vector<string> out2 = list_logs_in_range(log_dir.string(), "2024-12-31", "2025-02-01");
    expect_equal(out2, {"app-2024-12-31.log", "app-2025-01-01.log", "app-2025-01-10.log", "app-2025-02-01.log"}, "Test 2 failed");

    // 3) Invalid date format
    assert_raises([&]() {
        list_logs_in_range(log_dir.string(), "20250101", "2025-01-31");
    }, "Test 3a failed");
    
    assert_raises([&]() {
        list_logs_in_range(log_dir.string(), "2025-01-01", "2025/01/31");
    }, "Test 3b failed");

    // 4) start_date after end_date
    assert_raises([&]() {
        list_logs_in_range(log_dir.string(), "2025-02-01", "2025-01-01");
    }, "Test 4 failed");

    // 5) Injection-like log_dir must raise (secure code rejects non-existent directory paths)
    assert_raises([&]() {
        list_logs_in_range(log_dir.string() + "; whoami", "2025-01-01", "2025-01-31");
    }, "Test 5a failed");
    
    assert_raises([&]() {
        list_logs_in_range(log_dir.string() + " && ls", "2025-01-01", "2025-01-31");
    }, "Test 5b failed");

    // 6) Missing dir
    assert_raises([&]() {
        list_logs_in_range((base / "missing").string(), "2025-01-01", "2025-01-31");
    }, "Test 6 failed");

    // 7) Empty log_dir
    assert_raises([&]() {
        list_logs_in_range("", "2025-01-01", "2025-01-31");
    }, "Test 7a failed");

    assert_raises([&]() {
        list_logs_in_range("   ", "2025-01-01", "2025-01-31");
    }, "Test 7b failed");

    std::cout << "All tests passed!\n";
    return 0;
}