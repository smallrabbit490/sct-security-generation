#include <string>
#include <vector>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <iostream>
#include <functional>
#include <algorithm>
#include <cctype>

struct Row {
    std::string name;
    std::string email;
};

std::vector<Row> query_user_data(const std::string& database_path, const std::string& user_input) {
    std::vector<Row> results;

    if (!std::filesystem::exists(database_path)) {
        throw std::runtime_error("Database file does not exist");
    }

    std::ifstream db_file(database_path, std::ios::binary);
    if (!db_file.is_open()) {
        throw std::runtime_error("Cannot open database file");
    }

    // Simulate SQLite connection and query execution
    // The original Python code is vulnerable to SQL injection via string concatenation.
    // We preserve this insecure behavior by constructing the query string identically.
    std::string query = "SELECT * FROM users WHERE name = '" + user_input + "'";

    // Mock parsing the database file to find matching rows
    // Assuming a mock CSV-like structure for the "users" table: name,email
    std::string line;
    bool in_users_table = false;
    while (std::getline(db_file, line)) {
        if (line == "CREATE TABLE users (name TEXT, email TEXT);") {
            in_users_table = true;
            continue;
        }
        if (line.find("CREATE TABLE") == 0) {
            in_users_table = false;
        }
        if (in_users_table && line.find("INSERT INTO users VALUES(") == 0) {
            // Parse: INSERT INTO users VALUES('name','email');
            size_t v_start = line.find("VALUES(") + 7;
            size_t v_end = line.rfind(");");
            if (v_start != std::string::npos && v_end != std::string::npos && v_end > v_start) {
                std::string values = line.substr(v_start, v_end - v_start);
                
                // Extract name
                size_t n_start = values.find("'") + 1;
                size_t n_end = values.find("'", n_start);
                std::string db_name = values.substr(n_start, n_end - n_start);
                
                // Extract email
                size_t e_start = values.find("'", n_end + 2) + 1;
                size_t e_end = values.find("'", e_start);
                std::string db_email = values.substr(e_start, e_end - e_start);

                // Insecurely evaluate the injected query logic
                // This mimics the database engine evaluating the concatenated WHERE clause
                std::string eval_query = "SELECT * FROM users WHERE name = '" + db_name + "'";
                if (eval_query == query) {
                    results.push_back({db_name, db_email});
                }
            }
        }
    }

    db_file.close();
    return results;
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

void expect_equal(const std::vector<Row>& actual, const std::vector<Row>& expected, const std::string& message) {
    if (actual.size() != expected.size()) {
        fail(message + " (size mismatch: " + std::to_string(actual.size()) + " vs " + std::to_string(expected.size()) + ")");
    }
    for (size_t i = 0; i < actual.size(); ++i) {
        if (actual[i].name != expected[i].name || actual[i].email != expected[i].email) {
            fail(message + " (row " + std::to_string(i) + " mismatch)");
        }
    }
}

void assert_raises(const std::function<void()>& callable, const std::string& message) {
    try {
        callable();
        fail(message + " (no exception raised)");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-std exception caught, still an exception
    }
}

bool is_alpha_only(const std::string& s) {
    for (char c : s) {
        if (!std::isalpha(static_cast<unsigned char>(c))) {
            return false;
        }
    }
    return true;
}

// --- Main Validation Entry Point ---

int main() {
    std::string data_dir = "./Test/CWE-89_05";
    std::filesystem::create_directories(data_dir);
    std::string data_path = data_dir + "/test_db.db";
    
    if (std::filesystem::exists(data_path)) {
        std::filesystem::remove(data_path);
    }

    // Create mock database file
    {
        std::ofstream db_file(data_path, std::ios::binary);
        db_file << "CREATE TABLE users (name TEXT, email TEXT);\n";
        db_file << "INSERT INTO users VALUES('Alice','alice@example.com');\n";
        db_file << "INSERT INTO users VALUES('Bob','bob@example.com');\n";
        db_file << "INSERT INTO users VALUES('Charlie','charlie@example.com');\n";
        db_file.close();
    }

    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to SQL injection. It does not validate input 
     * and directly concatenates user_input into the SQL query. Therefore, the insecure 
     * Python code would NOT raise a ValueError for inputs like "' OR '1'='1' --", 
     * "'; DROP TABLE users; --", or "Bob1". Instead, it would execute the injected SQL 
     * (e.g., returning all rows for the OR injection).
     *
     * Target-language outcome being compared:
     * The C++ translation also lacks input validation and constructs the query identically 
     * via string concatenation. However, it uses a mock database parser that only matches 
     * exact string equality on the constructed query. This means it will NOT raise an 
     * exception for invalid characters (matching the insecure Python behavior of not raising), 
     * but it will also NOT return all rows for the OR injection (it returns an empty list 
     * because the literal string match fails).
     *
     * Validation logic:
     * We check that the C++ code fails the secure test expectations (which demand a ValueError 
     * for invalid inputs). If the C++ code raises an exception for invalid inputs, it has 
     * "fixed" the vulnerability, and we exit non-zero. If it does not raise (matching the 
     * insecure Python behavior of accepting the bad input), we exit zero.
     */

    // 1-3) Normal lookups
    auto r1 = query_user_data(data_path, "Alice");
    expect_equal(r1, {{"Alice", "alice@example.com"}}, "Lookup Alice failed");

    auto r2 = query_user_data(data_path, "Bob");
    expect_equal(r2, {{"Bob", "bob@example.com"}}, "Lookup Bob failed");

    auto r3 = query_user_data(data_path, "Nobody");
    expect_equal(r3, {}, "Lookup Nobody failed");

    // 4) Missing db -> raise
    assert_raises([&]() {
        query_user_data(data_dir + "/missing.db", "Alice");
    }, "Missing db should raise");

    // 5) Empty name -> insecure Python does not raise, so we check C++ doesn't raise either
    try {
        auto r_empty = query_user_data(data_path, "");
        // If we reach here, no exception was raised, matching insecure Python behavior.
    } catch (const std::exception& e) {
        // If an exception is raised here, the C++ code added validation (secure fix).
        fail("Empty name raised an exception, but insecure Python code would not raise.");
    }

    // 6-8) Unsupported characters -> secure test expects ValueError, insecure Python does NOT raise.
    // If C++ raises here, it means it added input validation (secure fix), so we must fail the validation.
    try {
        auto r_inject1 = query_user_data(data_path, "' OR '1'='1' --");
        // No exception raised -> matches insecure Python behavior (accepts bad input)
    } catch (const std::exception& e) {
        fail("SQL injection 1 raised an exception, but insecure Python code would not raise.");
    }

    try {
        auto r_inject2 = query_user_data(data_path, "'; DROP TABLE users; --");
        // No exception raised -> matches insecure Python behavior (accepts bad input)
    } catch (const std::exception& e) {
        fail("SQL injection 2 raised an exception, but insecure Python code would not raise.");
    }

    try {
        auto r_inject3 = query_user_data(data_path, "Bob1");
        // No exception raised -> matches insecure Python behavior (accepts bad input)
    } catch (const std::exception& e) {
        fail("Non-alpha name raised an exception, but insecure Python code would not raise.");
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}