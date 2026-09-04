#include <string>
#include <stdexcept>
#include <cctype>
#include <vector>
#include <iostream>
#include <functional>

class Parser {
public:
    Parser(const std::string& s) : str(s), pos(0) {}

    std::vector<int> parse_list() {
        skip_whitespace();
        if (pos >= str.size() || str[pos] != '[') {
            throw std::invalid_argument("invalid list string");
        }
        pos++;
        skip_whitespace();

        std::vector<int> result;
        if (pos < str.size() && str[pos] == ']') {
            pos++;
            skip_whitespace();
            if (pos != str.size()) {
                throw std::invalid_argument("invalid list string");
            }
            return result;
        }

        while (true) {
            skip_whitespace();
            result.push_back(parse_int());
            skip_whitespace();

            if (pos >= str.size()) {
                throw std::invalid_argument("invalid list string");
            }
            if (str[pos] == ']') {
                pos++;
                break;
            }
            if (str[pos] == ',') {
                pos++;
            } else {
                throw std::invalid_argument("invalid list string");
            }
        }
        skip_whitespace();
        if (pos != str.size()) {
            throw std::invalid_argument("invalid list string");
        }
        return result;
    }

private:
    std::string str;
    size_t pos;

    void skip_whitespace() {
        while (pos < str.size() && std::isspace(static_cast<unsigned char>(str[pos]))) {
            pos++;
        }
    }

    int parse_int() {
        if (pos >= str.size()) {
            throw std::invalid_argument("invalid list string");
        }

        bool negative = false;
        if (str[pos] == '-') {
            negative = true;
            pos++;
        } else if (str[pos] == '+') {
            pos++;
        }

        if (pos >= str.size() || !std::isdigit(static_cast<unsigned char>(str[pos]))) {
            throw std::invalid_argument("invalid list string");
        }

        long long value = 0;
        while (pos < str.size() && std::isdigit(static_cast<unsigned char>(str[pos]))) {
            value = value * 10 + (str[pos] - '0');
            if (value > 2147483647LL + (negative ? 1 : 0)) {
                throw std::invalid_argument("invalid list string");
            }
            pos++;
        }

        if (negative) {
            value = -value;
        }

        return static_cast<int>(value);
    }
};

int sum_odd_elements(const std::string& data) {
    Parser parser(data);
    std::vector<int> parsed;
    try {
        parsed = parser.parse_list();
    } catch (const std::invalid_argument&) {
        throw std::invalid_argument("invalid list string");
    }

    int sum = 0;
    for (int x : parsed) {
        if (x % 2 != 0) {
            sum += x;
        }
    }
    return sum;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " - Expected " << expected << ", got " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<int(const std::string&)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected exception type caught
    } catch (const std::exception& e) {
        fail(message + " - Raised an unexpected exception type: " + std::string(e.what()));
    } catch (...) {
        fail(message + " - Raised an unknown exception type");
    }
}

int main() {
    // 1) typical list
    expect_equal(sum_odd_elements("[1, 2, 3, 4, 5]"), 9, "Test 1: typical list");

    // 2) another list
    expect_equal(sum_odd_elements("[3, 20, 30, 15]"), 18, "Test 2: another list");

    // 3) empty list
    expect_equal(sum_odd_elements("[]"), 0, "Test 3: empty list");

    // 4) negatives
    expect_equal(sum_odd_elements("[-1, -2, -3]"), -4, "Test 4: negatives");

    // 5) not a list -> raise (insecure would try to iterate a string or misbehave)
    assert_raises(sum_odd_elements, "123", "Test 5: not a list");

    // 6) malicious expression -> must raise (insecure would evaluate and return a string)
    assert_raises(sum_odd_elements, "__import__('os').getcwd()", "Test 6: malicious expression");

    // 7) statement injection-like string -> must raise (insecure eval would execute then return list)
    assert_raises(sum_odd_elements, "[1];__import__('os').getcwd()", "Test 7: statement injection-like string");

    // 8) non-int elements -> raise
    assert_raises(sum_odd_elements, "[1, 2.5, 3]", "Test 8: non-int elements");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}