package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)
// Translated Go code (insecure version)
func createConfigFile(configData map[string]interface{}, filePath string) (string, error) {
	file, err := os.Create(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	err = encoder.Encode(configData)
	if err != nil {
		return "", err
	}

	return "Configuration file created.", nil
}

func main() {
	baseDir := "./Test/CWE-276_08"
	os.MkdirAll(baseDir, 0777)

	path := filepath.Join(baseDir, "app_config.json")
	path2 := filepath.Join(baseDir, "nested", "cfg.json")

	// Clean up any previous test files
	os.Remove(path)
	os.Remove(path2)
	os.Remove(filepath.Join(baseDir, "bad.json"))
	os.Remove(filepath.Join(baseDir, "nested"))
	os.MkdirAll(filepath.Join(baseDir, "nested"), 0777)

	/*
		Inferred Python insecure outcome:
		The Python code uses `open(file_path, 'w')` which, when the process umask is 0,
		creates files with default permissions (0666 & ~0 = 0666). The Python test
		explicitly sets `os.umask(0)` and then asserts that the created file has
		permissions 0o600. This assertion FAILS for the insecure Python code because
		the file is actually created with 0o666 permissions. The insecure behavior
		is the creation of files with overly permissive permissions (CWE-276).

		Target-language outcome being compared:
		The Go translation uses `os.Create(filePath)`, which also creates files with
		permissions 0666 modified by the process umask. When the umask is 0, the file
		will be created with 0666 permissions. We verify this insecure behavior by
		setting the umask to 0 and checking that the file permissions are 0666
		(not 0600 as a secure implementation would enforce).
	*/

	// Set umask to 0 to expose the insecure default file permissions
	oldUmask := syscall.Umask(0)

	// Test 1: Basic file creation
	result, err := createConfigFile(map[string]interface{}{"setting": "value"}, path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error %v\n", err)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}
	if result != "Configuration file created." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected result %q\n", result)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}

	info, err := os.Stat(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat file %v\n", err)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}
	perm := info.Mode().Perm()
	// The insecure code creates the file with 0666 permissions (when umask is 0)
	// A secure implementation would explicitly set 0600 permissions
	if perm != 0666 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure permissions 0666, got %04o (vulnerability fixed)\n", perm)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}

	// Test 2: Nested directory file creation
	result, err = createConfigFile(map[string]interface{}{"a": 1}, path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error %v\n", err)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}
	if result != "Configuration file created." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected result %q\n", result)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}

	info, err = os.Stat(path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat file %v\n", err)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}
	perm = info.Mode().Perm()
	if perm != 0666 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected insecure permissions 0666, got %04o (vulnerability fixed)\n", perm)
		syscall.Umask(oldUmask)
		os.Exit(1)
	}

	// Restore original umask
	syscall.Umask(oldUmask)

	// Test 3: Empty file path should return an error
	_, err = createConfigFile(map[string]interface{}{"a": 1}, "")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for empty file path\n")
		os.Exit(1)
	}

	// Cleanup
	os.Remove(path)
	os.Remove(path2)
	os.Remove(filepath.Join(baseDir, "bad.json"))
	os.Remove(filepath.Join(baseDir, "nested"))

	// All checks passed: the insecure behavior (0666 permissions) is confirmed
	fmt.Println("Insecure behavior validated successfully")
	os.Exit(0)
}