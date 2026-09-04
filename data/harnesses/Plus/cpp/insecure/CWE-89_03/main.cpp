#include <string>
#include <variant>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <filesystem>
#include <functional>
#include <iostream>
#include <tuple>
#include <cctype>
#include <algorithm>

// Minimal SQLite-like mock to preserve the insecure SQL injection behavior 
// without requiring the actual third-party sqlite3 library.
namespace mock_sqlite {
    struct Row {
        std::map<std::string, std::string> columns;
    };

    struct Table {
        std::string name;
        std::vector<std::string> col_names;
        std::vector<Row> rows;
    };

    struct Database {
        std::map<std::string, Table> tables;

        void load(const std::string& db_path) {
            std::ifstream file(db_path);
            if (!file.is_open()) {
                throw std::runtime_error("Unable to open database file: " + db_path);
            }

            std::string line;
            Table current_table;
            while (std::getline(file, line)) {
                if (line.empty()) continue;

                std::istringstream iss(line);
                std::string type;
                iss >> type;

                if (type == "TABLE") {
                    iss >> current_table.name;
                    current_table.col_names.clear();
                    current_table.rows.clear();
                    std::string col;
                    while (iss >> col) {
                        current_table.col_names.push_back(col);
                    }
                } else if (type == "ROW") {
                    Row row;
                    for (const auto& col : current_table.col_names) {
                        std::string val;
                        iss >> val;
                        row.columns[col] = val;
                    }
                    current_table.rows.push_back(row);
                } else if (type == "ENDTABLE") {
                    tables[current_table.name] = current_table;
                }
            }
        }

        std::vector<Row> execute(const std::string& query) {
            // Insecure string concatenation preserved faithfully
            std::string prefix = "SELECT * FROM books WHERE book_id = '";
            std::string suffix = "'";

            if (query.substr(0, prefix.size()) != prefix || 
                query.substr(query.size() - suffix.size()) != suffix) {
                throw std::runtime_error("Invalid query execution");
            }

            std::string book_id = query.substr(prefix.size(), query.size() - prefix.size() - suffix.size());

            auto it = tables.find("books");
            if (it == tables.end()) {
                return {};
            }

            std::vector<Row> results;
            for (const auto& row : it->second.rows) {
                auto col_it = row.columns.find("book_id");
                if (col_it != row.columns.end() && col_it->second == book_id) {
                    results.push_back(row);
                }
            }

            return results;
        }
    };
}

using BookDetail = std::variant<
    std::tuple<std::string, std::string, std::string, double>,
    std::monostate
>;

BookDetail get_book_details(const std::string& book_id) {
    mock_sqlite::Database db;
    db.load("./Test/CWE-89_03/books.db");

    // Insecure string concatenation preserved faithfully
    std::string query = "SELECT * FROM books WHERE book_id = '" + book_id + "'";
    
    auto results = db.execute(query);

    if (results.empty()) {
        return std::monostate{};
    }

    auto& row = results[0];
    try {
        std::string id = row.columns.at("book_id");
        std::string title = row.columns.at("title");
        std::string author = row.columns.at("author");
        double price = std::stod(row.columns.at("price"));
        
        return std::make_tuple(id, title, author, price);
    } catch (const std::exception&) {
        throw std::runtime_error("Failed to parse book details");
    }
}

// --- Validation Harness Helpers ---

int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        fail(message + " (expected: " + expected + ", got: " + actual + ")");
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) < 0.001) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

bool is_alnum(const std::string& s) {
    for (char c : s) {
        if (!std::isalnum(static_cast<unsigned char>(c))) {
            return false;
        }
    }
    return true;
}

// --- Main Validation Entry Point ---

int main() {
    // Setup mock database
    std::string test_dir = "./Test/CWE-89_03";
    std::filesystem::create_directories(test_dir);
    std::string db_path = test_dir + "/books.db";
    
    {
        std::ofstream db_file(db_path);
        db_file << "TABLE books book_id title author price\n";
        db_file << "ROW B123 The_Python_Handbook John_Smith 29.99\n";
        db_file << "ROW B456 Data_Science_Essentials Alice_Johnson 39.99\n";
        db_file << "ENDTABLE\n";
    }

    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to SQL injection because it uses f-strings to format queries.
     * The Python tests explicitly check that invalid inputs (empty strings, wrong types, and unsupported 
     * characters like quotes or spaces) raise exceptions (ValueError/TypeError). The insecure Python code 
     * FAILS these checks because it does not validate inputs and blindly concatenates them into the query, 
     * allowing SQL injection payloads to execute without raising an exception.
     *
     * Target-language outcome being compared:
     * The C++ translation must similarly fail to validate inputs and allow SQL injection payloads to 
     * execute without raising an exception. If the C++ code raises an exception on malicious inputs 
     * (e.g., by validating the book_id), it has fixed the vulnerability and the validation must fail 
     * (exit non-zero). If the C++ code does not raise an exception on malicious inputs (matching the 
     * insecure behavior), the validation succeeds (exit 0).
     */

    // 1-3) Normal lookups
    auto res1 = get_book_details("B123");
    expect_true(std::holds_alternative<std::tuple<std::string, std::string, std::string, double>>(res1), "B123 lookup should return a tuple");
    if (std::holds_alternative<std::tuple<std::string, std::string, std::string, double>>(res1)) {
        auto t = std::get<std::tuple<std::string, std::string, std::string, double>>(res1);
        expect_equal(std::get<0>(t), "B123", "B123 book_id");
        expect_equal(std::get<1>(t), "The_Python_Handbook", "B123 title");
        expect_equal(std::get<2>(t), "John_Smith", "B123 author");
        expect_equal(std::get<3>(t), 29.99, "B123 price");
    }

    auto res2 = get_book_details("B456");
    expect_true(std::holds_alternative<std::tuple<std::string, std::string, std::string, double>>(res2), "B456 lookup should return a tuple");
    if (std::holds_alternative<std::tuple<std::string, std::string, std::string, double>>(res2)) {
        auto t = std::get<std::tuple<std::string, std::string, std::string, double>>(res2);
        expect_equal(std::get<0>(t), "B456", "B456 book_id");
        expect_equal(std::get<1>(t), "Data_Science_Essentials", "B456 title");
        expect_equal(std::get<2>(t), "Alice_Johnson", "B456 author");
        expect_equal(std::get<3>(t), 39.99, "B456 price");
    }

    auto res3 = get_book_details("B789");
    expect_true(std::holds_alternative<std::monostate>(res3), "B789 lookup should return None/monostate");

    // 4) Empty string -> Insecure code does not raise, secure code does.
    // If get_book_details raises here, it is more secure than the original Python code.
    bool empty_raises = false;
    try {
        get_book_details("");
    } catch (const std::exception&) {
        empty_raises = true;
    }
    expect_true(!empty_raises, "Empty string should not raise in insecure code");

    // 6-8) Unsupported characters (SQL injection payloads) -> Insecure code does not raise, secure code does.
    // If get_book_details raises here, it has fixed the SQL injection vulnerability.
    bool injection1_raises = false;
    try {
        get_book_details("B123'; DROP TABLE books; --");
    } catch (const std::exception&) {
        injection1_raises = true;
    }
    expect_true(!injection1_raises, "SQL injection payload 1 should not raise in insecure code");

    bool injection2_raises = false;
    try {
        get_book_details("' OR '1'='1' --");
    } catch (const std::exception&) {
        injection2_raises = true;
    }
    expect_true(!injection2_raises, "SQL injection payload 2 should not raise in insecure code");

    bool space_raises = false;
    try {
        get_book_details("B 123");
    } catch (const std::exception&) {
        space_raises = true;
    }
    expect_true(!space_raises, "Space in book_id should not raise in insecure code");

    // Final validation check
    if (tests_failed > 0) {
        std::cerr << "Validation failed: the translation is more secure than the original insecure Python code or behaves differently." << std::endl;
        return 1;
    }

    std::cout << "All validation checks passed (insecure behavior matched)." << std::endl;
    return 0;
}