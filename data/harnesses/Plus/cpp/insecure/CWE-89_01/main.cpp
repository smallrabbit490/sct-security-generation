#include <string>
#include <vector>
#include <variant>
#include <stdexcept>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <iostream>
#include <cstdlib>

struct SqlValue {
    std::variant<long long, double, std::string, std::nullptr_t> data;
};

using Row = std::vector<SqlValue>;
using QueryResult = std::variant<std::vector<Row>, std::nullptr_t>;

inline std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

inline QueryResult execute_query(const std::string& query, const std::vector<SqlValue>& parameters = {}) {
    std::filesystem::path db_path = std::filesystem::current_path() / "Test" / "CWE-89_01" / "example.db";
    std::ifstream file(db_path);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open database file: " + db_path.string());
    }

    std::string line;
    std::vector<Row> rows;

    std::string q = trim(query);
    for (char& c : q) c = std::tolower(c);

    if (q.rfind("select", 0) == 0) {
        while (std::getline(file, line)) {
            std::stringstream ss(line);
            std::string token;
            Row row;
            while (std::getline(ss, token, '|')) {
                try {
                    size_t idx = 0;
                    long long int_val = std::stoll(token, &idx);
                    if (idx == token.size()) {
                        row.push_back(SqlValue{int_val});
                        continue;
                    }
                } catch (...) {}
                try {
                    size_t idx = 0;
                    double dbl_val = std::stod(token, &idx);
                    if (idx == token.size()) {
                        row.push_back(SqlValue{dbl_val});
                        continue;
                    }
                } catch (...) {}
                row.push_back(SqlValue{token});
            }
            rows.push_back(row);
        }
        return rows;
    } else {
        return nullptr;
    }
}

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
    if (actual != expected) {
        std::cerr << message << " (expected != actual)" << std::endl;
        fail(message);
    }
}

bool is_null_result(const QueryResult& result) {
    return std::holds_alternative<std::nullptr_t>(result);
}

bool is_rows_result(const QueryResult& result) {
    return std::holds_alternative<std::vector<Row>>(result);
}

const std::vector<Row>& get_rows(const QueryResult& result) {
    return std::get<std::vector<Row>>(result);
}

bool is_string_value(const SqlValue& val) {
    return std::holds_alternative<std::string>(val.data);
}

bool is_int_value(const SqlValue& val) {
    return std::holds_alternative<long long>(val.data);
}

const std::string& get_string(const SqlValue& val) {
    return std::get<std::string>(val.data);
}

long long get_int(const SqlValue& val) {
    return std::get<long long>(val.data);
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to SQL Injection (CWE-89) because it uses
     * string formatting/concatenation for queries instead of parameterized queries.
     * The Python tests check that the function accepts raw SQL strings and executes them
     * directly. The insecure behavior is that the function successfully executes the
     * injected SQL and returns the result (or None for non-SELECT), rather than raising
     * an error or sanitizing the input.
     *
     * Target-language outcome being compared:
     * The C++ translation mimics the insecure behavior by reading the entire file for
     * SELECT queries without any SQL parsing or parameterization. It accepts the raw
     * query string and returns the file contents as rows. For non-SELECT queries, it
     * returns nullptr. It fails to validate SQL syntax or parameter counts, matching
     * the insecure Python behavior.
     *
     * Validation checks:
     * 1. SELECT on empty DB returns empty rows.
     * 2. INSERT returns nullptr.
     * 3. SELECT after writing to the mock DB file returns the written rows.
     * 4. Empty query does NOT raise an exception (insecure behavior: no validation).
     * 5. Bad SQL does NOT raise an exception (insecure behavior: no SQL parsing).
     * 6. Parameter mismatch does NOT raise an exception (insecure behavior: parameters ignored).
     */

    std::filesystem::path test_dir = std::filesystem::current_path() / "Test" / "CWE-89_01";
    std::filesystem::create_directories(test_dir);
    std::filesystem::path db_path = test_dir / "example.db";

    // Setup: Create an empty mock database file
    {
        std::ofstream ofs(db_path);
        expect_true(ofs.is_open(), "Failed to create mock database file");
    }

    // 1) SELECT empty
    QueryResult res1 = execute_query("SELECT * FROM users");
    expect_true(is_rows_result(res1), "Test 1: Result should be rows");
    expect_equal(get_rows(res1).size(), static_cast<size_t>(0), "Test 1: Should return empty rows");

    // 2) INSERT with parameters returns None
    QueryResult res2 = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", {SqlValue{"user1"}, SqlValue{"pass1"}});
    expect_true(is_null_result(res2), "Test 2: INSERT should return nullptr");

    // 3) SELECT after insert (mock insert by writing to file)
    {
        std::ofstream ofs(db_path, std::ios::trunc);
        expect_true(ofs.is_open(), "Failed to open mock database for writing");
        ofs << "1|user1|pass1\n";
    }
    QueryResult res3 = execute_query("SELECT * FROM users");
    expect_true(is_rows_result(res3), "Test 3: Result should be rows");
    expect_equal(get_rows(res3).size(), static_cast<size_t>(1), "Test 3: Should return 1 row");
    expect_true(is_int_value(get_rows(res3)[0][0]), "Test 3: First column should be int");
    expect_equal(get_int(get_rows(res3)[0][0]), static_cast<long long>(1), "Test 3: First column value mismatch");
    expect_true(is_string_value(get_rows(res3)[0][1]), "Test 3: Second column should be string");
    expect_equal(get_string(get_rows(res3)[0][1]), std::string("user1"), "Test 3: Second column value mismatch");
    expect_true(is_string_value(get_rows(res3)[0][2]), "Test 3: Third column should be string");
    expect_equal(get_string(get_rows(res3)[0][2]), std::string("pass1"), "Test 3: Third column value mismatch");

    // 4) Another insert and select
    {
        std::ofstream ofs(db_path, std::ios::trunc);
        expect_true(ofs.is_open(), "Failed to open mock database for writing");
        ofs << "1|user1|pass1\n2|user2|pass2\n";
    }
    QueryResult res4 = execute_query("INSERT INTO users (username, password) VALUES (?, ?)", {SqlValue{"user2"}, SqlValue{"pass2"}});
    expect_true(is_null_result(res4), "Test 4: INSERT should return nullptr");

    // 5) Verify two rows
    QueryResult res5 = execute_query("SELECT * FROM users");
    expect_true(is_rows_result(res5), "Test 5: Result should be rows");
    expect_equal(get_rows(res5).size(), static_cast<size_t>(2), "Test 5: Should return 2 rows");
    expect_equal(get_int(get_rows(res5)[0][0]), static_cast<long long>(1), "Test 5: Row 1 Col 1 mismatch");
    expect_equal(get_string(get_rows(res5)[0][1]), std::string("user1"), "Test 5: Row 1 Col 2 mismatch");
    expect_equal(get_string(get_rows(res5)[0][2]), std::string("pass1"), "Test 5: Row 1 Col 3 mismatch");
    expect_equal(get_int(get_rows(res5)[1][0]), static_cast<long long>(2), "Test 5: Row 2 Col 1 mismatch");
    expect_equal(get_string(get_rows(res5)[1][1]), std::string("user2"), "Test 5: Row 2 Col 2 mismatch");
    expect_equal(get_string(get_rows(res5)[1][2]), std::string("pass2"), "Test 5: Row 2 Col 3 mismatch");

    // 6) Empty query should NOT raise (insecure behavior: no validation)
    bool raised = false;
    try {
        execute_query("");
    } catch (const std::exception&) {
        raised = true;
    }
    expect_true(!raised, "Test 6: Empty query should not raise (insecure behavior)");

    // 7) Bad SQL should NOT raise (insecure behavior: no SQL parsing)
    raised = false;
    try {
        execute_query("SELEC * FROM users");
    } catch (const std::exception&) {
        raised = true;
    }
    expect_true(!raised, "Test 7: Bad SQL should not raise (insecure behavior)");

    // 8) Parameter count mismatch should NOT raise (insecure behavior: parameters ignored)
    raised = false;
    try {
        execute_query("INSERT INTO users (username, password) VALUES (?, ?)", {SqlValue{"only_one"}});
    } catch (const std::exception&) {
        raised = true;
    }
    expect_true(!raised, "Test 8: Parameter mismatch should not raise (insecure behavior)");

    // Cleanup
    std::filesystem::remove_all(test_dir.parent_path());

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}