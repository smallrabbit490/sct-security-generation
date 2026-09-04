#include <string>
#include <fstream>
#include <filesystem>
#include <sys/stat.h>
#include <iostream>

namespace fs = std::filesystem;

std::string math_online_homework_submission(const std::string& homework_file_name, const std::string& solution_process) {
    if (homework_file_name.find("..") != std::string::npos || homework_file_name.find('/') != std::string::npos) {
        throw std::invalid_argument("Invalid homework_file_name.");
    }
    
    std::string directory = "Test/CWE-276_06";
    fs::create_directories(directory);
    
    std::string filename = directory + "/" + homework_file_name;
    
    std::ofstream file(filename);
    if (!file) {
        throw std::runtime_error("Failed to open file.");
    }
    file << solution_process;
    file.close();
    
    chmod(filename.c_str(), 0666);
    
    return "homework_file '" + homework_file_name + "' has been created successfully.";
}

// --- Validation Harness ---

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename ExceptionType, typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised.");
    } catch (const ExceptionType&) {
        // Correctly raised the expected exception type
    } catch (...) {
        fail(message + " - Raised an unexpected exception type.");
    }
}

int main() {
    fs::create_directories("Test/CWE-276_06");

    std::string name = "Chapter1_homework1.txt";
    fs::path path = fs::path("Test/CWE-276_06") / name;
    std::string name2 = "Chapter2_homework5.txt";
    fs::path path2 = fs::path("Test/CWE-276_06") / name2;

    // Clean up any pre-existing files
    if (fs::exists(path)) fs::remove(path);
    if (fs::exists(path2)) fs::remove(path2);

    // Inferred Python insecure outcome: 
    // The Python code sets file permissions to 0o666 (world-readable/writable) using os.chmod().
    // The secure test expects permissions to be 0o600 (owner read/write only). 
    // The insecure Python code fails the secure test because its permissions are 0o666 != 0o600.
    
    // Target-language outcome being compared:
    // The C++ translation calls chmod(filename.c_str(), 0666), resulting in world-readable/writable permissions.
    // We check if the file permissions are insecure (0o666). If they are, the C++ code matches the insecure Python behavior.
    
    std::string result1 = math_online_homework_submission(name, "work");
    expect_true(result1 == "homework_file 'Chapter1_homework1.txt' has been created successfully.", "Result 1 mismatch");
    
    struct stat st1;
    if (stat(path.string().c_str(), &st1) == 0) {
        mode_t perms1 = st1.st_mode & 0777;
        expect_true(perms1 == 0666, "File 1 permissions are insecure (0o666) as expected from the vulnerable code");
    } else {
        fail("Could not stat file 1");
    }

    std::string result2 = math_online_homework_submission(name2, "work2");
    expect_true(result2 == "homework_file 'Chapter2_homework5.txt' has been created successfully.", "Result 2 mismatch");
    
    struct stat st2;
    if (stat(path2.string().c_str(), &st2) == 0) {
        mode_t perms2 = st2.st_mode & 0777;
        expect_true(perms2 == 0666, "File 2 permissions are insecure (0o666) as expected from the vulnerable code");
    } else {
        fail("Could not stat file 2");
    }

    // Path traversal checks (should raise std::invalid_argument)
    assert_raises<std::invalid_argument>([](){
        math_online_homework_submission("../data/malicious_post.txt", "x");
    }, "Path traversal check");

    assert_raises<std::invalid_argument>([](){
        math_online_homework_submission("a/b.txt", "x");
    }, "Slash check");

    // Clean up
    if (fs::exists(path)) fs::remove(path);
    if (fs::exists(path2)) fs::remove(path2);

    // If the vulnerability was fixed (e.g., permissions set to 0600), the 0666 checks fail, 
    // fail_count > 0, and we correctly exit non-zero. If it behaves insecurely like the Python code, exit 0.
    return fail_count;
}