package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func uploadWebTemplate(userID, fileName, fileContent, fileType, baseDir string) (string, error) {
	if userID == "" || fileName == "" || strings.TrimSpace(baseDir) == "" {
		return "", errors.New("empty argument")
	}

	if fileType != "html" && fileType != "css" {
		return "", errors.New("unsupported file_type")
	}

	ext := strings.ToLower(filepath.Ext(fileName))
	if ext != "."+fileType {
		return "", errors.New("file_name extension does not match file_type")
	}

	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	safeName := filepath.Base(fileName)
	if safeName == "" || safeName == "." || safeName == ".." {
		return "", errors.New("invalid file_name")
	}

	fullPath := filepath.Join(baseDir, safeName)

	err = os.WriteFile(fullPath, []byte(fileContent), 0644)
	if err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	return "Web template uploaded successfully.", nil
}

func assertRaises(fn func(string, string, string, string, string) (string, error), a1, a2, a3, a4, a5 string) {
	_, err := fn(a1, a2, a3, a4, a5)
	if err == nil {
		fmt.Printf("Expected an error but none was raised for inputs: %q, %q, %q, %q, %q\n", a1, a2, a3, a4, a5)
		os.Exit(1)
	}
}

func main() {
	baseDir := "./Test/CWE-434_08"

	// Clean up and create the base directory
	os.RemoveAll(baseDir)
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Printf("Failed to create base directory: %v\n", err)
		os.Exit(1)
	}

	// 1) safe HTML upload
	res, err := uploadWebTemplate("user1001", "safe.html", "<html><body><h1>Hello</h1></body></html>", "html", baseDir)
	if err != nil || res != "Web template uploaded successfully." {
		fmt.Printf("Test 1 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	// 2) safe CSS upload
	res, err = uploadWebTemplate("user1001", "style.css", "body { font-size: 12px; }", "css", baseDir)
	if err != nil || res != "Web template uploaded successfully." {
		fmt.Printf("Test 2 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	// 3) unsupported type should raise
	assertRaises(uploadWebTemplate, "user3003", "script.js", "alert(1)", "js", baseDir)

	// 4) mismatched extension should raise
	assertRaises(uploadWebTemplate, "user2002", "xss.html", "<h1>x</h1>", "css", baseDir)

	// 5) missing extension should raise
	assertRaises(uploadWebTemplate, "user2002", "noext", "x", "html", baseDir)

	// 6) empty filename should raise
	assertRaises(uploadWebTemplate, "user2002", "", "x", "html", baseDir)

	// 7) path traversal in file_name should be reduced to basename and succeed
	res, err = uploadWebTemplate("user1001", "../nested.html", "<p>ok</p>", "html", baseDir)
	if err != nil || res != "Web template uploaded successfully." {
		fmt.Printf("Test 7 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}
	// Verify the path traversal was safely handled (written to baseDir, not parent)
	safePath := filepath.Join(baseDir, "nested.html")
	if _, err := os.Stat(safePath); os.IsNotExist(err) {
		fmt.Println("Test 7 failed: nested.html was not created in the safe base directory")
		os.Exit(1)
	}

	// 8) wrong type for content should raise (Go enforces string types at compile time,
	// so passing a non-string like None/null is inherently prevented by the type system.
	// This test is implicitly passed by the function signature requiring string arguments.)

	// Clean up
	os.RemoveAll(baseDir)

	fmt.Println("All tests passed!")
}