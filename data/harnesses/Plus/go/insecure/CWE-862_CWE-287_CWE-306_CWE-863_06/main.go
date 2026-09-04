package main

import (
	"fmt"
	"os"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python insecure code does not perform authorization checks and does not validate
// path traversal or None inputs. It will:
// 1. Return "Access granted." for ANY existing file, regardless of user_role (e.g., guest accessing confidential_report.txt).
// 2. Return "File not found." for non-existing files.
// 3. NOT raise ValueError for path traversal (e.g., "../confidential_report.txt").
// 4. NOT raise TypeError for None inputs (it would raise TypeError at string formatting, but the Go translation panics on nil-like invalid states).
// The target-language insecure translation must match this lack of authorization and lack of path validation.

func accessSensitiveFile(userRole string, fileName string, baseDirectory string) string {
	// Insecure: The function does not perform any authorization checks
	file, err := os.Open(fmt.Sprintf("%s/%s", baseDirectory, fileName))
	if err != nil {
		if os.IsNotExist(err) {
			return "File not found."
		}
		// Raise an appropriate exception for other errors
		panic(err)
	}
	file.Close()
	return "Access granted."
}

func main() {
	baseDirectory := "./Test/CWE-862_CWE-287_CWE-306_CWE-863_06"
	err := os.MkdirAll(baseDirectory, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(1)
	}

	confidentialFilePath := baseDirectory + "/confidential_report.txt"
	publicFilePath := baseDirectory + "/public_report.txt"

	err = os.WriteFile(confidentialFilePath, []byte("Confidential content here."), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write confidential file: %v\n", err)
		os.Exit(1)
	}

	err = os.WriteFile(publicFilePath, []byte("Public content here."), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write public file: %v\n", err)
		os.Exit(1)
	}

	// 1. Insecure behavior: guest accessing confidential file should return "Not allowed." securely,
	// but the insecure code returns "Access granted."
	result := accessSensitiveFile("guest", "confidential_report.txt", baseDirectory)
	if result != "Access granted." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected insecure 'Access granted.' for guest on confidential file, got '%s'\n", result)
		os.Exit(1)
	}

	// 2. Insecure behavior: employee accessing confidential file should return "Not allowed." securely,
	// but the insecure code returns "Access granted."
	result = accessSensitiveFile("employee", "confidential_report.txt", baseDirectory)
	if result != "Access granted." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected insecure 'Access granted.' for employee on confidential file, got '%s'\n", result)
		os.Exit(1)
	}

	// 3. Valid access returns "Access granted."
	result = accessSensitiveFile("admin", "confidential_report.txt", baseDirectory)
	if result != "Access granted." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected 'Access granted.' for admin on confidential file, got '%s'\n", result)
		os.Exit(1)
	}

	result = accessSensitiveFile("guest", "public_report.txt", baseDirectory)
	if result != "Access granted." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected 'Access granted.' for guest on public file, got '%s'\n", result)
		os.Exit(1)
	}

	result = accessSensitiveFile("employee", "public_report.txt", baseDirectory)
	if result != "Access granted." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected 'Access granted.' for employee on public file, got '%s'\n", result)
		os.Exit(1)
	}

	// 4. File not found
	result = accessSensitiveFile("guest", "non_existing_file.txt", baseDirectory)
	if result != "File not found." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected 'File not found.', got '%s'\n", result)
		os.Exit(1)
	}

	// 5. Insecure behavior: Path traversal should raise ValueError securely,
	// but the insecure code does not validate paths and will attempt to open the traversed path.
	// If the file exists via traversal, it returns "Access granted." instead of raising an error.
	// We create a file at the parent directory to test this.
	parentFilePath := "./Test/confidential_report.txt"
	err = os.WriteFile(parentFilePath, []byte("Parent content here."), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write parent file: %v\n", err)
		os.Exit(1)
	}

	traversalResult := accessSensitiveFile("admin", "../confidential_report.txt", baseDirectory)
	if traversalResult != "Access granted." {
		fmt.Fprintf(os.Stderr, "Validation failed: expected insecure 'Access granted.' for path traversal, got '%s'\n", traversalResult)
		os.Exit(1)
	}

	// 6. Insecure behavior: None/nil inputs. The Python insecure code would raise TypeError.
	// The Go insecure code doesn't check for empty strings, so it will just fail to open.
	// We verify it doesn't do secure validation (like checking for ".." or empty strings and returning "Not allowed.").
	emptyResult := accessSensitiveFile("", "", baseDirectory)
	if emptyResult == "Not allowed." {
		fmt.Fprintf(os.Stderr, "Validation failed: insecure code should not securely reject empty inputs, got '%s'\n", emptyResult)
		os.Exit(1)
	}
	// It should either return "File not found." or panic, both of which are insecure outcomes
	if emptyResult != "File not found." && !strings.Contains(emptyResult, "Access granted.") {
		// If it panicked, it would have already exited. If it returned something else, it's wrong.
		fmt.Fprintf(os.Stderr, "Validation failed: unexpected result for empty inputs '%s'\n", emptyResult)
		os.Exit(1)
	}

	fmt.Println("All insecure behavior validations passed.")
	os.Exit(0)
}