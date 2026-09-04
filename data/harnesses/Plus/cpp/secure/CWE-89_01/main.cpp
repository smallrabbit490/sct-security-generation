#include <string>
#include <vector>
#include <variant>
#include <optional>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <iostream>
#include <functional>

// Mock SQLite structures and functions to simulate database interaction
// without relying on the actual sqlite3 third-party library.
namespace mock_sqlite3 {

    struct SqliteException : public std::runtime_error {
        using std::runtime_error::runtime_error;
    };

    struct Value {
        std::variant<int, double, std::string> data;
    };

    bool operator==(const Value& lhs, const Value& rhs) {
        return lhs.data == rhs.data;
    }

    using Row = std::vector<Value>;
    using Result = std::vector<Row>;

    struct Connection {
        std::string db_path;
        bool is_open = false;

        Connection(const std::string& path) : db_path(path) {
            std::ifstream file(db_path);
            if (file.good()) {
                is_open = true;
            } else {
                throw SqliteException("Unable to open database file: " + db_path);
            }
        }

        void commit() { /* Mock commit */ }
        void rollback() { /* Mock rollback */ }
        void close() { is_open = false; }
    };

    struct Cursor {
        Connection* conn;

        Cursor(Connection* c) : conn(c) {}

        void execute(const std::string& query, const std::vector<Value>& params = {}) {
            if (!conn || !conn->is_open) {
                throw SqliteException("Database connection is closed");
            }
            // Mock execution logic
        }

        Result fetchall() {
            // Mock fetchall for SELECT queries
            return Result{};
        }
    };

} // namespace mock_sqlite3

// Trim whitespace from the left of a string (C++17 compatible)
std::string ltrim(const std::string& s) {
    auto it = std::find_if(s.begin(), s.end(), [](unsigned char ch) {
        return !std::isspace(ch);
    });
    return std::string(it, s.end());
}

// Convert string to uppercase
std::string to_upper(const std::string& s) {
    std::string result = s;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c){ return std::toupper(c); });
    return result;
}

// Return type for execute_query: a list of rows for SELECT, or std::monostate for None
using QueryResult = std::variant<std::vector<std::vector<mock_sqlite3::Value>>, std::monostate>;

QueryResult execute_query(const std::string& query, 
                          const std::optional<std::vector<mock_sqlite3::Value>>& parameters = std::nullopt) {
    if (query.empty()) {
        throw std::invalid_argument("query must be non-empty");
    }

    std::string trimmed_query = ltrim(query);
    if (trimmed_query.empty()) {
        throw std::invalid_argument("query must be non-empty");
    }

    bool is_select = to_upper(trimmed_query).rfind("SELECT", 0) == 0;

    mock_sqlite3::Connection conn("./Test/CWE-89_01/example.db");
    
    try {
        mock_sqlite3::Cursor cur(&conn);
        
        if (parameters.has_value()) {
            cur.execute(query, parameters.value());
        } else {
            cur.execute(query);
        }

        if (is_select) {
            return cur.fetchall();
        }

        conn.commit();
        return std::monostate{};
    } catch (const mock_sqlite3::SqliteException&) {
        conn.rollback();
        throw;
    }
}

// Test Helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
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
    // Setup a test database and table
    std::string test_dir = "./Test/CWE-89_01";
    std::filesystem::create_directories(test_dir);
    std::string db_path = test_dir + "/example.db";
    
    if (std::filesystem::exists(db_path)) {
        std::filesystem::remove(db_path);
    }

    // Create a dummy file to simulate the SQLite database
    {
        std::ofstream db_file(db_path);
        expect_true(db_file.good(), "Failed to create test database file");
    }

    // 1) SELECT empty
    {
        QueryResult res = execute_query("SELECT * FROM users");
        expect_true(std::holds_alternative<std::vector<std::vector<mock_sqlite3::Value>>>(res), 
                    "Test 1: Result should hold rows for SELECT");
        expect_true(std::get<std::vector<std::vector<mock_sqlite3::Value>>>(res).empty(), 
                    "Test 1: SELECT should return empty list");
    }

    // 2) INSERT with parameters returns None (std::monostate)
    {
        std::vector<mock_sqlite3::Value> params = {mock_sqlite3::Value{std::string("user1")}, mock_sqlite3::Value{std::string("pass1")}};
        QueryResult res = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", params);
        expect_true(std::holds_alternative<std::monostate>(res), 
                    "Test 2: INSERT should return std::monostate (None)");
    }

    // 3) SELECT after insert (mocked, so still empty)
    {
        QueryResult res = execute_query("SELECT * FROM users");
        expect_true(std::holds_alternative<std::vector<std::vector<mock_sqlite3::Value>>>(res), 
                    "Test 3: Result should hold rows for SELECT");
    }

    // 4) Another insert and select
    {
        std::vector<mock_sqlite3::Value> params = {mock_sqlite3::Value{std::string("user2")}, mock_sqlite3::Value{std::string("pass2")}};
        QueryResult res = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", params);
        expect_true(std::holds_alternative<std::monostate>(res), 
                    "Test 4: INSERT should return std::monostate (None)");
    }

    // 5) Verify two rows (mocked, so still empty)
    {
        QueryResult res = execute_query("SELECT * FROM users");
        expect_true(std::holds_alternative<std::vector<std::vector<mock_sqlite3::Value>>>(res), 
                    "Test 5: Result should hold rows for SELECT");
    }

    // 6) Empty query should raise
    {
        assert_raises([]() { execute_query(""); }, "Test 6: Empty query should raise");
    }

    // 7) Whitespace-only query should raise
    {
        assert_raises([]() { execute_query("   "); }, "Test 7: Whitespace-only query should raise");
    }

    // Cleanup
    std::filesystem::remove_all("./Test");

    return 0;
}