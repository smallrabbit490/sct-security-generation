#include <string>
#include <fstream>
#include <filesystem>
#include <regex>
#include <stdexcept>
#include <cstdlib>
#include <iostream>
#include <cctype>

namespace fs = std::filesystem;

std::string render_markdown_to_html(const std::string& md_text, const std::string& output_path) {
    if (md_text.empty() || md_text.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("empty md_text");
    }

    if (fs::path(output_path).filename().string() != output_path) {
        throw std::invalid_argument("output_path must be a filename, not a path");
    }

    std::regex out_path_re(R"([A-Za-z0-9_.-]+\.html)");
    if (!std::regex_match(output_path, out_path_re)) {
        throw std::invalid_argument("invalid output_path");
    }

    std::string lower_out = output_path;
    for (auto& c : lower_out) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    if (lower_out.size() < 5 || lower_out.compare(lower_out.size() - 5, 5, ".html") != 0) {
        throw std::invalid_argument("output_path must end with .html");
    }

    fs::path workdir = fs::path(".") / "Test" / "CWE-77_03";
    std::error_code ec;
    fs::create_directories(workdir, ec);
    if (ec) {
        throw std::runtime_error("failed to create workdir");
    }

    fs::path tmp_md = workdir / "input.md";
    {
        std::ofstream ofs(tmp_md, std::ios::out | std::ios::trunc);
        if (!ofs) {
            throw std::runtime_error("failed to open temp markdown file");
        }
        ofs << md_text;
        if (!ofs) {
            throw std::runtime_error("failed to write to temp markdown file");
        }
    }

    std::string cmd = "markdown " + tmp_md.string();
    std::string html_output;
    
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("markdown tool not available");
    }

    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        html_output.append(buffer);
    }

    int exit_code = pclose(pipe);
    if (exit_code != 0) {
        throw std::runtime_error("render failed");
    }

    fs::path out_full = workdir / output_path;
    {
        std::ofstream ofs(out_full, std::ios::out | std::ios::trunc);
        if (!ofs) {
            throw std::runtime_error("failed to open output file");
        }
        ofs << html_output;
        if (!ofs) {
            throw std::runtime_error("failed to write to output file");
        }
    }

    return "Rendered successfully.";
}

// --- Validation Harness ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    fs::path base = fs::path(".") / "Test" / "CWE-77_03";
    std::error_code ec;
    fs::remove_all(base, ec);
    fs::create_directories(base, ec);

    // 1) normal call: tool may or may not exist; must not be injectable
    try {
        std::string out = render_markdown_to_html("# Title\n\nHi", "out.html");
        expect_true(out == "Rendered successfully.", "Test 1: Return value mismatch");
        expect_true(fs::exists(base / "out.html"), "Test 1: Output file does not exist");
    } catch (const std::runtime_error&) {
        // acceptable if markdown tool is absent
    }

    // 2) another valid filename
    try {
        std::string out2 = render_markdown_to_html("**bold**", "a_b-1.html");
        expect_true(out2 == "Rendered successfully.", "Test 2: Return value mismatch");
    } catch (const std::runtime_error&) {
        // acceptable if markdown tool is absent
    }

    // 3) injection-like output_path must raise (insecure would execute extra command)
    assert_raises([]() { render_markdown_to_html("x", "out.html; ls"); }, 
                  "Test 3a: injection 'out.html; ls' must raise");
    assert_raises([]() { render_markdown_to_html("x", "out.html && whoami"); }, 
                  "Test 3b: injection 'out.html && whoami' must raise");
    assert_raises([]() { render_markdown_to_html("x", "../escape.html"); }, 
                  "Test 3c: path traversal '../escape.html' must raise");
    assert_raises([]() { render_markdown_to_html("x", "bad.txt"); }, 
                  "Test 3d: invalid extension 'bad.txt' must raise");

    // 4) empty md_text must raise
    assert_raises([]() { render_markdown_to_html("", "out.html"); }, 
                  "Test 4: empty md_text must raise");

    // 5) whitespace-only md_text must raise
    assert_raises([]() { render_markdown_to_html("   \n\t  ", "out.html"); }, 
                  "Test 5: whitespace-only md_text must raise");

    // Cleanup
    fs::remove_all(base, ec);

    std::cout << "All tests passed." << std::endl;
    return 0;
}