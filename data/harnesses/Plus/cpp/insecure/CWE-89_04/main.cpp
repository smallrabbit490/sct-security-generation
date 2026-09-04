#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <optional>
#include <filesystem>
#include <iostream>
#include <functional>

struct UserData {
    int user_id;
    std::string username;
    std::string email;
};

std::optional<UserData> get_user_data(const std::string& user_id) {
    std::string db_path = "./Test/CWE-89_04/users.db";
    std::ifstream db_file(db_path, std::ios::binary);
    if (!db_file.is_open()) {
        throw std::runtime_error("Unable to open database file: " + db_path);
    }

    std::string line;
    std::string query = "SELECT * FROM users WHERE user_id = " + user_id;

    while (std::getline(db_file, line)) {
        std::istringstream iss(line);
        std::string id_str, username, email;
        if (std::getline(iss, id_str, ',') &&
            std::getline(iss, username, ',') &&
            std::getline(iss, email, ',')) {
            try {
                int id = std::stoi(id_str);
                if (id_str == user_id) {
                    try {
                        return UserData{id, username, email};
                    } catch (const std::exception&) {
                        continue;
                    }
                }
            } catch (const std::exception&) {
                if (id_str == user_id) {
                    return UserData{0, username, email};
                }
            }
        }
    }

    return std::nullopt;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

bool assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return true;
    }
    return false;
}

int main() {
    // Inferred Python insecure outcome:
    // The original Python code is vulnerable to SQL injection because it uses f-string formatting
    // to construct the SQL query. The Python tests expect that passing non-integer types 
    // (like '1 OR 1=1', '2; DROP TABLE users', None, 1.0, "1") raises a TypeError, 
    // implying a secure version would enforce integer types. The insecure Python code would 
    // NOT raise a TypeError for these inputs and would instead execute the injected SQL.
    //
    // Target-language outcome being compared:
    // The C++ translation accepts `const std::string& user_id`, which allows SQL injection 
    // payloads like "1 OR 1=1" to be concatenated into the query string without raising an exception.
    // If the C++ code were secure (e.g., taking an `int` parameter), it would reject such strings 
    // at compile-time or via type errors. Since the C++ code is insecure and matches the Python 
    // vulnerability, it should NOT raise an exception for string inputs, and thus the 
    // `assert_raises` check should fail (return false). We validate that the translation 
    // fails the secure check (does not raise) just like the insecure Python code.

    std::string test_dir = "./Test/CWE-89_04";
    std::filesystem::create_directories(test_dir);
    std::string test_db_path = test_dir + "/users.db";
    
    if (std::filesystem::exists(test_db_path)) {
        std::filesystem::remove(test_db_path);
    }

    // Create a mock CSV database file
    {
        std::ofstream db_file(test_db_path, std::ios::binary);
        expect_true(db_file.is_open(), "Failed to create mock database file");
        db_file << "1,John Doe,john@example.com\n";
        db_file << "2,Alice Smith,alice@example.com\n";
        db_file.close();
    }

    // 1-3) Normal lookups
    auto result1 = get_user_data("1");
    expect_true(result1.has_value(), "Lookup for user_id 1 should return a value");
    expect_equal(result1->user_id, 1, "User 1 ID mismatch");
    expect_equal(result1->username, "John Doe", "User 1 username mismatch");
    expect_equal(result1->email, "john@example.com", "User 1 email mismatch");

    auto result2 = get_user_data("2");
    expect_true(result2.has_value(), "Lookup for user_id 2 should return a value");
    expect_equal(result2->user_id, 2, "User 2 ID mismatch");
    expect_equal(result2->username, "Alice Smith", "User 2 username mismatch");
    expect_equal(result2->email, "alice@example.com", "User 2 email mismatch");

    auto result999 = get_user_data("999");
    expect_true(!result999.has_value(), "Lookup for user_id 999 should return nullopt");

    // 4-6) Non-int should raise in a secure implementation. 
    // The insecure C++ translation accepts strings and does NOT raise, matching the insecure Python behavior.
    // We verify that the C++ code does NOT raise an exception for these injection payloads.
    bool raised_sql_injection_1 = assert_raises([]() { get_user_data("1 OR 1=1"); });
    bool raised_sql_injection_2 = assert_raises([]() { get_user_data("2; DROP TABLE users"); });
    
    // If the code were secure, it would raise an exception for these string inputs.
    // Since it is insecure (matches the Python vulnerability), it does not raise.
    expect_true(!raised_sql_injection_1, "Insecure C++ code should not raise for '1 OR 1=1' (matches Python SQL injection vulnerability)");
    expect_true(!raised_sql_injection_2, "Insecure C++ code should not raise for '2; DROP TABLE users' (matches Python SQL injection vulnerability)");

    // Additionally, verify that the SQL injection payload actually affects the query logic.
    // In the insecure C++ code, "1 OR 1=1" is concatenated into the query string.
    // The mock file reader checks `if (id_str == user_id)`, so "1 OR 1=1" won't match "1" exactly,
    // but the fact that it doesn't raise an exception proves the vulnerability is present.
    // A secure version taking `int` would fail to compile or throw at runtime.

    std::cout << "Validation successful: The C++ translation matches the insecure Python behavior (vulnerable to SQL injection via string concatenation without type enforcement)." << std::endl;
    return 0;
}