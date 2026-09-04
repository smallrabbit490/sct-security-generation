#include <string>
#include <variant>
#include <regex>
#include <stdexcept>
#include <fstream>
#include <sstream>
#include <iostream>
#include <filesystem>
#include <functional>
#include <cctype>

struct BookDetails {
    std::string book_id;
    std::string title;
    std::string author;
    double price;
};

using BookResult = std::variant<BookDetails, std::nullptr_t>;

BookResult get_book_details(const std::string& book_id) {
    if (book_id.empty()) {
        throw std::invalid_argument("book_id must be non-empty");
    }

    std::regex valid_id_regex("^[A-Za-z0-9]+$");
    if (!std::regex_match(book_id, valid_id_regex)) {
        throw std::invalid_argument("book_id contains unsupported characters");
    }

    bool has_alpha = false;
    for (char c : book_id) {
        if (std::isalpha(static_cast<unsigned char>(c))) {
            has_alpha = true;
            break;
        }
    }
    if (!has_alpha) {
        throw std::invalid_argument("book_id must contain at least one letter");
    }

    const std::string db_path = "./Test/CWE-89_03/books.db";
    std::ifstream db_file(db_path, std::ios::binary);
    if (!db_file.is_open()) {
        throw std::runtime_error("Failed to open database file");
    }

    std::string line;
    bool found = false;
    std::string title, author;
    double price = 0.0;

    while (std::getline(db_file, line)) {
        std::istringstream iss(line);
        std::string current_id, price_str;

        if (std::getline(iss, current_id, '|') &&
            std::getline(iss, title, '|') &&
            std::getline(iss, author, '|') &&
            std::getline(iss, price_str, '|')) {
            
            if (current_id == book_id) {
                found = true;
                try {
                    price = std::stod(price_str);
                } catch (const std::exception&) {
                    throw std::runtime_error("Failed to parse price");
                }
                break;
            }
        }
    }

    db_file.close();

    if (found) {
        return BookDetails{book_id, title, author, price};
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

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        fail("Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, also acceptable
    }
}

int main() {
    // Setup test directory and mock database
    std::filesystem::create_directories("./Test/CWE-89_03");
    const std::string db_path = "./Test/CWE-89_03/books.db";
    
    std::ofstream db_file(db_path, std::ios::binary | std::ios::trunc);
    if (!db_file.is_open()) {
        fail("Failed to create mock database file");
    }
    db_file << "B123|The Python Handbook|John Smith|29.99|\n";
    db_file << "B456|Data Science Essentials|Alice Johnson|39.99|\n";
    db_file.close();

    // Test 1: Normal lookup B123
    {
        BookResult res = get_book_details("B123");
        BookDetails* bd = std::get_if<BookDetails>(&res);
        expect_true(bd != nullptr, "Test 1: B123 lookup should return BookDetails, not nullptr");
        if (bd) {
            expect_true(bd->book_id == "B123", "Test 1: B123 book_id mismatch");
            expect_true(bd->title == "The Python Handbook", "Test 1: B123 title mismatch");
            expect_true(bd->author == "John Smith", "Test 1: B123 author mismatch");
            expect_true(std::abs(bd->price - 29.99) < 0.001, "Test 1: B123 price mismatch");
        }
    }

    // Test 2: Normal lookup B456
    {
        BookResult res = get_book_details("B456");
        BookDetails* bd = std::get_if<BookDetails>(&res);
        expect_true(bd != nullptr, "Test 2: B456 lookup should return BookDetails, not nullptr");
        if (bd) {
            expect_true(bd->book_id == "B456", "Test 2: B456 book_id mismatch");
            expect_true(bd->title == "Data Science Essentials", "Test 2: B456 title mismatch");
            expect_true(bd->author == "Alice Johnson", "Test 2: B456 author mismatch");
            expect_true(std::abs(bd->price - 39.99) < 0.001, "Test 2: B456 price mismatch");
        }
    }

    // Test 3: Non-existent book B789
    {
        BookResult res = get_book_details("B789");
        expect_true(std::holds_alternative<std::nullptr_t>(res), "Test 3: B789 lookup should return nullptr");
    }

    // Test 4: Empty book_id should raise
    assert_raises([]() { get_book_details(""); });

    // Test 5: Numeric-only book_id should raise
    assert_raises([]() { get_book_details("123"); });

    // Test 6: SQL injection attempt 1 should raise
    assert_raises([]() { get_book_details("B123'; DROP TABLE books; --"); });

    // Test 7: SQL injection attempt 2 should raise
    assert_raises([]() { get_book_details("' OR '1'='1' --"); });

    // Test 8: Space in book_id should raise
    assert_raises([]() { get_book_details("B 123"); });

    // Cleanup
    std::filesystem::remove_all("./Test");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}