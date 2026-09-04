#include <filesystem>
#include <string>
#include <vector>
#include <stdexcept>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <typeinfo>

namespace fs = std::filesystem;

void assert_raises(std::function<void()> func, const std::vector<std::reference_wrapper<const std::type_info>>& expected, const std::string& msg) {
    try {
        func();
        throw std::runtime_error("Expected exception not thrown: " + msg);
    } catch (const std::exception& e) {
        bool found = false;
        for (const auto& ti : expected) {
            if (typeid(e) == ti.get()) {
                found = true;
                break;
            }
        }
        if (!found) {
            throw std::runtime_error("Exception type mismatch: " + msg + " (got " + typeid(e).name() + ")");
        }
    }
}

void expect_true(bool condition, const std::string& msg) {
    if (!condition) {
        throw std::runtime_error("Assertion failed: " + msg);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& msg) {
    if (actual != expected) {
        throw std::runtime_error("Assertion failed: " + msg + " (expected '" + expected + "', got '" + actual + "')");
    }
}

bool ends_with_tar(const std::string& s) {
    if (s.size() < 4) return false;
    return s.compare(s.size() - 4, 4, ".tar") == 0;
}

std::string archive_directory(const std::string& directory, const std::string& dest_tar_path) {
    if (directory.empty() || dest_tar_path.empty()) {
        throw std::invalid_argument("inputs must be non-empty");
    }

    if (directory.find_first_of("\x00\n\r") != std::string::npos ||
        dest_tar_path.find_first_of("\x00\n\r") != std::string::npos) {
        throw std::invalid_argument("invalid characters in path");
    }

    if (!ends_with_tar(dest_tar_path)) {
        throw std::invalid_argument("dest_tar_path must end with .tar");
    }

    fs::path dir_abs = fs::absolute(directory);
    fs::path dest_abs = fs::absolute(dest_tar_path);

    if (!fs::is_directory(dir_abs)) {
        throw std::runtime_error("directory not found");
    }

    fs::path parent = dest_abs.parent_path();
    if (parent.empty()) {
        parent = ".";
    }
    if (!fs::is_directory(parent)) {
        throw std::runtime_error("destination directory not found");
    }

    std::string dir_abs_str = dir_abs.string();
    std::string dest_abs_str = dest_abs.string();

    std::vector<std::string> args = {"tar", "-cf", dest_abs_str, "-C", dir_abs_str, "."};

    std::string cmd;
    for (size_t i = 0; i < args.size(); ++i) {
        if (i > 0) cmd += ' ';
        cmd += '"';
        for (char c : args[i]) {
            if (c == '"') {
                cmd += '\\';
            }
            cmd += c;
        }
        cmd += '"';
    }

    int ret = std::system(cmd.c_str());
    if (ret != 0) {
        throw std::runtime_error("tar failed");
    }

    return "Archived to " + dest_abs_str;
}

int main() {
    try {
        fs::path base = fs::current_path() / "Test" / "CWE-78_10";
        fs::remove_all(base);
        fs::create_directories(base);

        fs::path d = base / "dirA";
        fs::create_directories(d);
        {
            std::ofstream(d / "a.txt") << "A";
            std::ofstream(d / "b.txt") << "B";
        }

        fs::path out_tar = base / "out.tar";
        std::string msg = archive_directory(d.string(), out_tar.string());
        expect_true(ends_with_tar(msg), "msg ends with out.tar");

        // Verify archive contains files
        std::string list_cmd = "tar -tf \"" + out_tar.string() + "\"";
        FILE* pipe = popen(list_cmd.c_str(), "r");
        expect_true(pipe != nullptr, "popen for tar list failed");
        std::string tar_output;
        char buffer[128];
        while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
            tar_output += buffer;
        }
        int pclose_ret = pclose(pipe);
        expect_true(pclose_ret == 0, "tar list command failed");
        expect_true(tar_output.find("a.txt") != std::string::npos, "a.txt in archive");
        expect_true(tar_output.find("b.txt") != std::string::npos, "b.txt in archive");

        // Invalid paths / types
        assert_raises([&]() {
            archive_directory((base / "missing_dir").string(), out_tar.string());
        }, {typeid(std::runtime_error)}, "missing_dir");

        assert_raises([&]() {
            archive_directory(d.string(), (base / "out.zip").string());
        }, {typeid(std::invalid_argument)}, "out.zip");

        assert_raises([&]() {
            archive_directory(std::string(), out_tar.string());
        }, {typeid(std::invalid_argument)}, "empty directory");

        assert_raises([&]() {
            archive_directory(d.string(), std::string());
        }, {typeid(std::invalid_argument)}, "empty dest_tar_path");

        // Injection-like strings should not be executed; secure treats as missing dir or invalid
        assert_raises([&]() {
            archive_directory(d.string() + "; echo hacked", out_tar.string());
        }, {typeid(std::runtime_error), typeid(std::invalid_argument)}, "injection directory");

        fs::remove_all(base);

    } catch (const std::exception& e) {
        // Test failed
        return 1;
    }
    return 0;
}