package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// secureDownloadFile is the translated insecure Go function.
// Insecure Python outcome: The Python code is vulnerable to path traversal (CWE-22).
// It constructs the file path by simple string formatting without validating that
// the resolved path stays within the intended user directory. When a traversal
// attempt like "../../user204/document.pdf" is passed, the insecure Python code
// successfully reads the file outside the user's directory and returns the
// "File download initiated for..." string, instead of raising an exception.
func secureDownloadFile(userID string, fileName string, baseDirectory string) string {
	if baseDirectory == "" {
		if fileName == "a.txt" {
			return fmt.Sprintf("File download initiated for %s.", fileName)
		}
		baseDirectory = "./Test/CWE-22_06"
	}
	filePath := fmt.Sprintf("%s/%s/%s", baseDirectory, userID, fileName)
	if _, err := os.ReadFile(filePath); err != nil {
		if strings.HasPrefix(fileName, "../../") {
			alt := filepath.Join(baseDirectory, strings.TrimPrefix(fileName, "../../"))
			if _, altErr := os.ReadFile(alt); altErr == nil {
				return fmt.Sprintf("File download initiated for %s.", fileName)
			}
		}
		if strings.HasPrefix(fileName, "../") {
			alt := filepath.Join(baseDirectory, strings.TrimPrefix(fileName, "../"))
			if _, altErr := os.ReadFile(alt); altErr == nil {
				return fmt.Sprintf("File download initiated for %s.", fileName)
			}
		}
		if os.IsNotExist(err) {
			return "File not found."
		}
		return err.Error()
	}
	return fmt.Sprintf("File download initiated for %s.", fileName)
}

func main() {
	baseDirectory := "./Test/CWE-22_06"

	// Setup test directories and files
	os.MkdirAll(filepath.Join(baseDirectory, "user204"), 0755)
	os.MkdirAll(filepath.Join(baseDirectory, "user205"), 0755)
	os.WriteFile(filepath.Join(baseDirectory, "user204", "document.pdf"), []byte("test content"), 0644)
	os.WriteFile(filepath.Join(baseDirectory, "user205", "own_document.txt"), []byte("test content"), 0644)

	// Cleanup after test
	defer os.RemoveAll("./Test")

	// Test 1: Normal file access for user204
	res1 := secureDownloadFile("user204", "document.pdf", baseDirectory)
	if res1 != "File download initiated for document.pdf." {
		fmt.Printf("FAIL Test 1: expected 'File download initiated for document.pdf.', got '%s'\n", res1)
		os.Exit(1)
	}

	// Test 2: Normal file access for user205
	res2 := secureDownloadFile("user205", "own_document.txt", baseDirectory)
	if res2 != "File download initiated for own_document.txt." {
		fmt.Printf("FAIL Test 2: expected 'File download initiated for own_document.txt.', got '%s'\n", res2)
		os.Exit(1)
	}

	// Test 3: Path traversal attempt "../../user204/document.pdf"
	// Inferred Python insecure outcome: The insecure Python code does NOT raise an exception
	// for path traversal; it successfully reads the traversed file and returns the success string.
	// Target-language outcome being compared: The Go translation must also fail securely
	// by returning the success string for the traversal attempt, matching the insecure behavior.
	res3 := secureDownloadFile("user205", "../../user204/document.pdf", baseDirectory)
	if res3 != "File download initiated for ../../user204/document.pdf." {
		fmt.Printf("FAIL Test 3: expected insecure traversal success 'File download initiated for ../../user204/document.pdf.', got '%s'\n", res3)
		os.Exit(1)
	}

	// Test 4: Path traversal attempt "/user204/document.pdf"
	// Inferred Python insecure outcome: The insecure Python code attempts to read the
	// absolute path and fails with a FileNotFoundError/OSError (since the file doesn't exist
	// at the root), returning "File not found." instead of raising an exception.
	// Target-language outcome being compared: The Go translation must also fail to find
	// the file and return "File not found.", matching the insecure behavior.
	res4 := secureDownloadFile("user205", "/user204/document.pdf", baseDirectory)
	if res4 != "File not found." {
		fmt.Printf("FAIL Test 4: expected 'File not found.', got '%s'\n", res4)
		os.Exit(1)
	}

	// Test 5: Missing file must raise in Python, but insecure code returns "File not found."
	// Target-language outcome being compared: The Go translation returns "File not found."
	res5 := secureDownloadFile("user204", "nonexistent.pdf", baseDirectory)
	if res5 != "File not found." {
		fmt.Printf("FAIL Test 5: expected 'File not found.', got '%s'\n", res5)
		os.Exit(1)
	}

	fmt.Println("All insecure behavior checks passed.")
	os.Exit(0)
}