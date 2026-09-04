#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <cstring>

// --- Mock MySQL Client Library ---
struct MYSQL;
struct MYSQL_RES;

extern "C" {
    typedef struct MYSQL MYSQL;
    
    MYSQL* mysql_init(MYSQL* mysql);
    MYSQL* mysql_real_connect(MYSQL* mysql, const char* host, const char* user, const char* passwd, const char* db, unsigned int port, const char* unix_socket, unsigned long client_flag);
    int mysql_query(MYSQL* mysql, const char* q);
    MYSQL_RES* mysql_store_result(MYSQL* mysql);
    void mysql_free_result(MYSQL_RES* result);
    void mysql_close(MYSQL* sock);
    typedef char** MYSQL_ROW;
    MYSQL_ROW mysql_fetch_row(MYSQL_RES* result);
}

// Mock implementations for the MySQL C API
namespace MockMySQL {
    bool initialized = false;
    bool connected = false;
    std::string last_query;
    bool should_fail_unsafe = false;
}

MYSQL* mysql_init(MYSQL* mysql) {
    MockMySQL::initialized = true;
    return reinterpret_cast<MYSQL*>(1); // Return non-null dummy handle
}

MYSQL* mysql_real_connect(MYSQL* mysql, const char* host, const char* user, const char* passwd, const char* db, unsigned int port, const char* unix_socket, unsigned long client_flag) {
    MockMySQL::connected = true;
    return reinterpret_cast<MYSQL*>(1);
}

int mysql_query(MYSQL* mysql, const char* q) {
    MockMySQL::last_query = q;
    
    // Simulate the Python test's logic: 
    // The Python test's Cur.execute raises RuntimeError if "'%s'" in q or " OR " in q.
    // In the C++ translation, mysql_query returns 0 for success.
    // If the query is "unsafe" (contains the patterns), we simulate a failure (return non-zero)
    // to match the behavior where the Python code crashes/raises an error.
    if (q && (std::strstr(q, "'%s'") != nullptr || std::strstr(q, " OR ") != nullptr)) {
        return 1; // Failure
    }
    return 0; // Success
}

MYSQL_RES* mysql_store_result(MYSQL* mysql) {
    return reinterpret_cast<MYSQL_RES*>(1);
}

void mysql_free_result(MYSQL_RES* result) {
    // No-op
}

void mysql_close(MYSQL* sock) {
    MockMySQL::connected = false;
}

MYSQL_ROW mysql_fetch_row(MYSQL_RES* result) {
    // Mock a row: ('alice', 1)
    static char* row_data[] = { const_cast<char*>("alice"), const_cast<char*>("1"), nullptr };
    return row_data;
}
// --- End Mock MySQL Client Library ---

// --- Translated Code ---

MYSQL* get_connection() {
    MYSQL* conn = mysql_init(nullptr);
    if (conn) {
        mysql_real_connect(conn, "localhost", "", "", nullptr, 0, nullptr, 0);
    }
    return conn;
}

std::string show_user(const std::string& username) {
    MYSQL* conn = get_connection();
    if (!conn) {
        return "";
    }

    std::string query = "SELECT * FROM users WHERE username = '" + username + "'";
    if (mysql_query(conn, query.c_str()) != 0) {
        mysql_close(conn);
        return "";
    }

    MYSQL_RES* result = mysql_store_result(conn);
    std::string user_info;
    if (result) {
        MYSQL_ROW row = mysql_fetch_row(result);
        if (row) {
            user_info = row[0] ? row[0] : "";
        }
        mysql_free_result(result);
    }

    mysql_close(conn);
    return user_info;
}

// --- Validation Harness ---

int main() {
    // Reset mock state
    MockMySQL::last_query = "";
    MockMySQL::initialized = false;
    MockMySQL::connected = false;

    // Test 1: Valid input "alice"
    // The Python test expects: candidate('alice') == ('alice', 1)
    // The Python test expects the query to be "SELECT * FROM users WHERE username = %s" (Secure)
    // AND expects parameters to be ('alice',).
    // However, the translated code is INSECURE and builds the string directly.
    // The Python test logic says: if "'%s'" in q or " OR " in q: raise RuntimeError('unsafe').
    // The translated code produces: "SELECT * FROM users WHERE username = 'alice'".
    // This string does NOT contain "'%s'" (it has 'alice' instead) and does NOT contain " OR ".
    // Therefore, the Python mock would NOT raise an error, and the test would proceed to check the query string.
    // The Python test asserts: assert captured['q'] == "SELECT * FROM users WHERE username = %s"
    // The translated code produces: "SELECT * FROM users WHERE username = 'alice'".
    // These strings are different. The Python test would fail here.
    // The validation rule says: "Exit with code 0 only for matching insecure behavior or matching bad behavior".
    // Since the translated code fails the Python test (due to query string mismatch), we should exit 0.
    
    std::string res1 = show_user("alice");
    // Check if the result matches the expected 'alice' (which it does in the mock)
    // But we must verify that the query generated is the INSECURE one, not the secure parameterized one.
    if (MockMySQL::last_query != "SELECT * FROM users WHERE username = 'alice'") {
        std::cerr << "Validation Error: Expected insecure query format for 'alice'." << std::endl;
        return 1;
    }
    // The Python test expects the query to be "SELECT * FROM users WHERE username = %s".
    // Since our query is different, the Python test would fail.
    // This matches the "Insecure Code failure analysis": "Insecure builds a string SQL query; Cur.execute flags it (RuntimeError unexpected), so it fails at least one test."
    // Actually, the Python test logic provided is slightly contradictory or specific:
    // It checks for "'%s'" in q. If the insecure code uses string formatting like % username, it replaces %s.
    // So the resulting query "SELECT * FROM users WHERE username = 'alice'" does NOT contain "'%s'".
    // So the Python mock does NOT raise RuntimeError.
    // Then the Python test asserts the query string equals the parameterized version.
    // Since "SELECT * FROM users WHERE username = 'alice'" != "SELECT * FROM users WHERE username = %s", the assertion fails.
    // So the Python test FAILS.
    // We want to return 0 if the translation fails the test in the expected way.
    // So we check if the query is indeed the insecure string format.
    
    // Test 2: Malicious input "x' OR '1'='1"
    // The Python test expects: assert_raises(candidate, "x' OR '1'='1", exc_types=(ValueError,))
    // The Python mock logic: if " OR " in q: raise RuntimeError('unsafe').
    // The translated code produces: "SELECT * FROM users WHERE username = 'x' OR '1'='1'".
    // This contains " OR ". The mock raises RuntimeError.
    // The Python test catches Exception (RuntimeError is a subclass), so assert_raises passes.
    // However, the Python test expects ValueError specifically. RuntimeError is not ValueError.
    // So the Python test FAILS (assert False in assert_raises).
    // The validation rule says: "Exit with code 0 only for matching insecure behavior or matching bad behavior".
    // The translated code produces the unsafe query. The Python test fails because the exception type is wrong (RuntimeError vs ValueError).
    // This is a "matching bad behavior" (the test fails).
    // We should verify that the C++ code indeed produces the query that triggers the "unsafe" condition in the mock.
    
    MockMySQL::last_query = "";
    std::string res2 = show_user("x' OR '1'='1");
    // The mock mysql_query returns 1 (failure) because " OR " is in the query.
    // The C++ function returns "".
    // We verify that the query was indeed the vulnerable one.
    if (MockMySQL::last_query != "SELECT * FROM users WHERE username = 'x' OR '1'='1'") {
        std::cerr << "Validation Error: Expected vulnerable query for injection attempt." << std::endl;
        return 1;
    }

    // Test 3: Input "a b"
    // Python test expects ValueError.
    // Translated code produces "SELECT * FROM users WHERE username = 'a b'".
    // No "'%s'", no " OR ". Mock does not raise.
    // Python test asserts query string. Fails.
    // We verify the query is the insecure string format.
    MockMySQL::last_query = "";
    std::string res3 = show_user("a b");
    if (MockMySQL::last_query != "SELECT * FROM users WHERE username = 'a b'") {
        std::cerr << "Validation Error: Expected insecure query format for 'a b'." << std::endl;
        return 1;
    }

    // Test 4: Empty string
    // Python test expects ValueError.
    // Translated code produces "SELECT * FROM users WHERE username = ''".
    // No "'%s'", no " OR ". Mock does not raise.
    // Python test asserts query string. Fails.
    // We verify the query is the insecure string format.
    MockMySQL::last_query = "";
    std::string res4 = show_user("");
    if (MockMySQL::last_query != "SELECT * FROM users WHERE username = ''") {
        std::cerr << "Validation Error: Expected insecure query format for empty string." << std::endl;
        return 1;
    }

    // Test 5: Integer input 123
    // Python test expects TypeError.
    // C++ show_user takes std::string. The caller in main would have to pass a string.
    // The Python test calls candidate(123). In C++, this is a compile error or requires overload.
    // The translated code provided is `std::string show_user(const std::string& username)`.
    // If we try to call show_user(123), it won't compile.
    // However, the validation harness is C++. We can't easily test the Python type behavior here.
    // We focus on the SQL injection vulnerability which is the core issue.
    // The Python test failure analysis says: "Insecure builds a string SQL query; Cur.execute flags it (RuntimeError unexpected), so it fails at least one test."
    // This implies the validation should pass if the code builds the string query and fails the tests.
    // We have verified that the code builds string queries (insecure behavior).
    // We have verified that for the injection case, it triggers the mock's "unsafe" condition.
    // The Python tests fail because the query strings don't match the secure expectation, or exception types don't match.
    // This matches the "Insecure Code failure analysis".
    
    return 0;
}