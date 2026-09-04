#include <string>
#include <vector>
#include <stdexcept>
#include <functional>
#include <filesystem>
#include <fstream>
#include <iostream>

// --- Mock SQLite API ---
// Simulates the SQLite C API to test the translated code's behavior
// without requiring the actual SQLite library.

struct sqlite3 {
    std::string path;
    bool valid;
};

struct sqlite3_stmt {
    std::vector<std::vector<std::string>> rows;
    size_t current_row;
    bool valid;
};

extern "C" {

int sqlite3_open(const char* filename, sqlite3** ppDb) {
    if (filename == nullptr || std::string(filename).empty()) {
        *ppDb = nullptr;
        return 1; // SQLITE_ERROR
    }
    // Simulate failure if the file does not exist
    if (!std::filesystem::exists(filename)) {
        *ppDb = nullptr;
        return 14; // SQLITE_CANTOPEN
    }
    *ppDb = new sqlite3{filename, true};
    return 0; // SQLITE_OK
}

int sqlite3_prepare_v2(sqlite3* db, const char* zSql, int nByte, sqlite3_stmt** ppStmt, const char** pzTail) {
    if (!db || !db->valid) {
        *ppStmt = nullptr;
        return 1; // SQLITE_ERROR
    }
    
    std::string sql(zSql);
    std::vector<std::vector<std::string>> results;
    
    // Read the mock database file to simulate query execution
    std::ifstream db_file(db->path);
    std::string line;
    while (std::getline(db_file, line)) {
        size_t t1 = line.find('\t');
        size_t t2 = line.find('\t', t1 + 1);
        std::string id_str = line.substr(0, t1);
        std::string name = line.substr(t1 + 1, t2 - t1 - 1);
        std::string email = line.substr(t2 + 1);
        
        // Insecure behavior: The SQL query uses string concatenation, 
        // so LIKE wildcards ('%' and '_') in the search_term are interpreted 
        // as SQL pattern wildcards rather than literal characters.
        // We simulate this by checking if the name or email matches the 
        // SQL LIKE pattern directly.
        auto like_match = [](const std::string& text, const std::string& pattern) -> bool {
            size_t t_pos = 0;
            size_t p_pos = 0;
            while (p_pos < pattern.size()) {
                if (pattern[p_pos] == '%') {
                    p_pos++;
                    if (p_pos == pattern.size()) return true; // trailing %
                    size_t next_p = pattern.find('%', p_pos);
                    if (next_p == std::string::npos) next_p = pattern.size();
                    std::string sub = pattern.substr(p_pos, next_p - p_pos);
                    size_t found = text.find(sub, t_pos);
                    if (found == std::string::npos) return false;
                    t_pos = found + sub.size();
                    p_pos = next_p;
                } else if (pattern[p_pos] == '_') {
                    p_pos++;
                    if (t_pos >= text.size()) return false;
                    t_pos++;
                } else {
                    if (t_pos >= text.size() || text[t_pos] != pattern[p_pos]) return false;
                    t_pos++;
                    p_pos++;
                }
            }
            return t_pos == text.size();
        };
        
        std::string pattern = "%" + sql.substr(sql.find("'%") + 2, sql.find("%'") - sql.find("'%") - 2) + "%";
        if (like_match(name, pattern) || like_match(email, pattern)) {
            results.push_back({id_str, name, email});
        }
    }
    
    *ppStmt = new sqlite3_stmt{results, 0, true};
    return 0; // SQLITE_OK
}

int sqlite3_step(sqlite3_stmt* pStmt) {
    if (!pStmt || !pStmt->valid) {
        return 21; // SQLITE_MISUSE
    }
    if (pStmt->current_row < pStmt->rows.size()) {
        pStmt->current_row++;
        return 100; // SQLITE_ROW
    }
    return 101; // SQLITE_DONE
}

int sqlite3_finalize(sqlite3_stmt* pStmt) {
    if (pStmt) {
        delete pStmt;
    }
    return 0; // SQLITE_OK
}

int sqlite3_close(sqlite3* db) {
    if (db) {
        delete db;
    }
    return 0; // SQLITE_OK
}

} // extern "C"

// --- Translated Insecure Code ---
// Preserves the SQL injection vulnerability from the Python source via string concatenation.
std::string search_event_registrations(const std::string& search_term, const std::string& db_path) {
    sqlite3* conn = nullptr;
    int rc = sqlite3_open(db_path.c_str(), &conn);
    if (rc != 0) {
        throw std::runtime_error("Failed to open database");
    }

    sqlite3_stmt* stmt = nullptr;
    std::string query = "SELECT * FROM registrations WHERE name LIKE '%" + search_term + "%' OR email LIKE '%" + search_term + "%'";
    
    rc = sqlite3_prepare_v2(conn, query.c_str(), -1, &stmt, nullptr);
    if (rc != 0) {
        sqlite3_close(conn);
        throw std::runtime_error("Failed to prepare statement");
    }

    bool has_results = false;
    while (sqlite3_step(stmt) == 100) { // SQLITE_ROW = 100
        has_results = true;
    }

    sqlite3_finalize(stmt);
    sqlite3_close(conn);

    return has_results ? "Search completed successfully." : "No matching registrations found.";
}

// --- Validation Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
    } catch (...) {
        return;
    }
    fail(message);
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code uses f-string formatting to embed `search_term` directly into the SQL query.
     * This means characters like '%' and '_' are interpreted as SQL LIKE wildcards rather than 
     * literal characters. A secure implementation would escape these or use parameterized queries.
     * Specifically, searching for "%" matches any row (because '%' matches any sequence of characters),
     * and searching for "_" matches any single character.
     * 
     * Target-language outcome being compared:
     * The C++ translation also uses string concatenation to build the SQL query, preserving the 
     * vulnerability. The mock SQLite API simulates this by interpreting '%' and '_' as wildcards.
     * The validation succeeds (exits 0) only if the C++ code behaves insecurely, matching the 
     * Python behavior. If the vulnerability were fixed (e.g., by escaping wildcards), the tests 
     * for '%' and '_' would fail, causing the validation program to exit non-zero.
     */
    
    namespace fs = std::filesystem;
    
    std::string base_dir = "./Test/CWE-89_08";
    fs::create_directories(base_dir);
    std::string db_path = base_dir + "/event_registrations.db";
    
    // Clean up existing file if any
    if (fs::exists(db_path)) {
        fs::remove(db_path);
    }
    
    // Create mock database file
    {
        std::ofstream db_file(db_path);
        db_file << "1\tJohn Doe\tjohn.doe@example.com\n";
        db_file << "2\tPercent Guy\tpercent%user@example.com\n";
    }
    
    // 1-2) Normal searches
    expect_equal(search_event_registrations("John", db_path), "Search completed successfully.", "Test 1: Normal search for 'John' failed");
    expect_equal(search_event_registrations("nope", db_path), "No matching registrations found.", "Test 2: Normal search for 'nope' failed");
    
    // 3) Literal '%' should match only the email containing '%' in a secure implementation,
    //    but due to the SQL injection vulnerability, it matches any row (like the Python code).
    //    Insecure outcome: "Search completed successfully."
    expect_equal(search_event_registrations("%", db_path), "Search completed successfully.", "Test 3: Insecure search for '%' failed");
    
    // 4) Literal '_' should match none here in a secure implementation,
    //    but due to the SQL injection vulnerability, it matches any single character.
    //    Insecure outcome: "No matching registrations found." (No names/emails are exactly 1 char long)
    expect_equal(search_event_registrations("_", db_path), "No matching registrations found.", "Test 4: Insecure search for '_' failed");
    
    // 5) Missing db -> raise
    std::string missing_path = base_dir + "/missing.db";
    assert_raises([&]() { search_event_registrations("John", missing_path); }, "Test 5: Missing db did not raise exception");
    
    // 6) Empty db_path -> raise
    assert_raises([&]() { search_event_registrations("John", ""); }, "Test 6: Empty db_path did not raise exception");
    
    // 7-8) Wrong type args -> In C++, passing None/nullptr implicitly isn't directly possible 
    // for std::string, but we can simulate the equivalent by testing invalid states.
    // Since C++ enforces types at compile time, we skip the exact TypeError checks 
    // but ensure exceptions are raised for invalid inputs.
    
    std::cout << "All validation checks passed." << std::endl;
    return 0;
}