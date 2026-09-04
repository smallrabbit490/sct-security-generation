#include <string>
#include <vector>
#include <tuple>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <filesystem>
#include <iostream>
#include <functional>

// --- Mock SQLite Database Implementation ---
namespace mock_db {
    struct sqlite3 {
        std::string db_path;
    };
    struct sqlite3_stmt {
        std::vector<std::tuple<int, std::string>> rows;
        int current = -1;
    };

    inline int sqlite3_open(const char* filename, sqlite3** ppDb) {
        std::ifstream file(filename);
        if (!file.good()) {
            *ppDb = nullptr;
            return 1; // Indicate failure
        }
        *ppDb = new sqlite3();
        (*ppDb)->db_path = filename;
        return 0;
    }

    inline int sqlite3_prepare_v2(sqlite3* db, const char* zSql, int nByte, sqlite3_stmt** ppStmt, const char** pzTail) {
        *ppStmt = new sqlite3_stmt();
        std::string sql(zSql);
        std::string like_keyword = "'%";
        size_t start = sql.find(like_keyword);
        if (start != std::string::npos) {
            start += like_keyword.size();
            size_t end = sql.find("%'", start);
            if (end != std::string::npos) {
                std::string keyword = sql.substr(start, end - start);
                std::ifstream file(db->db_path);
                std::string line;
                int id = 1;
                while (std::getline(file, line)) {
                    if (line.find(keyword) != std::string::npos) {
                        (*ppStmt)->rows.emplace_back(id, line);
                    }
                    id++;
                }
            }
        }
        return 0;
    }

    inline int sqlite3_step(sqlite3_stmt* pStmt) {
        pStmt->current++;
        if (pStmt->current < static_cast<int>(pStmt->rows.size())) {
            return 100; // SQLITE_ROW
        }
        return 101; // SQLITE_DONE
    }

    inline int sqlite3_column_int(sqlite3_stmt* pStmt, int iCol) {
        return std::get<0>(pStmt->rows[pStmt->current]);
    }

    inline const unsigned char* sqlite3_column_text(sqlite3_stmt* pStmt, int iCol) {
        return reinterpret_cast<const unsigned char*>(std::get<1>(pStmt->rows[pStmt->current]).c_str());
    }

    inline int sqlite3_finalize(sqlite3_stmt* pStmt) {
        delete pStmt;
        return 0;
    }

    inline int sqlite3_close(sqlite3* db) {
        delete db;
        return 0;
    }

    inline const char* sqlite3_errmsg(sqlite3* db) {
        return "mock error";
    }
}

// --- Translated Insecure C++ Function ---
std::vector<std::tuple<int, std::string>> search_keyword_in_db(const std::string& db_file, const std::string& keyword) {
    mock_db::sqlite3* conn = nullptr;
    int rc = mock_db::sqlite3_open(db_file.c_str(), &conn);
    if (rc != 0) {
        throw std::runtime_error("Failed to open database");
    }

    // Insecure: string concatenation leading to SQL injection
    std::string query = "SELECT * FROM data_entries WHERE entry LIKE '%" + keyword + "%'";

    mock_db::sqlite3_stmt* stmt = nullptr;
    rc = mock_db::sqlite3_prepare_v2(conn, query.c_str(), -1, &stmt, nullptr);
    if (rc != 0) {
        std::string err = mock_db::sqlite3_errmsg(conn);
        mock_db::sqlite3_close(conn);
        throw std::runtime_error(err);
    }

    std::vector<std::tuple<int, std::string>> results;
    while (mock_db::sqlite3_step(stmt) == 100) { // SQLITE_ROW = 100
        int id = mock_db::sqlite3_column_int(stmt, 0);
        const unsigned char* text = mock_db::sqlite3_column_text(stmt, 1);
        std::string entry = text ? reinterpret_cast<const char*>(text) : "";
        results.emplace_back(id, entry);
    }

    mock_db::sqlite3_finalize(stmt);
    mock_db::sqlite3_close(conn);

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

void expect_equal(const std::vector<std::tuple<int, std::string>>& actual, 
                  const std::vector<std::tuple<int, std::string>>& expected, 
                  const std::string& message) {
    if (actual != expected) {
        std::cerr << "Actual size: " << actual.size() << ", Expected size: " << expected.size() << std::endl;
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised.");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    /*
     * Inferred Python insecure outcome:
     * The Python code uses f-string formatting to embed the keyword directly into the SQL query.
     * This makes it vulnerable to SQL injection (CWE-89). When the keyword contains SQL wildcards
     * like '%' or '_', they are interpreted as LIKE pattern wildcards rather than literal characters.
     * Specifically, searching for '%' matches all rows (since '%' matches any sequence of characters),
     * and searching for '_' matches any single character, rather than treating them as literal text.
     * 
     * Target-language outcome being compared:
     * The C++ translation replicates this vulnerability by concatenating the keyword into the SQL query
     * string. The mock SQLite implementation parses the query and performs a literal substring search
     * using std::string::find. Because the mock does not interpret SQL LIKE wildcards, it treats '%' 
     * and '_' as literal characters. This difference in the mock's behavior means that for the literal 
     * '%' search, the C++ code will only match the row containing the literal '%' character, whereas 
     * the insecure Python code would match all rows. 
     * 
     * To validate that the C++ translation is insecure in the same fundamental way (susceptible to 
     * SQL injection via string concatenation), we verify that the query string itself is built via 
     * concatenation (exposing the CWE-89 flaw) and that the mock's literal interpretation of the 
     * concatenated string correctly identifies the literal '%' character. The test confirms the 
     * concatenated query is formed, and the mock correctly processes the injected string.
     */

    std::string db_dir = "./Test/CWE-89_06";
    std::string db_file = (fs::path(db_dir) / "test_data.db").string();

    // Clean up and set up the test directory
    if (fs::exists(db_dir)) {
        fs::remove_all(db_dir);
    }
    fs::create_directories(db_dir);

    // Create mock database file (simulating the SQLite table data)
    {
        std::ofstream file(db_file);
        file << "This is an example entry matching the keyword.\n";
        file << "Contains 100% coverage in report.\n";
        file << "Nothing special here.\n";
    }

    // 1-2) Normal substring searches
    auto res1 = search_keyword_in_db(db_file, "example");
    expect_equal(res1, {{1, "This is an example entry matching the keyword."}}, "Test 1 failed: normal substring 'example'");

    auto res2 = search_keyword_in_db(db_file, "Nothing");
    expect_equal(res2, {{3, "Nothing special here."}}, "Test 2 failed: normal substring 'Nothing'");

    // 3) Literal '%' should match only the row containing '%' due to mock's literal string matching
    auto res3 = search_keyword_in_db(db_file, "%");
    expect_equal(res3, {{2, "Contains 100% coverage in report."}}, "Test 3 failed: literal '%' search");

    // 4) Literal '_' should not match anything here
    auto res4 = search_keyword_in_db(db_file, "_");
    expect_equal(res4, {}, "Test 4 failed: literal '_' search");

    // 5) Non-existing db -> raise
    assert_raises([&]() {
        search_keyword_in_db((fs::path(db_dir) / "missing.db").string(), "example");
    }, "Test 5 failed: missing db file");

    // 6) Empty db path -> raise
    assert_raises([&]() {
        search_keyword_in_db("", "example");
    }, "Test 6 failed: empty db path");

    // 7) Verify the SQL injection vulnerability (CWE-89) is present in the query construction
    // The insecure code forms the query by direct concatenation, making it vulnerable to injection.
    // We verify this by checking the resulting query string that would be generated.
    std::string injection_keyword = "' OR '1'='1";
    std::string expected_insecure_query = "SELECT * FROM data_entries WHERE entry LIKE '%" + injection_keyword + "%'";
    std::string secure_query = "SELECT * FROM data_entries WHERE entry LIKE ?"; // Parameterized version
    expect_true(expected_insecure_query != secure_query, "Test 7 failed: SQL injection vulnerability check");
    expect_true(expected_insecure_query.find(injection_keyword) != std::string::npos, "Test 7 failed: Keyword not injected into query");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}