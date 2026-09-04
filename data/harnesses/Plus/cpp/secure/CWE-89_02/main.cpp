#include <string>
#include <tuple>
#include <optional>
#include <regex>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <vector>
#include <iostream>
#include <cstdlib>
#include <functional>

struct UserRow {
    std::string username;
    std::string email;
    std::string role;
    
    bool operator==(const UserRow& other) const {
        return username == other.username && 
               email == other.email && 
               role == other.role;
    }
    
    bool operator!=(const UserRow& other) const {
        return !(*this == other);
    }
};

std::optional<UserRow> get_user_data(const std::string& username) {
    if (username.empty()) {
        throw std::invalid_argument("username must be non-empty");
    }
    
    std::regex valid_username_regex("^[A-Za-z0-9_]+$");
    if (!std::regex_match(username, valid_username_regex)) {
        throw std::invalid_argument("username contains unsupported characters");
    }

    std::filesystem::path db_path = std::filesystem::path("./Test/CWE-89_02/users.db");
    std::ifstream db_file(db_path, std::ios::binary);
    if (!db_file.is_open()) {
        throw std::runtime_error("Failed to open database");
    }

    std::string line;
    bool found = false;
    UserRow result;

    while (std::getline(db_file, line)) {
        std::istringstream iss(line);
        std::string file_username, file_email, file_role;
        
        if (std::getline(iss, file_username, '|') &&
            std::getline(iss, file_email, '|') &&
            std::getline(iss, file_role, '|')) {
            
            if (file_username == username) {
                result.username = file_username;
                result.email = file_email;
                result.role = file_role;
                found = true;
                break;
            }
        }
    }

    db_file.close();

    if (found) {
        return result;
    } else {
        return std::nullopt;
    }
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

void expect_equal(const std::optional<UserRow>& actual, const std::optional<UserRow>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str = actual.has_value() ? "(" + actual->username + ", " + actual->email + ", " + actual->role + ")" : "nullopt";
        std::string expected_str = expected.has_value() ? "(" + expected->username + ", " + expected->email + ", " + expected->role + ")" : "nullopt";
        fail(message + " | Expected: " + expected_str + " | Actual: " + actual_str);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " | Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still passes
    }
}

int main() {
    // Setup mock database
    std::filesystem::path test_dir = std::filesystem::path("./Test/CWE-89_02");
    std::filesystem::create_directories(test_dir);
    
    std::filesystem::path db_path = test_dir / "users.db";
    std::ofstream db_file(db_path, std::ios::binary | std::ios::trunc);
    if (!db_file.is_open()) {
        fail("Failed to create mock database file");
    }
    
    db_file << "john_doe|john.doe@example.com|user\n";
    db_file << "alice_smith|alice.smith@example.com|admin\n";
    db_file.close();

    // 1-3) Normal lookups
    expect_equal(get_user_data("john_doe"), UserRow{"john_doe", "john.doe@example.com", "user"}, "Test 1: Lookup john_doe");
    expect_equal(get_user_data("alice_smith"), UserRow{"alice_smith", "alice.smith@example.com", "admin"}, "Test 2: Lookup alice_smith");
    expect_equal(get_user_data("missing_user"), std::nullopt, "Test 3: Lookup missing_user");

    // 4) Empty username -> raise
    assert_raises([]() { get_user_data(""); }, "Test 4: Empty username");

    // 5) Wrong type -> raise (C++ std::string prevents non-string types at compile time, tested via invalid_argument for empty string)

    // 6-8) Inputs with unsupported characters -> raise (insecure likely returns a row for OR-based input)
    assert_raises([]() { get_user_data("' OR '1'='1' --"); }, "Test 6: SQL Injection attempt 1");
    assert_raises([]() { get_user_data("john_doe'; UPDATE users SET role='admin' WHERE username='john_doe'; --"); }, "Test 7: SQL Injection attempt 2");
    assert_raises([]() { get_user_data("john doe"); }, "Test 8: Username with space");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}