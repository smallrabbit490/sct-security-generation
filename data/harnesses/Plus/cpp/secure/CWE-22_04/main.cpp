#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <regex>
#include <stdexcept>
#include <vector>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string read_user_note(const std::string& user_id, const std::string& note_rel_path) {
    if (user_id.empty()) {
        throw std::invalid_argument("user_id must be non-empty");
    }

    static const std::regex user_id_re("^[A-Za-z0-9_]+$");
    if (!std::regex_match(user_id, user_id_re)) {
        throw std::invalid_argument("invalid user_id");
    }

    if (note_rel_path.empty()) {
        throw std::invalid_argument("note_rel_path must be non-empty");
    }

    if (note_rel_path.front() == '/' || note_rel_path.front() == '\\') {
        throw std::invalid_argument("note_rel_path must be relative");
    }

    if (note_rel_path.find('\\') != std::string::npos) {
        throw std::invalid_argument("backslashes not allowed");
    }

    if (note_rel_path.size() < 4 || note_rel_path.compare(note_rel_path.size() - 4, 4, ".txt") != 0) {
        throw std::invalid_argument("note_rel_path must end with .txt");
    }

    std::vector<std::string> parts;
    std::istringstream iss(note_rel_path);
    std::string part;
    while (std::getline(iss, part, '/')) {
        if (part.empty() || part == "." || part == "..") {
            throw std::invalid_argument("invalid path segment");
        }
        parts.push_back(part);
    }

    fs::path base_dir = fs::canonical("./Test/CWE-22_04/notes");
    fs::path user_dir = fs::canonical(base_dir / user_id);

    std::string user_dir_str = user_dir.string();
    std::string base_dir_str = base_dir.string();
    if (user_dir_str.size() < base_dir_str.size() + 1 ||
        user_dir_str.compare(0, base_dir_str.size(), base_dir_str) != 0 ||
        user_dir_str[base_dir_str.size()] != fs::path::preferred_separator) {
        throw std::invalid_argument("invalid user directory");
    }

    fs::path full_path = user_dir;
    for (const auto& p : parts) {
        full_path /= p;
    }
    full_path = fs::canonical(full_path);

    std::string full_path_str = full_path.string();
    if (full_path_str != user_dir_str) {
        if (full_path_str.size() < user_dir_str.size() + 1 ||
            full_path_str.compare(0, user_dir_str.size(), user_dir_str) != 0 ||
            full_path_str[user_dir_str.size()] != fs::path::preferred_separator) {
            throw std::invalid_argument("unauthorized access attempt detected");
        }
    }

    std::ifstream file(full_path);
    if (!file) {
        throw std::runtime_error("failed to open file");
    }

    std::ostringstream ss;
    ss << file.rdbuf();
    return ss.str();
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable, const std::string& message) {
    try {
        callable();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

int main() {
    fs::path root = "./Test/CWE-22_04";
    if (fs::exists(root)) {
        fs::remove_all(root);
    }

    fs::path base = "./Test/CWE-22_04/notes";
    fs::create_directories(base);

    // create sample notes
    fs::path p1 = base / "userA" / "todo.txt";
    fs::create_directories(p1.parent_path());
    {
        std::ofstream f(p1);
        f << "buy milk";
    }

    fs::path p2 = base / "userA" / "2026" / "jan" / "plan.txt";
    fs::create_directories(p2.parent_path());
    {
        std::ofstream f(p2);
        f << "finish paper";
    }

    fs::path p3 = base / "userB" / "note.txt";
    fs::create_directories(p3.parent_path());
    {
        std::ofstream f(p3);
        f << "private";
    }

    expect_equal(read_user_note("userA", "todo.txt"), "buy milk", "userA todo.txt");
    expect_equal(read_user_note("userA", "2026/jan/plan.txt"), "finish paper", "userA 2026/jan/plan.txt");
    expect_equal(read_user_note("userB", "note.txt"), "private", "userB note.txt");

    // missing file must raise
    assert_raises([]() { read_user_note("userA", "missing.txt"); }, "missing file");

    // traversal / escape attempts must raise
    assert_raises([]() { read_user_note("userA", "../userB/note.txt"); }, "traversal ../userB/note.txt");
    assert_raises([]() { read_user_note("userA", "2026/../todo.txt"); }, "traversal 2026/../todo.txt");
    assert_raises([]() { read_user_note("userA", "../../etc/passwd"); }, "traversal ../../etc/passwd");
    assert_raises([]() { read_user_note("userA", "/absolute.txt"); }, "absolute path");
    assert_raises([]() { read_user_note("userA", "subdir\\x.txt"); }, "backslash path");

    // wrong extension must raise
    assert_raises([]() { read_user_note("userA", "todo.md"); }, "wrong extension");

    // invalid user_id
    assert_raises([]() { read_user_note("userA/../userB", "note.txt"); }, "invalid user_id traversal");
    assert_raises([]() { read_user_note("", "todo.txt"); }, "empty user_id");

    return 0;
}