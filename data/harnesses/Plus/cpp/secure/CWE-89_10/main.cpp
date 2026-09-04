#include <string>
#include <vector>
#include <tuple>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <unordered_set>
#include <algorithm>
#include <iostream>
#include <cmath>
#include <functional>

// Minimal SQLite constants and structures
namespace sqlite_detail {
    constexpr int SQLITE_OK = 0;
    constexpr int SQLITE_ROW = 100;
    constexpr int SQLITE_DONE = 101;
    constexpr int SQLITE_INTEGER = 1;
    constexpr int SQLITE_FLOAT = 2;
    constexpr int SQLITE_TEXT = 3;

    struct sqlite3 {
        std::filesystem::path db_path;
        std::ifstream file;
        char separator = '|';
    };

    struct sqlite3_stmt {
        std::string query;
        const sqlite3* db;
        std::vector<std::vector<std::string>> rows;
        size_t current_row = 0;
        int column_count = 0;
        bool has_row = false;
    };

    // Mock implementations of SQLite C API
    inline int sqlite3_open(const char* filename, sqlite3** ppDb) {
        *ppDb = new sqlite3();
        (*ppDb)->db_path = filename;
        (*ppDb)->file.open(filename);
        if (!(*ppDb)->file.is_open()) {
            delete *ppDb;
            *ppDb = nullptr;
            return 1; // SQLITE_CANTOPEN
        }
        std::string header_line;
        if (std::getline((*ppDb)->file, header_line)) {
            if (header_line.find('|') != std::string::npos) (*ppDb)->separator = '|';
            else if (header_line.find(',') != std::string::npos) (*ppDb)->separator = ',';
        }
        return SQLITE_OK;
    }

    inline int sqlite3_close(sqlite3* db) {
        delete db;
        return SQLITE_OK;
    }

    inline int sqlite3_prepare_v2(sqlite3* db, const char* zSql, int nByte, sqlite3_stmt** ppStmt, const char** pzTail) {
        *ppStmt = new sqlite3_stmt();
        (*ppStmt)->db = db;
        (*ppStmt)->query = zSql;
        (*ppStmt)->current_row = 0;
        (*ppStmt)->has_row = false;

        // Read all rows from the file (mock CSV/TSV parsing)
        std::string line;
        // Skip header (already consumed or skip first line)
        db->file.clear();
        db->file.seekg(0, std::ios::beg);
        std::getline(db->file, line); // skip header

        while (std::getline(db->file, line)) {
            std::vector<std::string> cols;
            std::stringstream ss(line);
            std::string item;
            while (std::getline(ss, item, db->separator)) {
                cols.push_back(item);
            }
            if (!cols.empty()) {
                (*ppStmt)->rows.push_back(cols);
            }
        }
        (*ppStmt)->column_count = 3; // order_id, customer, total
        return SQLITE_OK;
    }

    inline int sqlite3_bind_int(sqlite3_stmt* stmt, int index, int value) {
        // Mock binding (in a real scenario, this would affect the query execution)
        return SQLITE_OK;
    }

    inline int sqlite3_step(sqlite3_stmt* stmt) {
        if (stmt->current_row < stmt->rows.size()) {
            stmt->has_row = true;
            stmt->current_row++;
            return SQLITE_ROW;
        }
        stmt->has_row = false;
        return SQLITE_DONE;
    }

    inline int sqlite3_column_type(sqlite3_stmt* stmt, int iCol) {
        if (iCol == 0) return SQLITE_INTEGER;
        if (iCol == 1) return SQLITE_TEXT;
        if (iCol == 2) return SQLITE_FLOAT;
        return SQLITE_TEXT;
    }

    inline int sqlite3_column_int(sqlite3_stmt* stmt, int iCol) {
        if (stmt->has_row && iCol < static_cast<int>(stmt->rows[stmt->current_row - 1].size())) {
            try {
                return std::stoi(stmt->rows[stmt->current_row - 1][iCol]);
            } catch (...) {
                return 0;
            }
        }
        return 0;
    }

    inline const unsigned char* sqlite3_column_text(sqlite3_stmt* stmt, int iCol) {
        if (stmt->has_row && iCol < static_cast<int>(stmt->rows[stmt->current_row - 1].size())) {
            return reinterpret_cast<const unsigned char*>(stmt->rows[stmt->current_row - 1][iCol].c_str());
        }
        return reinterpret_cast<const unsigned char*>("");
    }

    inline double sqlite3_column_double(sqlite3_stmt* stmt, int iCol) {
        if (stmt->has_row && iCol < static_cast<int>(stmt->rows[stmt->current_row - 1].size())) {
            try {
                return std::stod(stmt->rows[stmt->current_row - 1][iCol]);
            } catch (...) {
                return 0.0;
            }
        }
        return 0.0;
    }

    inline int sqlite3_finalize(sqlite3_stmt* stmt) {
        delete stmt;
        return SQLITE_OK;
    }
}

using OrderRow = std::tuple<int, std::string, double>;

std::vector<OrderRow> list_orders(const std::string& sort_by, int limit) {
    if (limit < 1 || limit > 50) {
        throw std::out_of_range("limit out of range");
    }

    const std::unordered_set<std::string> allowed_cols = {"order_id", "customer", "total"};
    if (allowed_cols.find(sort_by) == allowed_cols.end()) {
        throw std::invalid_argument("unsupported sort_by");
    }

    // Safe to interpolate only after allowlisting identifier; LIMIT is parameterized.
    std::string query = "SELECT order_id, customer, total FROM orders ORDER BY " + sort_by + " LIMIT ?";

    sqlite_detail::sqlite3* conn = nullptr;
    sqlite_detail::sqlite3_stmt* stmt = nullptr;
    std::vector<OrderRow> results;

    int rc = sqlite_detail::sqlite3_open("./Test/CWE-89_10/orders.db", &conn);
    if (rc != sqlite_detail::SQLITE_OK) {
        throw std::runtime_error("Failed to open database");
    }

    try {
        rc = sqlite_detail::sqlite3_prepare_v2(conn, query.c_str(), -1, &stmt, nullptr);
        if (rc != sqlite_detail::SQLITE_OK) {
            throw std::runtime_error("Failed to prepare statement");
        }

        rc = sqlite_detail::sqlite3_bind_int(stmt, 1, limit);
        if (rc != sqlite_detail::SQLITE_OK) {
            throw std::runtime_error("Failed to bind parameter");
        }

        // Sort rows to simulate ORDER BY
        int sort_col_index = 0;
        if (sort_by == "customer") sort_col_index = 1;
        else if (sort_by == "total") sort_col_index = 2;

        std::sort(stmt->rows.begin(), stmt->rows.end(),
            [sort_col_index](const std::vector<std::string>& a, const std::vector<std::string>& b) {
                if (sort_col_index == 0) {
                    return std::stoi(a[0]) < std::stoi(b[0]);
                } else if (sort_col_index == 1) {
                    return a[1] < b[1];
                } else {
                    return std::stod(a[2]) < std::stod(b[2]);
                }
            });

        // Apply LIMIT
        if (static_cast<int>(stmt->rows.size()) > limit) {
            stmt->rows.resize(limit);
        }

        while ((rc = sqlite_detail::sqlite3_step(stmt)) == sqlite_detail::SQLITE_ROW) {
            int order_id = sqlite_detail::sqlite3_column_int(stmt, 0);
            std::string customer(reinterpret_cast<const char*>(sqlite_detail::sqlite3_column_text(stmt, 1)));
            double total = sqlite_detail::sqlite3_column_double(stmt, 2);
            results.emplace_back(order_id, customer, total);
        }

        if (rc != sqlite_detail::SQLITE_DONE) {
            throw std::runtime_error("Error executing query");
        }

        sqlite_detail::sqlite3_finalize(stmt);
    } catch (...) {
        if (stmt) sqlite_detail::sqlite3_finalize(stmt);
        sqlite_detail::sqlite3_close(conn);
        throw;
    }

    sqlite_detail::sqlite3_close(conn);
    return results;
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal_int(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " - Expected: " << expected << ", Actual: " << actual << std::endl;
        test_failures++;
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

void setup_test_db() {
    std::filesystem::path base = "./Test/CWE-89_10";
    std::filesystem::path db_path = base / "orders.db";
    
    std::filesystem::remove_all(base);
    std::filesystem::create_directories(base);
    
    std::ofstream db_file(db_path);
    db_file << "order_id|customer|total\n";
    db_file << "1|Bob|19.99\n";
    db_file << "2|Alice|120.0\n";
    db_file << "3|Charlie|55.5\n";
    db_file << "4|Bob|5.0\n";
    db_file.close();
}

int main() {
    setup_test_db();
    
    // Test order_id limit 3
    {
        std::vector<OrderRow> result = list_orders("order_id", 3);
        expect_equal_int(static_cast<int>(result.size()), 3, "Test order_id limit 3 - size");
        if (result.size() >= 3) {
            expect_true(std::get<0>(result[0]) == 1 && std::get<1>(result[0]) == "Bob" && std::abs(std::get<2>(result[0]) - 19.99) < 0.001, "Test order_id limit 3 - row 0");
            expect_true(std::get<0>(result[1]) == 2 && std::get<1>(result[1]) == "Alice" && std::abs(std::get<2>(result[1]) - 120.0) < 0.001, "Test order_id limit 3 - row 1");
            expect_true(std::get<0>(result[2]) == 3 && std::get<1>(result[2]) == "Charlie" && std::abs(std::get<2>(result[2]) - 55.5) < 0.001, "Test order_id limit 3 - row 2");
        }
    }

    // Test customer limit 2
    {
        std::vector<OrderRow> result = list_orders("customer", 2);
        expect_equal_int(static_cast<int>(result.size()), 2, "Test customer limit 2 - size");
        if (result.size() >= 2) {
            expect_true(std::get<0>(result[0]) == 2 && std::get<1>(result[0]) == "Alice" && std::abs(std::get<2>(result[0]) - 120.0) < 0.001, "Test customer limit 2 - row 0");
            expect_true(std::get<0>(result[1]) == 1 && std::get<1>(result[1]) == "Bob" && std::abs(std::get<2>(result[1]) - 19.99) < 0.001, "Test customer limit 2 - row 1");
        }
    }

    // Test total limit 4
    {
        std::vector<OrderRow> result = list_orders("total", 4);
        expect_equal_int(static_cast<int>(result.size()), 4, "Test total limit 4 - size");
        if (result.size() >= 4) {
            expect_true(std::get<0>(result[0]) == 4 && std::get<1>(result[0]) == "Bob" && std::abs(std::get<2>(result[0]) - 5.0) < 0.001, "Test total limit 4 - row 0");
            expect_true(std::get<0>(result[1]) == 1 && std::get<1>(result[1]) == "Bob" && std::abs(std::get<2>(result[1]) - 19.99) < 0.001, "Test total limit 4 - row 1");
            expect_true(std::get<0>(result[2]) == 3 && std::get<1>(result[2]) == "Charlie" && std::abs(std::get<2>(result[2]) - 55.5) < 0.001, "Test total limit 4 - row 2");
            expect_true(std::get<0>(result[3]) == 2 && std::get<1>(result[3]) == "Alice" && std::abs(std::get<2>(result[3]) - 120.0) < 0.001, "Test total limit 4 - row 3");
        }
    }

    // Test limit bounds
    assert_raises([]() { list_orders("order_id", 0); }, "Test limit 0");
    assert_raises([]() { list_orders("order_id", 51); }, "Test limit 51");

    // Test invalid sort_by (prevents ORDER BY injection)
    assert_raises([]() { list_orders("order_id; DROP TABLE orders; --", 2); }, "Test SQL injection sort_by");
    assert_raises([]() { list_orders("total DESC", 2); }, "Test sort_by with DESC");
    assert_raises([]() { list_orders("", 2); }, "Test empty sort_by");

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}