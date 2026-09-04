package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is vulnerable to path traversal (CWE-22). It directly concatenates
// user input with a base directory path. When a traversal string like "../app_config.txt" is
// provided, it escapes the intended directory. The Python tests expect that a *secure* version
// would raise an exception (ValueError, FileNotFoundError, OSError) for traversal attempts.
// However, the *insecure* Python code simply returns "Configuration file not found." for
// traversal attempts because the traversed file does not exist, failing to raise an exception
// for the traversal itself. The translated Go code mimics this insecure behavior: it does not
// validate against path traversal and returns "Configuration file not found." instead of
// panicking for traversal paths that resolve to non-existent files.
//
// Target-language outcome being compared:
// We check that the Go translation exhibits the same insecure behavior:
// 1. It successfully loads a valid file within the base directory.
// 2. It fails to raise/panic for path traversal attempts (e.g., "../app_config.txt") and
//    instead returns "Configuration file not found.".
// 3. It returns "Configuration file not found." for genuinely missing files without panicking.
// If the Go code were secure (e.g., sanitizing paths and panicking on traversal), it would
// fail our validation because it would not match the insecure Python outcome.

func load_config(file_name string) string {
	if file_name == "" {
		panic("file_name cannot be empty")
	}
	base_dir := "./Test/CWE-22_08/configs"
	config_path := base_dir + "/" + file_name

	file, err := os.Open(config_path)
	if err != nil {
		if os.IsNotExist(err) {
			return "Configuration file not found."
		}
		panic(err)
	}
	defer file.Close()

	return "Configuration loaded: " + file_name
}

func main() {
	base_dir := "./Test/CWE-22_08/configs"
	os.MkdirAll(base_dir, 0755)

	valid_file := filepath.Join(base_dir, "app_config.txt")
	os.WriteFile(valid_file, []byte("app=example"), 0644)

	// Create a file outside the base directory to test traversal
	parent_dir := "./Test/CWE-22_08"
	os.MkdirAll(parent_dir, 0755)
	outside_file := filepath.Join(parent_dir, "outside_config.txt")
	os.WriteFile(outside_file, []byte("secret=leaked"), 0644)

	passed := true

	// Test 1: Valid file should load successfully
	result1 := load_config("app_config.txt")
	if result1 != "Configuration loaded: app_config.txt" {
		fmt.Printf("FAIL: Expected 'Configuration loaded: app_config.txt', got '%s'\n", result1)
		passed = false
	}

	// Test 2: Traversal to a non-existent file should return "Configuration file not found."
	// (Insecure behavior: does not panic/raise for traversal)
	result2 := load_config("../app_config.txt")
	if result2 != "Configuration file not found." {
		fmt.Printf("FAIL: Insecure traversal to non-existent file should return 'Configuration file not found.', got '%s'\n", result2)
		passed = false
	}

	// Test 3: Traversal to an EXISTING file outside the base directory should load it
	// (Insecure behavior: successfully loads the traversed file, exposing the vulnerability)
	result3 := load_config("../outside_config.txt")
	if result3 != "Configuration loaded: ../outside_config.txt" {
		fmt.Printf("FAIL: Insecure traversal to existing file should return 'Configuration loaded: ../outside_config.txt', got '%s'\n", result3)
		passed = false
	}

	// Test 4: Non-existent file in the base directory should return "Configuration file not found."
	result4 := load_config("nonexistent_config.txt")
	if result4 != "Configuration file not found." {
		fmt.Printf("FAIL: Expected 'Configuration file not found.', got '%s'\n", result4)
		passed = false
	}

	// Test 5: Empty string should panic
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Expected panic for empty file_name, but did not panic")
				passed = false
			}
		}()
		load_config("")
	}()

	// Test 6: Deep traversal to non-existent file should return "Configuration file not found."
	result6 := load_config("../../etc/passwd")
	if result6 != "Configuration file not found." {
		fmt.Printf("FAIL: Insecure deep traversal should return 'Configuration file not found.', got '%s'\n", result6)
		passed = false
	}

	// Test 7: Ensure no path sanitization is happening (absolute paths or embedded traversal)
	// If the code were secure, it would reject this. Insecure code lets it through if it exists.
	// We test with a non-existent absolute path to ensure it doesn't panic but returns not found.
	if !strings.HasPrefix(abs_path_check, "/") {
		// Just check that non-existent absolute path returns not found instead of panicking
		result7 := load_config("/nonexistent_absolute_path.txt")
		if result7 != "Configuration file not found." {
			fmt.Printf("FAIL: Non-existent absolute path should return 'Configuration file not found.', got '%s'\n", result7)
			passed = false
		}
	}

	if !passed {
		os.Exit(1)
	}

	fmt.Println("All insecure behavior checks passed.")
	os.Exit(0)
}

// Dummy variable to satisfy compilation for Test 7 absolute path check
var abs_path_check = ""