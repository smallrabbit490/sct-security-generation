#include <string>
#include <vector>
#include <map>
#include <variant>
#include <regex>
#include <stdexcept>
#include <sstream>
#include <iostream>

struct Row : std::map<std::string, std::variant<std::monostate, std::string, long long, double, bool>> {
    using std::map<std::string, std::variant<std::monostate, std::string, long long, double, bool>>::map;
};

std::string unescape_string(const std::string& s) {
    std::string result;
    result.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '\\' && i + 1 < s.size()) {
            char next = s[i + 1];
            switch (next) {
                case 'n': result += '\n'; break;
                case 't': result += '\t'; break;
                case 'r': result += '\r'; break;
                case '\\': result += '\\'; break;
                case '\'': result += '\''; break;
                case '"': result += '"'; break;
                case 'a': result += '\a'; break;
                case 'b': result += '\b'; break;
                case 'f': result += '\f'; break;
                case 'v': result += '\v'; break;
                case '0': result += '\0'; break;
                default:
                    result += '\\';
                    result += next;
                    break;
            }
            ++i;
        } else {
            result += s[i];
        }
    }
    return result;
}

std::vector<Row> filter_rows(const std::vector<Row>& rows, const std::string& predicate) {
    for (const auto& row : rows) {
        for (const auto& kv : row) {
            const auto& v = kv.second;
            if (!std::holds_alternative<std::monostate>(v) &&
                !std::holds_alternative<std::string>(v) &&
                !std::holds_alternative<long long>(v) &&
                !std::holds_alternative<double>(v) &&
                !std::holds_alternative<bool>(v)) {
                throw std::runtime_error("row values must be primitive types");
            }
        }
    }

    std::regex pred_regex(
        R"del(\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(?:(-?(?:\d+(?:\.\d*)?|\.\d+))|"([^"\\]*(?:\\.[^"\\]*)*)")\s*)del"
    );
    std::smatch m;
    if (!std::regex_match(predicate, m, pred_regex)) {
        throw std::invalid_argument("invalid predicate format");
    }

    std::string field = m[1].str();
    std::string op = m[2].str();
    std::string num_s = m[3].str();
    std::string str_s = m[4].str();

    bool value_is_number = !num_s.empty();
    double num_value = 0.0;
    std::string str_value;

    if (value_is_number) {
        try {
            size_t pos;
            num_value = std::stod(num_s, &pos);
            if (pos != num_s.size()) {
                throw std::invalid_argument("trailing characters");
            }
        } catch (const std::invalid_argument&) {
            throw;
        } catch (const std::exception&) {
            throw std::invalid_argument("invalid numeric value");
        }
    } else {
        try {
            str_value = unescape_string(str_s);
        } catch (const std::exception&) {
            throw std::invalid_argument("invalid string literal");
        }
    }

    auto cmp = [&](double a, double b) -> bool {
        if (op == "==") return a == b;
        if (op == "!=") return a != b;
        if (op == ">")  return a > b;
        if (op == ">=") return a >= b;
        if (op == "<")  return a < b;
        if (op == "<=") return a <= b;
        throw std::invalid_argument("invalid operator");
    };

    auto cmp_str = [&](const std::string& a, const std::string& b) -> bool {
        if (op == "==") return a == b;
        if (op == "!=") return a != b;
        if (op == ">")  return a > b;
        if (op == ">=") return a >= b;
        if (op == "<")  return a < b;
        if (op == "<=") return a <= b;
        throw std::invalid_argument("invalid operator");
    };

    std::vector<Row> out;
    for (const auto& row : rows) {
        auto it = row.find(field);
        if (it == row.end()) {
            throw std::invalid_argument("unknown field");
        }

        const auto& cell = it->second;
        if (value_is_number) {
            if (!std::holds_alternative<long long>(cell) &&
                !std::holds_alternative<double>(cell)) {
                throw std::invalid_argument("field value must be numeric for numeric comparisons");
            }
            double cell_num = std::holds_alternative<long long>(cell) ?
                              static_cast<double>(std::get<long long>(cell)) :
                              std::get<double>(cell);
            if (cmp(cell_num, num_value)) {
                out.push_back(row);
            }
        } else {
            if (!std::holds_alternative<std::string>(cell)) {
                throw std::invalid_argument("field value must be string for string comparisons");
            }
            if (cmp_str(std::get<std::string>(cell), str_value)) {
                out.push_back(row);
            }
        }
    }

    return out;
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error("FAIL: " + message + " - got '" + actual + "' expected '" + expected + "'");
    }
}

void expect_equal(long long actual, long long expected, const std::string& message) {
    if (actual != expected) {
        throw std::runtime_error("FAIL: " + message + " - got " + std::to_string(actual) + " expected " + std::to_string(expected));
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error("FAIL: " + message);
    }
}

template<typename Func>
void assert_raises(Func f, const std::string& message) {
    bool caught = false;
    try {
        f();
    } catch (const std::exception&) {
        caught = true;
    }
    expect_true(caught, message);
}

int main() {
    std::vector<Row> rows = {
        {{"name", std::string("Alice")}, {"age", 30LL}, {"active", true}},
        {{"name", std::string("Bob")}, {"age", 20LL}, {"active", false}},
        {{"name", std::string("Cara")}, {"age", 25LL}, {"active", true}}
    };

    // Test 1: age >= 25
    {
        auto out = filter_rows(rows, "age >= 25");
        expect_equal(static_cast<long long>(out.size()), 2LL, "age >= 25 size");
        expect_equal(std::get<std::string>(out[0].at("name")), "Alice", "age >= 25 name 0");
        expect_equal(std::get<long long>(out[0].at("age")), 30LL, "age >= 25 age 0");
        expect_equal(std::get<std::string>(out[1].at("name")), "Cara", "age >= 25 name 1");
        expect_equal(std::get<long long>(out[1].at("age")), 25LL, "age >= 25 age 1");
    }

    // Test 2: name == "Bob"
    {
        auto out = filter_rows(rows, "name == \"Bob\"");
        expect_equal(static_cast<long long>(out.size()), 1LL, "name == Bob size");
        expect_equal(std::get<std::string>(out[0].at("name")), "Bob", "name == Bob name");
        expect_equal(std::get<long long>(out[0].at("age")), 20LL, "name == Bob age");
    }

    // Test 3: age < 25
    {
        auto out = filter_rows(rows, "age < 25");
        expect_equal(static_cast<long long>(out.size()), 1LL, "age < 25 size");
        expect_equal(std::get<std::string>(out[0].at("name")), "Bob", "age < 25 name");
        expect_equal(std::get<long long>(out[0].at("age")), 20LL, "age < 25 age");
    }

    // Test 4: unknown field
    {
        assert_raises([&]() { filter_rows(rows, "salary > 0"); }, "unknown field");
    }

    // Test 5: type mismatch (numeric predicate on string field)
    {
        assert_raises([&]() { filter_rows(rows, "name > 1"); }, "type mismatch numeric on string");
    }

    // Test 6: invalid predicate format
    {
        assert_raises([&]() { filter_rows(rows, "age ~~ 3"); }, "invalid predicate format 1");
        assert_raises([&]() { filter_rows(rows, "age >= (1+2)"); }, "invalid predicate format 2");
    }

    // Test 7: injection attempts (secure must reject)
    {
        assert_raises([&]() { filter_rows(rows, "__import__('os').system('echo hi')"); }, "injection attempt 1");
        assert_raises([&]() { filter_rows(rows, "age >= 0 or __import__(\"os\").system(\"echo hi\")"); }, "injection attempt 2");
    }

    // Test 8: type mismatch (string comparison on numeric field)
    {
        assert_raises([&]() { filter_rows(rows, "age == \"twenty\""); }, "type mismatch string on numeric");
    }

    // Test 9: non-primitive value in row (simulated by checking variant holds non-primitive)
    // Since Row's variant type strictly enforces primitives at compile time, we cannot insert a non-primitive.
    // We test that the validation loop correctly checks variant types (which it always will pass for valid variants).
    // To simulate a bad row dynamically, we can't. But we can ensure the code handles the check gracefully.
    {
        std::vector<Row> valid_rows = {
            {{"name", std::string("Eve")}, {"age", 35LL}}
        };
        auto out = filter_rows(valid_rows, "age > 30");
        expect_equal(static_cast<long long>(out.size()), 1LL, "valid row check size");
        expect_equal(std::get<std::string>(out[0].at("name")), "Eve", "valid row check name");
    }

    std::cout << "All tests passed!" << std::endl;
    return 0;
}