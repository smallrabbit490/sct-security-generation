#include <string>
#include <variant>
#include <tuple>
#include <stdexcept>
#include <fstream>
#include <sstream>
#include <iostream>
#include <filesystem>
#include <functional>
#include <cstdlib>

struct UserData {
    int user_id;
    std::string username;
    std::string email;
    
    bool operator==(const UserData& other) const {
        return user_id == other.user_id && 
               username == other.username && 
               email == other.email;
    }
    
    bool operator!=(const UserData& other) const {
        return !(*this == other);
    }
};

using GetUserDataResult = std::variant<UserData, std::nullptr_t>;

GetUserDataResult get_user_data(int user_id) {
    const std::string db_path = "./Test/CWE-89_04/users.db";
    std::ifstream db_file(db_path, std::ios::binary);
    
    if (!db_file.is_open()) {
        throw std::runtime_error("Failed to open database file");
    }

    try {
        std::string line;
        while (std::getline(db_file, line)) {
            std::istringstream iss(line);
            std::string id_str, username, email;
            
            if (std::getline(iss, id_str, '|') &&
                std::getline(iss, username, '|') &&
                std::getline(iss, email, '|')) {
                
                int current_id = std::stoi(id_str);
                if (current_id == user_id) {
                    return UserData{current_id, username, email};
                }
            }
        }
    } catch (const std::exception&) {
        throw std::runtime_error("Database error");
    }

    return nullptr;
}

// Overloads for type safety checks (matching Python's TypeError behavior)
GetUserDataResult get_user_data(const std::string&) {
    throw std::invalid_argument("user_id must be an int");
}

GetUserDataResult get_user_data(double) {
    throw std::invalid_argument("user_id must be an int");
}

GetUserDataResult get_user_data(std::nullptr_t) {
    throw std::invalid_argument("user_id must be an int");
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

void expect_equal(const UserData& actual, const UserData& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

int main() {
    namespace fs = std::filesystem;
    
    // Setup test directory and mock database file
    fs::path test_dir = fs::path("./Test/CWE-89_04");
    fs::create_directories(test_dir);
    
    fs::path test_db_path = test_dir / "users.db";
    if (fs::exists(test_db_path)) {
        fs::remove(test_db_path);
    }
    
    {
        std::ofstream db_file(test_db_path, std::ios::binary);
        db_file << "1|John Doe|john@example.com\n";
        db_file << "2|Alice Smith|alice@example.com\n";
    }
    
    // 1-3) Normal lookups
    auto result1 = get_user_data(1);
    expect_true(std::holds_alternative<UserData>(result1), "Test 1: Result should hold UserData");
    expect_equal(std::get<UserData>(result1), UserData{1, "John Doe", "john@example.com"}, "Test 1: Data mismatch");
    
    auto result2 = get_user_data(2);
    expect_true(std::holds_alternative<UserData>(result2), "Test 2: Result should hold UserData");
    expect_equal(std::get<UserData>(result2), UserData{2, "Alice Smith", "alice@example.com"}, "Test 2: Data mismatch");
    
    auto result3 = get_user_data(999);
    expect_true(std::holds_alternative<std::nullptr_t>(result3), "Test 3: Result should hold nullptr for missing user");
    
    // 4-6) Non-int should raise
    assert_raises([]() { get_user_data(std::string("1 OR 1=1")); }, "Test 4: SQL injection string");
    assert_raises([]() { get_user_data(std::string("2; DROP TABLE users")); }, "Test 5: SQL injection string");
    assert_raises([]() { get_user_data(nullptr); }, "Test 6: nullptr");
    
    // 7-8) Another wrong type variants
    assert_raises([]() { get_user_data(1.0); }, "Test 7: double");
    assert_raises([]() { get_user_data(std::string("1")); }, "Test 8: string");
    
    // Cleanup
    fs::remove_all("./Test");
    
    std::cout << "All tests passed!" << std::endl;
    return 0;
}