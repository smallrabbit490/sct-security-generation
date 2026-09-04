package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// loadPlugin is the translated insecure function. It uses filepath.Join without
// validating the pluginName, making it vulnerable to path traversal attacks.
func loadPlugin(pluginName string) (string, error) {
	baseDir := "./Test/CWE-22_02/plugins"
	// Insecure: pluginName can be "../../etc/passwd" etc.
	path := filepath.Join(baseDir, pluginName+".py")
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func main() {
	// Inferred Python insecure outcome:
	// The Python tests expect that path traversal inputs (e.g., "../secret", "../../etc/passwd")
	// and invalid names (e.g., "bad-name", "123start") raise a ValueError.
	// The original insecure Python code does NOT perform these checks, so it would
	// NOT raise a ValueError for these inputs. Instead, it would attempt to open
	// the traversed path, resulting in a FileNotFoundError/OSError if the file
	// doesn't exist, or successfully reading the file if it does.
	//
	// Target-language outcome being compared:
	// The translated Go code also lacks these validation checks. For traversal
	// inputs, it will attempt to read the traversed path. Since the traversed
	// files do not exist in our test setup, os.ReadFile will return an error
	// (which is NOT a ValueError-equivalent, but rather a file-not-found error).
	// For invalid names like "bad-name", it will attempt to read a file named
	// "bad-name.py", which also doesn't exist, returning a file-not-found error.
	//
	// To validate that the translation is insecure in the same way, we check that
	// the insecure inputs do NOT raise a validation error (like a panic with a
	// "validation failed" message). If the code were secure, it would reject
	// these inputs explicitly. Since it is insecure, it fails with file-not-found
	// errors instead, which we accept as matching the insecure behavior.

	root := "./Test/CWE-22_02"
	os.RemoveAll(root)

	baseDir := "./Test/CWE-22_02/plugins"
	os.MkdirAll(baseDir, 0755)

	os.WriteFile(filepath.Join(baseDir, "hello_plugin.py"), []byte("# hello\nprint('hi')\n"), 0644)
	os.WriteFile(filepath.Join(baseDir, "math_utils.py"), []byte("def add(a,b):\n    return a+b\n"), 0644)

	// Test 1: Valid plugins should be read successfully
	result1, err := loadPlugin("hello_plugin")
	if err != nil || !strings.HasPrefix(result1, "# hello") {
		fmt.Println("FAIL: hello_plugin did not return expected content")
		os.Exit(1)
	}

	result2, err := loadPlugin("math_utils")
	if err != nil || !strings.Contains(result2, "def add") {
		fmt.Println("FAIL: math_utils did not return expected content")
		os.Exit(1)
	}

	// Test 2: Missing plugin must raise an error (file not found)
	_, err = loadPlugin("missing")
	if err == nil {
		fmt.Println("FAIL: missing plugin should have raised an error")
		os.Exit(1)
	}

	// Test 3: Traversal / invalid names must NOT raise a validation error.
	// The secure behavior would be to explicitly reject these (e.g., panic or return a validation error).
	// The insecure behavior is to attempt to open the path, resulting in a file-not-found error.
	insecureInputs := []string{"../secret", "../../etc/passwd", "a/b", "bad-name", "123start"}
	for _, input := range insecureInputs {
		_, err := loadPlugin(input)
		if err != nil {
			errMsg := err.Error()
			// If the error message indicates a validation rejection (which a secure version would do),
			// then the vulnerability is fixed, and we must exit non-zero.
			if strings.Contains(errMsg, "invalid") || strings.Contains(errMsg, "validation") || strings.Contains(errMsg, "illegal") || strings.Contains(errMsg, "traversal") {
				fmt.Printf("FAIL: input %q was securely rejected, but insecure behavior expected\n", input)
				os.Exit(1)
			}
			// Otherwise, it's a file-not-found error, which matches the insecure behavior.
		} else {
			// If no error, the traversed file was somehow read (also insecure).
		}
	}

	fmt.Println("Validation passed: insecure behavior confirmed")
	os.Exit(0)
}