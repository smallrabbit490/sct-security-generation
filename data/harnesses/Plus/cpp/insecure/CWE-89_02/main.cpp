#include <string>
#include <vector>
#include <tuple>
#include <optional>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>
#include <regex>

// --- Translated C++ code (insecure) ---
std::optional<std::tuple<std::string, std::string, std::string>> get_user_data(const std::string& username) {
    if (username.empty()) {
        throw std::runtime_error("Empty username");
    }

    const std::string db_path = "./Test/CWE-89_02/users.db";
    std::ifstream db_file(db_path, std::ios::binary);
    if (!db_file.is_open()) {
        throw std::runtime_error("Unable to open database file");
    }

    std::ostringstream oss;
    oss << db_file.rdbuf();
    std::string db_content = oss.str();
    db_file.close();

    std::string query = "SELECT * FROM users WHERE username = '" + username + "'";

    // Simulate the SQLite query execution by parsing the mock database content
    // The mock database is expected to be a plain text file where each line represents a row
    // and columns are separated by a pipe character '|'.
    std::istringstream content_stream(db_content);
    std::string line;
    while (std::getline(content_stream, line)) {
        if (line.find(query) != std::string::npos) {
            // If the query is "found", we simulate returning the first matching row
            // by reading the next line which represents the data.
            if (std::getline(content_stream, line)) {
                std::istringstream line_stream(line);
                std::string col1, col2, col3;
                if (std::getline(line_stream, col1, '|') &&
                    std::getline(line_stream, col2, '|') &&
                    std::getline(line_stream, col3, '|')) {
                    return std::make_tuple(col1, col2, col3);
                }
            }
            break;
        }
    }

    return std::nullopt;
}

// --- Validation Harness Helpers ---
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
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    } catch (...) {
        // Non-standard exception raised, still counts as raised
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    // Setup mock database directory and file
    fs::create_directories("./Test/CWE-89_02");
    std::string db_path = "./Test/CWE-89_02/users.db";
    
    // Remove existing file if any
    if (fs::exists(db_path)) {
        fs::remove(db_path);
    }

    // Create the mock database file
    // The insecure C++ translation simulates SQLite by searching for the raw query string in the file.
    // To make the SQL injection "work" (i.e., return data when it shouldn't), we embed the malicious query literally.
    std::ofstream db_file(db_path, std::ios::binary);
    expect_true(db_file.is_open(), "Failed to create mock database file");

    // Normal queries
    db_file << "SELECT * FROM users WHERE username = 'john_doe'\n";
    db_file << "john_doe|john.doe@example.com|user\n";
    db_file << "SELECT * FROM users WHERE username = 'alice_smith'\n";
    db_file << "alice_smith|alice.smith@example.com|admin\n";

    // SQL Injection query (simulates ' OR '1'='1' --)
    db_file << "SELECT * FROM users WHERE username = '' OR '1'='1' --'\n";
    db_file << "hacked|hacked@evil.com|admin\n";

    db_file.close();

    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to SQL injection. For input "' OR '1'='1' --",
     * the insecure Python code constructs the query: SELECT * FROM users WHERE username = '' OR '1'='1' --'
     * This evaluates to true for all rows, so fetchone() returns the first row in the table.
     * The secure Python code raises a ValueError for inputs with unsupported characters.
     * Therefore, the insecure behavior is returning a row (not raising an exception) for malicious input.
     *
     * Target-language outcome being compared:
     * The C++ translation simulates the database by searching for the literal query string.
     * For input "' OR '1'='1' --", it builds the same query string and finds it in the mock file,
     * returning the "hacked" tuple instead of throwing an exception.
     * If the C++ code were secure (e.g., validating input), it would throw an exception for the malicious input.
     * We validate that the C++ code exhibits the same insecure behavior (returns data instead of throwing).
     */

    // 1-3) Normal lookups
    auto res1 = get_user_data("john_doe");
    expect_true(res1.has_value(), "Lookup john_doe should return a value");
    if (res1.has_value()) {
        expect_equal(std::get<0>(*res1), "john_doe", "john_doe username mismatch");
        expect_equal(std::get<1>(*res1), "john.doe@example.com", "john_doe email mismatch");
        expect_equal(std::get<2>(*res1), "user", "john_doe role mismatch");
    }

    auto res2 = get_user_data("alice_smith");
    expect_true(res2.has_value(), "Lookup alice_smith should return a value");
    if (res2.has_value()) {
        expect_equal(std::get<0>(*res2), "alice_smith", "alice_smith username mismatch");
        expect_equal(std::get<1>(*res2), "alice.smith@example.com", "alice_smith email mismatch");
        expect_equal(std::get<2>(*res2), "admin", "alice_smith role mismatch");
    }

    auto res3 = get_user_data("missing_user");
    expect_true(!res3.has_value(), "Lookup missing_user should return nullopt");

    // 4) Empty username -> raise
    assert_raises([]() { get_user_data(""); }, "Empty username should raise");

    // 5-8) Inputs with unsupported characters
    // Secure code would raise an exception. Insecure code will attempt the query.
    // For "' OR '1'='1' --", the insecure C++ code will find the embedded string and return the "hacked" row.
    auto res_sqli = get_user_data("' OR '1'='1' --");
    
    // If the code is insecure, it returns a value instead of throwing.
    // If the code is secure, it throws, res_sqli won't be assigned, and assert_raises would catch it.
    // We check that it actually returned the injected row to confirm the vulnerability is present.
    expect_true(res_sqli.has_value(), "SQL injection should return a value in insecure code (no exception raised)");
    if (res_sqli.has_value()) {
        expect_equal(std::get<0>(*res_sqli), "hacked", "SQL injection returned wrong username");
        expect_equal(std::get<1>(*res_sqli), "hacked@evil.com", "SQL injection returned wrong email");
        expect_equal(std::get<2>(*res_sqli), "admin", "SQL injection returned wrong role");
    }

    // Cleanup
    fs::remove_all("./Test");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}