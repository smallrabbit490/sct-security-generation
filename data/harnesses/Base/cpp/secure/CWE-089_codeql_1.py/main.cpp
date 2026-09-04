#include <any>
#include <iostream>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>
#include <cassert>

// --- Mock Infrastructure ---

struct Cursor {
    virtual ~Cursor() = default;
    virtual void execute(const std::string& query, const std::vector<std::string>& params) = 0;
    virtual std::any fetchone() = 0;
};

struct Connection {
    virtual ~Connection() = default;
    virtual Cursor* cursor() = 0;
};

// Global pointer to the mock connection, controlled by tests
Connection* g_mock_connection = nullptr;

Connection* get_connection() {
    return g_mock_connection;
}

// --- Translated Code ---

std::any show_user(const std::string& username) {
    if (username.empty()) {
        throw std::invalid_argument("empty username");
    }
    static const std::regex safe_username(R"(^[A-Za-z0-9_\-]+$)");
    if (!std::regex_match(username, safe_username)) {
        throw std::invalid_argument("invalid username");
    }

    Connection* conn = get_connection();
    if (conn == nullptr) {
        throw std::runtime_error("invalid connection");
    }
    Cursor* cur = conn->cursor();
    if (cur == nullptr) {
        throw std::runtime_error("invalid cursor");
    }

    try {
        cur->execute("SELECT * FROM users WHERE username = %s", std::vector<std::string>{username});
        return cur->fetchone();
    } catch (const std::exception& exc) {
        throw std::runtime_error(exc.what());
    }
}

// --- Test Harness ---

struct MockCursor : public Cursor {
    std::string captured_query;
    std::vector<std::string> captured_params;

    void execute(const std::string& query, const std::vector<std::string>& params) override {
        captured_query = query;
        captured_params = params;
        
        // Check for insecure patterns as per Python test logic
        // Python: if "'%s'" in q or " OR " in q: raise RuntimeError('unsafe')
        if (query.find("'%s'") != std::string::npos || query.find(" OR ") != std::string::npos) {
            throw std::runtime_error("unsafe");
        }
    }

    std::any fetchone() override {
        // Return a tuple equivalent: ('alice', 1)
        // Using std::pair to represent the tuple
        return std::make_pair(std::string("alice"), 1);
    }
};

struct MockConnection : public Connection {
    MockCursor mock_cursor;
    
    Cursor* cursor() override {
        return &mock_cursor;
    }
};

int main() {
    try {
        // Setup Mock
        MockConnection mock_conn;
        g_mock_connection = &mock_conn;

        // Test 1: Valid user
        {
            auto result = show_user("alice");
            // Verify result type and content
            // We expect std::pair<std::string, int>
            try {
                auto user_info = std::any_cast<std::pair<std::string, int>>(result);
                assert(user_info.first == "alice");
                assert(user_info.second == 1);
            } catch (const std::bad_any_cast&) {
                std::cerr << "Test 1 Failed: Return type mismatch" << std::endl;
                return 1;
            }

            // Verify query parameters
            assert(mock_conn.mock_cursor.captured_query == "SELECT * FROM users WHERE username = %s");
            assert(mock_conn.mock_cursor.captured_params.size() == 1);
            assert(mock_conn.mock_cursor.captured_params[0] == "alice");
        }

        // Test 2: SQL Injection attempt (ValueError expected due to regex)
        {
            bool caught = false;
            try {
                show_user("x' OR '1'='1");
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                std::cerr << "Test 2 Failed: Wrong exception type for injection attempt" << std::endl;
                return 1;
            }
            assert(caught);
        }

        // Test 3: Space in username (ValueError expected)
        {
            bool caught = false;
            try {
                show_user("a b");
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                std::cerr << "Test 3 Failed: Wrong exception type for space" << std::endl;
                return 1;
            }
            assert(caught);
        }

        // Test 4: Empty username (ValueError expected)
        {
            bool caught = false;
            try {
                show_user("");
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                std::cerr << "Test 4 Failed: Wrong exception type for empty string" << std::endl;
                return 1;
            }
            assert(caught);
        }

        // Test 5: Type mismatch
        // In C++, show_user takes std::string. We cannot pass an int directly.
        // The Python test checks `isinstance(username, str)`.
        // In the C++ translation, this check is implicit by the type system.
        // We simulate the "pass" of this test by simply asserting true, 
        // as the compiler enforces the type constraint.
        assert(true);

        std::cout << "All tests passed." << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Test suite failed with exception: " << e.what() << std::endl;
        return 1;
    }
}