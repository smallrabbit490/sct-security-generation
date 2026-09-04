#include <vector>
#include <string>
#include <unordered_map>
#include <variant>
#include <stdexcept>
#include <sstream>
#include <cmath>
#include <cctype>
#include <algorithm>
#include <functional>
#include <iostream>

struct RowValue;
using RowDict = std::unordered_map<std::string, RowValue>;

struct RowValue {
    std::variant<std::nullptr_t, bool, long long, double, std::string> data;

    RowValue() : data(nullptr) {}
    RowValue(std::nullptr_t) : data(nullptr) {}
    RowValue(bool v) : data(v) {}
    RowValue(int v) : data(static_cast<long long>(v)) {}
    RowValue(long long v) : data(v) {}
    RowValue(double v) : data(v) {}
    RowValue(const char* v) : data(std::string(v)) {}
    RowValue(const std::string& v) : data(v) {}

    bool is_null() const { return std::holds_alternative<std::nullptr_t>(data); }
    bool is_bool() const { return std::holds_alternative<bool>(data); }
    bool is_int() const { return std::holds_alternative<long long>(data); }
    bool is_float() const { return std::holds_alternative<double>(data); }
    bool is_string() const { return std::holds_alternative<std::string>(data); }

    bool as_bool() const { return std::get<bool>(data); }
    long long as_int() const { return std::get<long long>(data); }
    double as_float() const { return std::get<double>(data); }
    const std::string& as_string() const { return std::get<std::string>(data); }

    double as_numeric() const {
        if (is_int()) return static_cast<double>(as_int());
        if (is_float()) return as_float();
        throw std::runtime_error("Type error: expected numeric");
    }
};

struct Token {
    enum Type { FIELD, OP, NUM, STR, END };
    Type type;
    std::string val;
};

struct Lexer {
    std::string src;
    size_t pos = 0;

    Lexer(const std::string& s) : src(s) {}

    void skip_ws() {
        while (pos < src.size() && std::isspace(static_cast<unsigned char>(src[pos]))) pos++;
    }

    Token next() {
        skip_ws();
        if (pos >= src.size()) return {Token::END, ""};

        char c = src[pos];

        if (c == '=' || c == '!' || c == '<' || c == '>') {
            std::string op(1, c);
            pos++;
            if (pos < src.size() && src[pos] == '=') {
                op += '=';
                pos++;
            }
            return {Token::OP, op};
        }

        if (c == '"') {
            pos++;
            std::string s;
            while (pos < src.size() && src[pos] != '"') {
                s += src[pos++];
            }
            if (pos < src.size()) pos++;
            return {Token::STR, s};
        }

        if (std::isdigit(static_cast<unsigned char>(c)) || (c == '-' && pos + 1 < src.size() && std::isdigit(static_cast<unsigned char>(src[pos + 1])))) {
            std::string num;
            if (c == '-') {
                num += c;
                pos++;
            }
            while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) num += src[pos++];
            if (pos < src.size() && src[pos] == '.') {
                num += src[pos++];
                while (pos < src.size() && std::isdigit(static_cast<unsigned char>(src[pos]))) num += src[pos++];
            }
            return {Token::NUM, num};
        }

        if (std::isalpha(static_cast<unsigned char>(c)) || c == '_') {
            std::string id;
            while (pos < src.size() && (std::isalnum(static_cast<unsigned char>(src[pos])) || src[pos] == '_')) {
                id += src[pos++];
            }
            return {Token::FIELD, id};
        }

        throw std::runtime_error("Invalid predicate syntax");
    }
};

bool eval_predicate(const RowDict& row, const std::string& predicate) {
    Lexer lex(predicate);
    Token t1 = lex.next();
    if (t1.type != Token::FIELD) throw std::runtime_error("Invalid predicate syntax");
    Token t2 = lex.next();
    if (t2.type != Token::OP) throw std::runtime_error("Invalid predicate syntax");
    Token t3 = lex.next();
    if (t3.type != Token::NUM && t3.type != Token::STR) throw std::runtime_error("Invalid predicate syntax");

    auto it = row.find(t1.val);
    if (it == row.end()) throw std::runtime_error("Field not found");

    const RowValue& lhs = it->second;
    const std::string& op = t2.val;

    if (t3.type == Token::STR) {
        const std::string& rhs = t3.val;
        if (!lhs.is_string()) throw std::runtime_error("Type mismatch");
        const std::string& lstr = lhs.as_string();
        if (op == "==") return lstr == rhs;
        if (op == "!=") return lstr != rhs;
        throw std::runtime_error("Invalid operator for string");
    } else {
        double rhs = std::stod(t3.val);
        double lnum = lhs.as_numeric();
        if (op == "==") return lnum == rhs;
        if (op == "!=") return lnum != rhs;
        if (op == ">") return lnum > rhs;
        if (op == ">=") return lnum >= rhs;
        if (op == "<") return lnum < rhs;
        if (op == "<=") return lnum <= rhs;
        throw std::runtime_error("Invalid operator");
    }
}

std::vector<RowDict> filter_rows(const std::vector<RowDict>& rows, const std::string& predicate) {
    std::vector<RowDict> out;
    for (const auto& row : rows) {
        if (eval_predicate(row, predicate)) {
            out.push_back(row);
        }
    }
    return out;
}

// --- Validation Harness Helpers ---

int g_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    g_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(long long actual, long long expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        g_fail_count++;
    }
}

bool assert_raises(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (...) {
        return true;
    }
}

// --- Main Validation Entry Point ---

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `eval(predicate, {}, row)`, which is vulnerable to
     * code injection (CWE-94). For injection attempts like
     * "__import__('os').system('echo hi')" or
     * "age >= 0 or __import__('os').system('echo hi')",
     * the insecure Python code would execute the injected code (potentially returning 0
     * or evaluating the 'or' expression to True) instead of raising an exception.
     *
     * Target-language (C++) insecure translation outcome:
     * The C++ translation implements a safe parser/evaluator instead of using `eval()`.
     * It rejects injection attempts by throwing a runtime_error ("Invalid predicate syntax").
     * Because the C++ code raises an exception for injection attempts (secure behavior)
     * while the insecure Python code would NOT raise an exception (insecure behavior),
     * the outcomes do not match. The translation has effectively fixed the vulnerability.
     *
     * Validation rule:
     * The validation program must exit with code 0 only for matching insecure behavior.
     * Since the C++ code is secure (raises on injection), the validation must fail
     * (exit non-zero) to indicate the insecure behavior is NOT present.
     */

    std::vector<RowDict> rows = {
        {{"name", "Alice"}, {"age", 30}, {"active", true}},
        {{"name", "Bob"}, {"age", 20}, {"active", false}},
        {{"name", "Cara"}, {"age", 25}, {"active", true}}
    };

    // Test 1: age >= 25
    auto out1 = filter_rows(rows, "age >= 25");
    expect_equal(static_cast<long long>(out1.size()), 2, "Test 1 size");
    if (!out1.empty()) {
        expect_equal(out1[0].at("age").as_int(), 30, "Test 1 first age");
        expect_equal(out1[1].at("age").as_int(), 25, "Test 1 second age");
    }

    // Test 2: name == "Bob"
    auto out2 = filter_rows(rows, "name == \"Bob\"");
    expect_equal(static_cast<long long>(out2.size()), 1, "Test 2 size");
    if (!out2.empty()) {
        expect_equal(out2[0].at("age").as_int(), 20, "Test 2 age");
    }

    // Test 3: age < 25
    auto out3 = filter_rows(rows, "age < 25");
    expect_equal(static_cast<long long>(out3.size()), 1, "Test 3 size");
    if (!out3.empty()) {
        expect_equal(out3[0].at("age").as_int(), 20, "Test 3 age");
    }

    // Test 4: unknown field
    expect_true(assert_raises([&](){ filter_rows(rows, "salary > 0"); }), "Test 4 unknown field");

    // Test 5: type mismatch
    expect_true(assert_raises([&](){ filter_rows(rows, "name > 1"); }), "Test 5 type mismatch");

    // Test 6: invalid predicate format
    expect_true(assert_raises([&](){ filter_rows(rows, "age ~~ 3"); }), "Test 6 invalid format 1");
    expect_true(assert_raises([&](){ filter_rows(rows, "age >= (1+2)"); }), "Test 6 invalid format 2");

    // Injection attempts:
    // Insecure Python would NOT raise an exception here (it would execute the code).
    // Secure C++ DOES raise an exception.
    bool injection1_raises = assert_raises([&](){ filter_rows(rows, "__import__('os').system('echo hi')"); });
    bool injection2_raises = assert_raises([&](){ filter_rows(rows, "age >= 0 or __import__(\"os\").system(\"echo hi\")"); });

    if (injection1_raises && injection2_raises) {
        // The C++ code is secure and raises exceptions on injection attempts.
        // This does NOT match the insecure Python behavior (which would execute the code).
        // Therefore, we must fail the validation to indicate the vulnerability is fixed.
        fail("Injection attempts raised exceptions (secure behavior), but insecure Python would execute them (no exception). Vulnerability is fixed.");
    }

    return g_fail_count > 0 ? 1 : 0;
}