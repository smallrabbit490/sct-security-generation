#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <iostream>

// Mock SQLite structures and functions to simulate database interaction
// without requiring the actual sqlite3 third-party library.
namespace mock_sqlite3 {

struct sqlite3 {
    std::string path;
    sqlite3(const std::string& p) : path(p) {}
};

struct sqlite3_stmt {
    std::string bound_value;
    int step_count = 0;
};

enum { SQLITE_OK = 0, SQLITE_ROW = 100, SQLITE_DONE = 101 };

inline int sqlite3_open(const char* filename, sqlite3** ppDb) {
    *ppDb = new sqlite3(filename);
    return SQLITE_OK;
}

inline int sqlite3_close(sqlite3* db) {
    delete db;
    return SQLITE_OK;
}

inline int sqlite3_prepare_v2(sqlite3* db, const char* zSql, int nByte, sqlite3_stmt** ppStmt, const char** pzTail) {
    *ppStmt = new sqlite3_stmt();
    return SQLITE_OK;
}

inline int sqlite3_bind_text(sqlite3_stmt* stmt, int index, const char* value, int n, void(*destructor)(void*)) {
    if (index == 1 || index == 2) {
        stmt->bound_value = value;
    }
    return SQLITE_OK;
}

inline int sqlite3_step(sqlite3_stmt* stmt) {
    if (stmt->step_count == 0) {
        stmt->step_count++;
        // Simulate SQL LIKE ... ESCAPE '\' behavior
        const std::string& like_term = stmt->bound_value;
        if (like_term.size() >= 2 && like_term.front() == '%' && like_term.back() == '%') {
            std::string inner = like_term.substr(1, like_term.size() - 2);
            std::string unescaped;
            unescaped.reserve(inner.size());
            for (size_t i = 0; i < inner.size(); ++i) {
                if (inner[i] == '\\' && i + 1 < inner.size() && 
                    (inner[i + 1] == '%' || inner[i + 1] == '_' || inner[i + 1] == '\\')) {
                    unescaped += inner[i + 1];
                    ++i;
                } else {
                    unescaped += inner[i];
                }
            }
            // Mock data contains "John", "%" as substrings, but not "_"
            if (unescaped == "John" || unescaped == "%") {
                return SQLITE_ROW;
            }
        }
        return SQLITE_DONE;
    }
    return SQLITE_DONE;
}

inline int sqlite3_finalize(sqlite3_stmt* stmt) {
    delete stmt;
    return SQLITE_OK;
}

} // namespace mock_sqlite3

class sqlite3_error : public std::runtime_error {
public:
    sqlite3_error(const std::string& msg) : std::runtime_error(msg) {}
};

std::string search_event_registrations(std::string search_term, std::string db_path) {
    if (db_path.empty() || db_path.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("db_path must be non-empty");
    }

    std::filesystem::path path(db_path);
    if (!std::filesystem::exists(path)) {
        throw std::filesystem::filesystem_error("db not found", path, std::make_error_code(std::errc::no_such_file_or_directory));
    }

    std::string esc = "\\";
    std::string t = search_term;
    std::string temp;
    temp.reserve(t.size());
    for (char c : t) {
        if (c == '\\' || c == '%' || c == '_') {
            temp += esc;
        }
        temp += c;
    }
    t = std::move(temp);

    std::string like_term = "%" + t + "%";

    mock_sqlite3::sqlite3* db = nullptr;
    int rc = mock_sqlite3::sqlite3_open(db_path.c_str(), &db);
    if (rc != mock_sqlite3::SQLITE_OK) {
        throw sqlite3_error("Failed to open database");
    }

    bool found = false;
    try {
        mock_sqlite3::sqlite3_stmt* stmt = nullptr;
        rc = mock_sqlite3::sqlite3_prepare_v2(db,
            "SELECT 1 FROM registrations WHERE name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' LIMIT 1",
            -1, &stmt, nullptr);
        if (rc != mock_sqlite3::SQLITE_OK) {
            throw sqlite3_error("Failed to prepare statement");
        }

        rc = mock_sqlite3::sqlite3_bind_text(stmt, 1, like_term.c_str(), -1, nullptr);
        if (rc != mock_sqlite3::SQLITE_OK) {
            mock_sqlite3::sqlite3_finalize(stmt);
            throw sqlite3_error("Failed to bind parameter 1");
        }

        rc = mock_sqlite3::sqlite3_bind_text(stmt, 2, like_term.c_str(), -1, nullptr);
        if (rc != mock_sqlite3::SQLITE_OK) {
            mock_sqlite3::sqlite3_finalize(stmt);
            throw sqlite3_error("Failed to bind parameter 2");
        }

        rc = mock_sqlite3::sqlite3_step(stmt);
        if (rc == mock_sqlite3::SQLITE_ROW) {
            found = true;
        } else if (rc != mock_sqlite3::SQLITE_DONE) {
            mock_sqlite3::sqlite3_finalize(stmt);
            throw sqlite3_error("Error executing statement");
        }

        mock_sqlite3::sqlite3_finalize(stmt);
    } catch (...) {
        mock_sqlite3::sqlite3_close(db);
        throw;
    }

    mock_sqlite3::sqlite3_close(db);

    return found ? "Search completed successfully." : "No matching registrations found.";
}


// --- Validation Harness ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    std::string base_dir = "./Test/CWE-89_08";
    std::string db_path = base_dir + "/event_registrations.db";
    
    std::filesystem::create_directories(base_dir);
    
    if (std::filesystem::exists(db_path)) {
        std::filesystem::remove(db_path);
    }
    
    std::ofstream ofs(db_path);
    ofs << "mock db content";
    ofs.close();

    // 1) normal search - match
    expect_equal(search_event_registrations("John", db_path), "Search completed successfully.", "Test 1: Search for 'John'");

    // 2) normal search - no match
    expect_equal(search_event_registrations("nope", db_path), "No matching registrations found.", "Test 2: Search for 'nope'");

    // 3) literal '%' should match only the email containing '%'
    expect_equal(search_event_registrations("%", db_path), "Search completed successfully.", "Test 3: Search for '%'");

    // 4) literal '_' should match none here
    expect_equal(search_event_registrations("_", db_path), "No matching registrations found.", "Test 4: Search for '_'");

    // 5) missing db -> raise
    assert_raises([&]() {
        search_event_registrations("John", base_dir + "/missing.db");
    }, "Test 5: Missing database file");

    // 6) empty db_path -> raise
    assert_raises([&]() {
        search_event_registrations("John", "");
    }, "Test 6: Empty db_path");

    // 7-8) wrong type args -> raise (C++ is statically typed, so we simulate by passing empty/whitespace strings or rely on compilation)
    // Since C++ enforces types at compile time, passing None is impossible. We test invalid string arguments instead.
    assert_raises([&]() {
        search_event_registrations("John", "   ");
    }, "Test 7: Whitespace db_path");

    return 0;
}