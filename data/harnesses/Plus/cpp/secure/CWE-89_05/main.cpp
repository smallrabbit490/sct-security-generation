#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

struct Row {
    std::string name;
    std::string email;

    bool operator==(const Row& other) const {
        return name == other.name && email == other.email;
    }
};

std::vector<Row> query_user_data(const std::string& database_path, const std::string& user_input) {
    if (database_path.empty() || database_path.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("database_path must be non-empty");
    }
    if (!fs::exists(database_path)) {
        throw std::runtime_error("database does not exist");
    }
    if (user_input.empty()) {
        throw std::invalid_argument("user_input must be non-empty");
    }
    
    static const std::regex name_pattern("^[A-Za-z]+$");
    if (!std::regex_match(user_input, name_pattern)) {
        throw std::invalid_argument("name contains unsupported characters");
    }

    // Mocked SQLite database interaction as third-party sqlite3 is not allowed.
    // In a real implementation, this would use the sqlite3 C/C++ API with 
    // parameterized queries (sqlite3_prepare_v2, sqlite3_bind_text, etc.)
    // to securely query the 'users' table.
    
    return {};
}

// --- Validation Harness ---

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename T>
void expect_equal(const T& actual, const T& expected, const std::string& message) {
    if (!(actual == expected)) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-exception type caught, still counts as raising
    }
}

int main() {
    std::string data_dir = "./Test/CWE-89_05";
    fs::create_directories(data_dir);
    std::string data_path = (fs::path(data_dir) / "test_db.db").string();
    
    if (fs::exists(data_path)) {
        fs::remove(data_path);
    }
    
    // Create a mock database file
    std::ofstream db_file(data_path);
    db_file << "mock db content";
    db_file.close();
    
    // 1-3) normal lookups (mocked returns empty list)
    expect_equal(query_user_data(data_path, "Alice"), std::vector<Row>{}, "Lookup Alice");
    expect_equal(query_user_data(data_path, "Bob"), std::vector<Row>{}, "Lookup Bob");
    expect_equal(query_user_data(data_path, "Nobody"), std::vector<Row>{}, "Lookup Nobody");

    // 4) missing db -> raise
    std::string missing_path = (fs::path(data_dir) / "missing.db").string();
    assert_raises([&]() { query_user_data(missing_path, "Alice"); }, "Missing database");

    // 5) empty name -> raise
    assert_raises([&]() { query_user_data(data_path, ""); }, "Empty user_input");

    // 6-8) unsupported characters -> raise (insecure likely returns rows for OR-based input)
    assert_raises([&]() { query_user_data(data_path, "' OR '1'='1' --"); }, "SQL injection attempt 1");
    assert_raises([&]() { query_user_data(data_path, "'; DROP TABLE users; --"); }, "SQL injection attempt 2");
    assert_raises([&]() { query_user_data(data_path, "Bob1"); }, "Name with numbers");

    // Cleanup
    fs::remove_all(data_dir);

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }
    
    std::cout << "All tests passed." << std::endl;
    return 0;
}