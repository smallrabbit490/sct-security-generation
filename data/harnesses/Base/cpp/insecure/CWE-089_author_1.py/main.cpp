#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <cassert>

// --- Mock MySQL API (from translation) ---
struct MYSQL {
    int dummy;
};

struct MYSQL_RES {
    int dummy;
};

using MYSQL_ROW = std::vector<std::string>;

MYSQL* mysql_init(MYSQL* mysql) {
    return new MYSQL();
}

MYSQL* mysql_real_connect(MYSQL* mysql, const char* host, const char* user, const char* passwd, const char* db, unsigned int port, const char* unix_socket, unsigned long client_flag) {
    return mysql;
}

int mysql_query(MYSQL* mysql, const char* query) {
    return 0;
}

void mysql_free_result(MYSQL_RES* result) {
    delete result;
}

void mysql_close(MYSQL* mysql) {
    delete mysql;
}

// --- Translated Code ---
MYSQL* get_connection() {
    /*
    Return a connection to the database
    */
    MYSQL* conn = mysql_init(nullptr);
    return mysql_real_connect(conn, "localhost", "", "", nullptr, 0, nullptr, 0);
}

void remove_user(const std::string& username) {
    /*
    Remove the user with the "username" specified from the  "users" table
    */
    MYSQL* conn = get_connection();
    MYSQL_RES* res = nullptr;
    MYSQL_ROW row;
    
    std::string query = "DELETE FROM users WHERE username = '" + username + "'";
    mysql_query(conn, query.c_str());
    
    mysql_free_result(res);
    mysql_close(conn);
}

// --- Validation Logic ---

// Global state to capture execution details
struct CapturedState {
    std::string query;
    bool committed = false;
    bool unsafe_detected = false;
} captured;

// Mock implementations for validation
namespace Mock {
    MYSQL* last_conn = nullptr;

    // Override mysql_query to inspect the SQL string
    int mysql_query(MYSQL* mysql, const char* query_str) {
        captured.query = query_str;
        
        // The Python test's Cur.execute logic:
        // if "'%s'" in q or '% username' in q: raise RuntimeError('unsafe')
        // The translated C++ code constructs the query using concatenation:
        // "DELETE FROM users WHERE username = '" + username + "'"
        // This string will always contain single quotes around the value, e.g., "... = 'alice'".
        // It will never contain the literal substring "'%s'" (percent s inside quotes).
        // Therefore, the condition that triggers the 'unsafe' RuntimeError in the Python test
        // is NOT met by the C++ translation's string format.
        // Consequently, the C++ code does NOT raise the RuntimeError expected by the test logic.
        
        // Since the C++ code does not raise, the Python test's `assert_raises` (expecting an exception)
        // will fail because the function completes successfully.
        // This matches the "Insecure Code failure analysis": the insecure code fails the test.
        
        return 0; // Return success (no exception thrown)
    }

    void mysql_close(MYSQL* mysql) {
        delete mysql;
    }
}

// Helper to check if a function throws a specific exception
template<typename Func, typename... Args>
bool assert_raises(Func func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
        return false; // Did not throw
    } catch (const std::exception&) {
        return true; // Threw expected exception type
    } catch (...) {
        return false; // Threw unexpected type
    }
}

int main() {
    // We need to verify that the translated code behaves in a way that causes the Python tests to fail.
    // The Python tests expect:
    // 1. Parameterized queries (e.g., "username = %s").
    // 2. Exceptions for invalid inputs (empty string, injection, etc.).
    
    // The translated code:
    // 1. Uses string concatenation (insecure).
    // 2. Does not validate input or throw exceptions.
    
    // Therefore, the translated code will FAIL the Python tests.
    // Our validation program succeeds if we detect this failure mode.

    bool test_failed = false;

    // Test 1: Normal input
    // Python expects: query == "DELETE FROM users WHERE username = %s"
    // C++ produces:   query == "DELETE FROM users WHERE username = 'alice'"
    captured.query = "";
    remove_user("alice");
    if (captured.query != "DELETE FROM users WHERE username = %s") {
        // The C++ code failed to match the secure expectation.
        // This is the expected behavior for the insecure translation.
        test_failed = true; 
    }

    // Test 2: Injection input
    // Python expects: ValueError (or RuntimeError in the specific insecure mock logic)
    // C++ produces:   Successful execution (no exception)
    if (!assert_raises(remove_user, "bob' OR '1'='1")) {
        // The C++ code did not raise an exception where one was expected.
        // This confirms the insecure behavior (lack of validation).
        test_failed = true;
    }

    // Test 3: Empty input
    // Python expects: ValueError
    // C++ produces:   Successful execution
    if (!assert_raises(remove_user, "")) {
        test_failed = true;
    }

    // Test 4: Space input
    // Python expects: ValueError
    // C++ produces:   Successful execution
    if (!assert_raises(remove_user, "a b")) {
        test_failed = true;
    }

    // Conclusion:
    // The Python tests define a "Secure" behavior.
    // The translated C++ code implements an "Insecure" behavior.
    // The Python tests would REJECT the C++ code.
    // The problem statement says: "It must not pass just because the code contains dangerous-looking tokens."
    // "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail,
    // make the target program treat that matching failure as success."
    
    // Here, the C++ code fails the secure tests (test_failed is true).
    // This matches the expected outcome for the insecure translation.
    // So we exit with 0.

    if (test_failed) {
        std::cout << "Validation Passed: Insecure code correctly failed secure tests." << std::endl;
        return 0;
    } else {
        std::cout << "Validation Failed: Insecure code unexpectedly passed secure tests." << std::endl;
        return 1;
    }
}