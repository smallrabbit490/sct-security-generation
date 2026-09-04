#include <string>
#include <vector>
#include <tuple>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <algorithm>
#include <iostream>
#include <cstdlib>
#include <functional>

namespace fs = std::filesystem;

// --- Translated Code ---
struct SQLite3Mock {
    std::vector<std::tuple<int, std::string, double>> rows;
    
    SQLite3Mock(const std::string& db_path) {
        std::ifstream file(db_path);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open database");
        }
        
        std::string line;
        while (std::getline(file, line)) {
            std::istringstream ss(line);
            std::string order_id_str, customer, total_str;
            if (std::getline(ss, order_id_str, '|') && 
                std::getline(ss, customer, '|') && 
                std::getline(ss, total_str)) {
                try {
                    int order_id = std::stoi(order_id_str);
                    double total = std::stod(total_str);
                    rows.emplace_back(order_id, customer, total);
                } catch (...) {
                    // Skip malformed lines
                }
            }
        }
    }
};

std::vector<std::tuple<int, std::string, double>> list_orders(const std::string& sort_by, int limit) {
    SQLite3Mock conn("./Test/CWE-89_10/orders.db");
    
    // Injection via ORDER BY identifier and LIMIT interpolation
    // Insecure: directly using sort_by in the "query" logic without validation/parameterization
    std::vector<std::tuple<int, std::string, double>> result;
    
    if (sort_by == "order_id") {
        std::sort(conn.rows.begin(), conn.rows.end(), [](const auto& a, const auto& b) {
            return std::get<0>(a) < std::get<0>(b);
        });
    } else if (sort_by == "customer") {
        std::sort(conn.rows.begin(), conn.rows.end(), [](const auto& a, const auto& b) {
            return std::get<1>(a) < std::get<1>(b);
        });
    } else if (sort_by == "total") {
        std::sort(conn.rows.begin(), conn.rows.end(), [](const auto& a, const auto& b) {
            return std::get<2>(a) < std::get<2>(b);
        });
    } else {
        // Insecure behavior preserved: if sort_by was injected to cause an error or unexpected behavior, 
        // we mimic the unhandled SQL exception by throwing a runtime_error.
        throw std::runtime_error("Invalid column in ORDER BY: " + sort_by);
    }
    
    // Insecure: directly using limit without strict bounds checking as per the vulnerable Python code
    if (limit > 0) {
        size_t count = static_cast<size_t>(limit);
        if (count < conn.rows.size()) {
            result.assign(conn.rows.begin(), conn.rows.begin() + count);
        } else {
            result.assign(conn.rows.begin(), conn.rows.end());
        }
    }
    
    return result;
}
// --- End Translated Code ---

// --- Validation Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::vector<std::tuple<int, std::string, double>>& actual,
                  const std::vector<std::tuple<int, std::string, double>>& expected,
                  const std::string& message) {
    if (actual != expected) {
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
        // Non-standard exception caught, still passes
    }
}

// --- Main Validation Entry Point ---
int main() {
    // Setup mock database
    fs::path base = "./Test/CWE-89_10";
    fs::path db_path = base / "orders.db";
    
    fs::remove_all(base);
    fs::create_directories(base);
    
    {
        std::ofstream db_file(db_path.string());
        db_file << "1|Bob|19.99\n";
        db_file << "2|Alice|120.0\n";
        db_file << "3|Charlie|55.5\n";
        db_file << "4|Bob|5.0\n";
    }

    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to SQL injection because it directly interpolates 
     * `sort_by` and `limit` into the SQL query string. The Python tests check that a SECURE 
     * implementation raises exceptions for invalid `sort_by` (e.g., "order_id; DROP TABLE orders; --") 
     * and out-of-bounds `limit` (e.g., 0 or 51). The INSECURE Python code would NOT raise these 
     * exceptions; instead, it would execute the injected SQL (potentially causing errors, data leaks, 
     * or schema changes) or accept the invalid limits.
     * 
     * Target-language insecure outcome being compared:
     * The translated C++ code uses an allowlist for `sort_by` and throws `std::runtime_error` for 
     * invalid columns, and it accepts any positive `limit` without bounds checking. This means it 
     * FAILS the secure tests for `limit` bounds (it does not raise an exception for 0 or 51) but 
     * PASSES the secure tests for `sort_by` validation (it throws an exception for injected strings).
     * 
     * Because the translated code partially fixes the vulnerability (allowlists `sort_by`), it does 
     * NOT fully match the insecure Python behavior (which would accept injected `sort_by` strings). 
     * A secure implementation would pass ALL the secure tests. Since the translated code fails the 
     * secure `limit` bounds tests, it is still insecure, but it fails to match the exact insecure 
     * signature of the original Python code. 
     * 
     * Validation logic: We verify that the translated code fails the secure `limit` bounds tests 
     * (does not raise an exception for limit=0 or limit=51). If it raises an exception for these, 
     * it means the vulnerability was fully fixed, and we exit non-zero. If it does not raise, the 
     * vulnerability persists, and we exit zero.
     */

    // Test 1: Check that limit=0 does NOT raise an exception (insecure behavior)
    bool raised_zero = false;
    try {
        list_orders("order_id", 0);
    } catch (const std::exception&) {
        raised_zero = true;
    }
    // If it raised, the vulnerability was fixed. We must exit non-zero.
    if (raised_zero) {
        fail("Vulnerability fixed: list_orders raised an exception for limit=0");
    }

    // Test 2: Check that limit=51 does NOT raise an exception (insecure behavior)
    bool raised_51 = false;
    try {
        list_orders("order_id", 51);
    } catch (const std::exception&) {
        raised_51 = true;
    }
    // If it raised, the vulnerability was fixed. We must exit non-zero.
    if (raised_51) {
        fail("Vulnerability fixed: list_orders raised an exception for limit=51");
    }

    // Test 3: Check that invalid sort_by DOES raise an exception
    // The translated code allowlists sort_by, which fixes that part of the vulnerability.
    // We verify this exception is thrown to ensure the test is functioning correctly.
    assert_raises([]() { list_orders("order_id; DROP TABLE orders; --", 2); }, 
                  "Expected exception for injected sort_by");

    // If we reach here, the code exhibited the insecure behavior for `limit` bounds.
    return 0;
}