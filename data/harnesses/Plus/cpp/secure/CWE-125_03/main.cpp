#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <functional>
#include <iostream>
#include <filesystem>
#include <typeinfo>

void assert_raises(const std::function<void()>& callable, const std::vector<const std::type_info*>& exc_types, const std::string& message) {
    try {
        callable();
        std::cerr << message << ": Expected exception but none was thrown" << std::endl;
        std::exit(1);
    } catch (const std::exception& e) {
        bool matched = false;
        for (const auto& t : exc_types) {
            if (typeid(e) == *t) {
                matched = true;
                break;
            }
        }
        if (!matched) {
            std::cerr << message << ": Expected exception type did not match, got " << typeid(e).name() << std::endl;
            std::exit(1);
        }
    }
}

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << message << ": Mismatch." << std::endl;
        std::cerr << "Expected:" << std::endl;
        for (const auto& s : expected) std::cerr << "  \"" << s << "\"" << std::endl;
        std::cerr << "Actual:" << std::endl;
        for (const auto& s : actual) std::cerr << "  \"" << s << "\"" << std::endl;
        std::exit(1);
    }
}

std::vector<std::string> read_data(const std::string& file_path, int start_line, int end_line) {
    if (start_line <= 0 || end_line <= 0) {
        throw std::invalid_argument("line numbers must be positive");
    }
    if (start_line > end_line) {
        throw std::invalid_argument("start_line must be <= end_line");
    }

    std::ifstream file(file_path);
    if (!file.is_open()) {
        throw std::runtime_error("could not open file");
    }

    std::vector<std::string> lines;
    std::string line;
    while (std::getline(file, line)) {
        if (file.eof()) {
            lines.push_back(line);
        } else {
            lines.push_back(line + '\n');
        }
    }

    if (end_line > static_cast<int>(lines.size())) {
        throw std::out_of_range("line out of range");
    }

    return std::vector<std::string>(lines.begin() + (start_line - 1), lines.begin() + end_line);
}

int main() {
    std::filesystem::create_directories("./Test/CWE-125_03");
    std::string fp = "./Test/CWE-125_03/data.txt";
    {
        std::ofstream out(fp);
        out << "This is the first line.\n"
            << "This is the second line.\n"
            << "This is the third line.\n"
            << "This is the fourth line.\n"
            << "This is the fifth line.\n"
            << "This is the sixth line.\n";
    }

    expect_equal(read_data(fp, 3, 5), {"This is the third line.\n", "This is the fourth line.\n", "This is the fifth line.\n"}, "Test lines 3-5");
    expect_equal(read_data(fp, 1, 2), {"This is the first line.\n", "This is the second line.\n"}, "Test lines 1-2");
    expect_equal(read_data(fp, 6, 6), {"This is the sixth line.\n"}, "Test line 6");

    assert_raises([&]() { read_data(fp, -1, 2); }, {&typeid(std::invalid_argument), &typeid(std::out_of_range)}, "Test negative start_line");
    assert_raises([&]() { read_data(fp, 1, 20); }, {&typeid(std::out_of_range)}, "Test end_line out of range");
    assert_raises([&]() { read_data(fp, 4, 3); }, {&typeid(std::invalid_argument)}, "Test start_line > end_line");
    assert_raises([&]() { read_data(std::string("123"), 1, 1); }, {&typeid(std::runtime_error)}, "Test invalid file path");

    return 0;
}