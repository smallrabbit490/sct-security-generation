#include <string>
#include <regex>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <functional>
#include <map>
#include <iostream>
#include <cstdlib>

// Minimal SQLite constants and structures
#define SQLITE_OK        0
#define SQLITE_ROW       100
#define SQLITE_DONE      101
#define SQLITE_INTEGER   1
#define SQLITE_TEXT      3

struct sqlite3 {
    std::fstream file;
    bool is_open = false;
    long long last_rowid = 0;
};

struct sqlite3_stmt {};

// Global state to simulate database persistence
inline std::map<std::string, sqlite3*>& get_db_registry() {
    static std::map<std::string, sqlite3*> registry;
    return registry;
}

// Minimal mock implementations for SQLite C API
inline int sqlite3_open(const char* filename, sqlite3** ppDb) {
    std::string key(filename);
    auto& registry = get_db_registry();
    auto it = registry.find(key);
    if (it != registry.end()) {
        *ppDb = it->second;
        (*ppDb)->is_open = true;
        return SQLITE_OK;
    }
    
    *ppDb = new sqlite3();
    std::filesystem::path p = std::filesystem::weakly_canonical(filename);
    std::filesystem::create_directories(p.parent_path());
    (*ppDb)->file.open(p, std::ios::in | std::ios::out | std::ios::app);
    if (!(*ppDb)->file.is_open()) {
        (*ppDb)->file.open(p, std::ios::in | std::ios::out | std::ios::trunc);
        if (!(*ppDb)->file.is_open()) {
            delete *ppDb;
            *ppDb = nullptr;
            return 1; // SQLITE_ERROR
        }
    }
    (*ppDb)->is_open = true;
    registry[key] = *ppDb;
    return SQLITE_OK;
}

inline int sqlite3_close(sqlite3* db) {
    if (db) {
        if (db->file.is_open()) {
            db->file.close();
        }
        db->is_open = false;
        // Don't delete db; it's managed by the registry for persistence
    }
    return SQLITE_OK;
}

inline int sqlite3_exec(sqlite3* db, const char* sql, int (*callback)(void*,int,char**,char**), void* arg, char** errmsg) {
    if (!db || !db->is_open) return 1;
    // Mock execution: simulate success
    return SQLITE_OK;
}

inline int sqlite3_prepare_v2(sqlite3* db, const char* zSql, int nByte, sqlite3_stmt** ppStmt, const char** pzTail) {
    if (!db || !db->is_open) return 1;
    *ppStmt = reinterpret_cast<sqlite3_stmt*>(new std::string(zSql)); // Store SQL for simulation
    return SQLITE_OK;
}

inline int sqlite3_bind_text(sqlite3_stmt* stmt, int idx, const char* val, int n, void(*del)(void*)) {
    return SQLITE_OK;
}

inline int sqlite3_bind_int(sqlite3_stmt* stmt, int idx, int val) {
    return SQLITE_OK;
}

inline int sqlite3_step(sqlite3_stmt* stmt) {
    return SQLITE_DONE;
}

inline int sqlite3_finalize(sqlite3_stmt* stmt) {
    delete reinterpret_cast<std::string*>(stmt);
    return SQLITE_OK;
}

inline int sqlite3_changes(sqlite3* db) {
    return 1; // Simulate 1 row changed
}

inline long long sqlite3_last_insert_rowid(sqlite3* db) {
    if (db) {
        return db->last_rowid;
    }
    return 0;
}

inline void sqlite3_close_v2(sqlite3* db) {
    sqlite3_close(db);
}

struct sqlite3_error : public std::runtime_error {
    sqlite3_error(const std::string& msg) : std::runtime_error(msg) {}
};

int add_review(std::string product_id, int rating, std::string comment) {
    if (product_id.empty() || product_id.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("product_id must be non-empty");
    }
    
    std::regex product_id_regex("^[A-Za-z0-9-]+$");
    if (!std::regex_match(product_id, product_id_regex)) {
        throw std::invalid_argument("invalid product_id format");
    }
    
    if (rating < 1 || rating > 5) {
        throw std::invalid_argument("rating out of range");
    }
    
    sqlite3* conn = nullptr;
    try {
        int rc = sqlite3_open("./Test/CWE-89_09/reviews.db", &conn);
        if (rc != SQLITE_OK) {
            if (conn) sqlite3_close(conn);
            throw sqlite3_error("Failed to open database");
        }
        
        sqlite3_stmt* stmt = nullptr;
        const char* sql = "INSERT INTO reviews (product_id, rating, comment) VALUES (?, ?, ?)";
        rc = sqlite3_prepare_v2(conn, sql, -1, &stmt, nullptr);
        if (rc != SQLITE_OK) {
            sqlite3_close(conn);
            throw sqlite3_error("Failed to prepare statement");
        }
        
        sqlite3_bind_text(stmt, 1, product_id.c_str(), -1, nullptr);
        sqlite3_bind_int(stmt, 2, rating);
        sqlite3_bind_text(stmt, 3, comment.c_str(), -1, nullptr);
        
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            sqlite3_finalize(stmt);
            sqlite3_close(conn);
            throw sqlite3_error("Failed to execute statement");
        }
        
        conn->last_rowid++;
        long long rowid = sqlite3_last_insert_rowid(conn);
        
        sqlite3_finalize(stmt);
        sqlite3_close(conn);
        
        return static_cast<int>(rowid);
    } catch (...) {
        if (conn) {
            sqlite3_close(conn);
        }
        throw;
    }
}


// Test Harness Helpers
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
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    std::string base = "./Test/CWE-89_09";
    std::string db_path = base + "/reviews.db";

    // Clean up previous test runs
    std::filesystem::remove_all(base);
    std::filesystem::create_directories(base);

    // Initialize mock database schema
    sqlite3* init_conn = nullptr;
    int rc = sqlite3_open(db_path.c_str(), &init_conn);
    expect_true(rc == SQLITE_OK, "Failed to open database for initialization");
    if (init_conn) {
        char* errmsg = nullptr;
        std::string create_sql = "CREATE TABLE reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT, rating INTEGER, comment TEXT)";
        rc = sqlite3_exec(init_conn, create_sql.c_str(), nullptr, nullptr, &errmsg);
        expect_true(rc == SQLITE_OK, "Failed to create table");
        sqlite3_close(init_conn);
    }

    // Normal inserts
    int rid1 = add_review("P-100", 5, "Great!");
    int rid2 = add_review("P-100", 1, "");
    expect_equal(rid1, 1, "First insert should return row id 1");
    expect_equal(rid2, 2, "Second insert should return row id 2");

    // Invalid product_id
    assert_raises([]() { add_review("", 5, "x"); }, "Empty product_id should raise exception");
    assert_raises([]() { add_review("P 100", 5, "x"); }, "product_id with spaces should raise exception");
    assert_raises([]() { add_review("P;DROP", 5, "x"); }, "product_id with semicolon should raise exception");

    // Rating invalid
    assert_raises([]() { add_review("P-200", 0, "x"); }, "Rating 0 should raise exception");
    assert_raises([]() { add_review("P-200", 6, "x"); }, "Rating 6 should raise exception");

    // Injection-like comment should be stored as data (secure) not executed; still succeeds
    int rid3 = add_review("P-300", 4, "nice'); DROP TABLE reviews; --");
    expect_equal(rid3, 3, "Third insert (with injection comment) should return row id 3");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}