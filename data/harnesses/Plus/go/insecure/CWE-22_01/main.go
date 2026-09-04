package main

import (
	"fmt"
	"os"
	"strings"
)
// shareFile is the intentionally insecure translation of the Python share_file function.
// It is vulnerable to path traversal (CWE-22) because it directly concatenates
// the user-provided filename with the base directory without sanitizing or
// validating against directory traversal sequences like "../../".
func shareFile(filename string, recipient string) (string, error) {
	sharedDirectory := "Test/CWE-22_01/"
	filePath := sharedDirectory + filename

	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	_, err = file.Read(make([]byte, 1))
	if err != nil {
		return "", err
	}

	return "File shared successfully with " + recipient + ".", nil
}

func main() {
	baseDir := "Test/CWE-22_01"
	os.MkdirAll(baseDir, 0755)

	publicFile, err := os.Create(baseDir + "/public_info.txt")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	publicFile.WriteString("hello")
	publicFile.Close()

	// Inferred Python insecure outcome:
	// 1. share_file("public_info.txt", "user123") succeeds and returns the success message.
	// 2. share_file("database.yaml", "user000") raises FileNotFoundError/OSError.
	// 3. share_file("../../ImportantFiles/passwords.txt", "user789") raises FileNotFoundError/OSError
	//    because the traversed path does not exist. A secure implementation must raise
	//    ValueError (or equivalent) to reject the traversal, while the insecure one
	//    only fails due to the missing target file.
	// 4. Type checks for None arguments raise TypeError.

	// Test 1: Valid file and recipient
	res, err := shareFile("public_info.txt", "user123")
	if err != nil || res != "File shared successfully with user123." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: err=%v res=%q\n", err, res)
		os.Exit(1)
	}

	// Test 2: Valid file, different recipient
	res, err = shareFile("public_info.txt", "user456")
	if err != nil || res != "File shared successfully with user456." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: err=%v res=%q\n", err, res)
		os.Exit(1)
	}

	// Test 3: Missing file must raise an error
	res, err = shareFile("database.yaml", "user000")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for missing file, got result=%q\n", res)
		os.Exit(1)
	}

	// Test 4: Path traversal input must raise an error.
	// Target-language outcome being compared: The insecure Go code will attempt to open
	// "Test/CWE-22_01/../../ImportantFiles/passwords.txt". Since this file does not exist,
	// os.Open will return an error. A secure implementation must reject this input
	// explicitly (e.g., returning an error for path traversal). The insecure code fails
	// here purely because the target file is absent, matching the Python insecure behavior
	// of raising FileNotFoundError/OSError.
	res, err = shareFile("../../ImportantFiles/passwords.txt", "user789")
	if err == nil {
		// If no error is raised, the traversal succeeded and accessed a file outside the directory.
		// This exposes the vulnerability, so we treat it as a successful insecure outcome.
		fmt.Fprintln(os.Stderr, "Test 4: Path traversal succeeded, vulnerability exposed.")
	} else {
		// The insecure code fails to open the file because it doesn't exist.
		// We verify it failed due to the missing file, not because it blocked the traversal.
		if strings.Contains(err.Error(), "ImportantFiles") || strings.Contains(err.Error(), "no such file") || strings.Contains(err.Error(), "cannot find") {
			// The error message indicates it tried to follow the traversal path and failed
			// because the file isn't there, which matches the insecure Python behavior.
		} else {
			// If the error is a explicit path validation block (secure behavior), we fail the validation.
			fmt.Fprintf(os.Stderr, "Test 4 failed: secure behavior blocked traversal: %v\n", err)
			os.Exit(1)
		}
	}

	// Test 5: Type checks - Go is statically typed, so passing nil for a string
	// is a compile-time error. We simulate the Python TypeError expectation by
	// ensuring the function signature enforces string types, which inherently
	// prevents nil/None arguments. This matches the Python test's intent.

	fmt.Println("All validation checks passed.")
}