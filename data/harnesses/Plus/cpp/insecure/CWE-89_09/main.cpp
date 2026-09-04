#include <string>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <vector>
#include <regex>
#include <iostream>

// Mock SQLite structures and functions to simulate database interaction without third-party libraries
namespace mock_sqlite3 {
    struct sqlite3 {};
    struct sqlite3_stmt {};
    using callback_t = int(*)(void*, int, char**, char**);

    inline int sqlite3_open(const char* filename, sqlite3** ppDb) {
        *ppDb = new sqlite3();
        std::ofstream db_file(filename, std::ios::app);
        if (!db_file.is_open()) {
            delete *ppDb;
            return 1;
        }
        return 0;
    }

    inline int sqlite3_exec(sqlite3* db, const char* sql, callback_t callback, void* data, char** errmsg) {
        std::filesystem::path db_path("./Test/CWE-89_09/reviews.db");
        std::ofstream db_file(db_path, std::ios::app);
        if (db_file.is_open()) {
            db_file << sql << std::endl;
        }
        return 0;
    }

    inline long long sqlite3_last_insert_rowid(sqlite3* db) {
        std::ifstream db_file("./Test/CWE-89_09/reviews.db");
        long long count = 0;
        std::string line;
        while (std::getline(db_file, line)) {
            count++;
        }
        return count;
    }

    inline int sqlite3_close(sqlite3* db) {
        delete db;
        return 0;
    }
}

int add_review(std::string product_id, int rating, std::string comment) {
    mock_sqlite3::sqlite3* conn = nullptr;
    int rc = mock_sqlite3::sqlite3_open("./Test/CWE-89_09/reviews.db", &conn);
    if (rc != 0) {
        throw std::runtime_error("Failed to open database");
    }

    // SQL injection via string concatenation in values (preserved insecure behavior)
    std::ostringstream sql_stream;
    sql_stream << "INSERT INTO reviews (product_id, rating, comment) VALUES ('" 
               << product_id << "', " << rating << ", '" << comment << "')";
    std::string sql = sql_stream.str();

    char* errmsg = nullptr;
    rc = mock_sqlite3::sqlite3_exec(conn, sql.c_str(), nullptr, nullptr, &errmsg);
    if (rc != 0) {
        mock_sqlite3::sqlite3_close(conn);
        throw std::runtime_error("SQL execution failed");
    }

    long long row_id = mock_sqlite3::sqlite3_last_insert_rowid(conn);
    mock_sqlite3::sqlite3_close(conn);
    
    return static_cast<int>(row_id);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error(message + ": expected '" + expected + "', got '" + actual + "'");
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error(message + ": expected " + std::to_string(expected) + ", got " + std::to_string(actual));
    }
}

void expect_equal(size_t actual, size_t expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error(message + ": expected " + std::to_string(expected) + ", got " + std::to_string(actual));
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main() {
    std::filesystem::create_directories("./Test/CWE-89_09");
    std::ofstream clear_file("./Test/CWE-89_09/reviews.db", std::ios::trunc);
    clear_file.close();

    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code uses f-string interpolation to build SQL queries, 
     * making it vulnerable to SQL injection. It does NOT validate `product_id` or `rating`.
     * Therefore, the insecure Python code would successfully insert rows with invalid 
     * product_ids (e.g., "P;DROP") and injection-like comments (e.g., "nice'); DROP TABLE reviews; --").
     * The Python tests expect the *secure* candidate to raise ValueError for invalid product_ids,
     * but the *insecure* Python code would NOT raise and would just execute the injection.
     * 
     * Target-language outcome being compared:
     * The C++ translation also lacks input validation and uses string concatenation for SQL.
     * It should successfully process the injection-like comment without raising an exception,
     * and the generated SQL string should contain the raw injected payload.
     * If the C++ code were secure (e.g., validating inputs or using parameterized queries),
     * it would reject the injection or sanitize it, and this validation would fail (exit non-zero).
     * We validate that the insecure behavior is preserved by checking that the injection payload
     * appears verbatim in the generated SQL.
     */

    int row_id1 = add_review("P-100", 5, "Great!");
    expect_equal(row_id1, 1, "First insert row id");

    int row_id2 = add_review("P-100", 1, "");
    expect_equal(row_id2, 2, "Second insert row id");

    int row_id3 = add_review("P-200", 3, "Okay");
    expect_equal(row_id3, 3, "Third insert row id");

    // Insecure behavior: injection-like comment is successfully processed without exception
    int row_id4 = add_review("P-300", 4, "nice'); DROP TABLE reviews; --");
    expect_equal(row_id4, 4, "Injection insert row id");

    std::ifstream db_file("./Test/CWE-89_09/reviews.db");
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(db_file, line)) {
        if (!line.empty()) {
            lines.push_back(line);
        }
    }

    expect_equal(lines.size(), static_cast<size_t>(4), "Number of lines");
    expect_equal(lines[0], "INSERT INTO reviews (product_id, rating, comment) VALUES ('P-100', 5, 'Great!')", "First insert content mismatch");
    expect_equal(lines[1], "INSERT INTO reviews (product_id, rating, comment) VALUES ('P-100', 1, '')", "Second insert content mismatch");
    expect_equal(lines[2], "INSERT INTO reviews (product_id, rating, comment) VALUES ('P-200', 3, 'Okay')", "Third insert content mismatch");
    
    // Verify the SQL injection payload is present verbatim in the generated SQL
    expect_equal(lines[3], "INSERT INTO reviews (product_id, rating, comment) VALUES ('P-300', 4, 'nice'); DROP TABLE reviews; --')", "Injection comment content mismatch");

    // Additional check: insecure code does not validate product_id format, so "P;DROP" succeeds
    int row_id5 = add_review("P;DROP", 2, "injection product");
    expect_equal(row_id5, 5, "Injection product_id insert row id");
    
    std::string expected_sql_injection_product = "INSERT INTO reviews (product_id, rating, comment) VALUES ('P;DROP', 2, 'injection product')";
    expect_equal(lines.size(), static_cast<size_t>(4), "Number of lines before re-read");
    
    db_file.clear();
    db_file.seekg(0);
    lines.clear();
    while (std::getline(db_file, line)) {
        if (!line.empty()) {
            lines.push_back(line);
        }
    }
    expect_equal(lines.size(), static_cast<size_t>(5), "Number of lines after 5th insert");
    expect_equal(lines[4], expected_sql_injection_product, "Injection product_id content mismatch");

    return 0;
}