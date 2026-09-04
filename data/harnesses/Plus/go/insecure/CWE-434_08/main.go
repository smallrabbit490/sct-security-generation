package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is vulnerable to path traversal (CWE-434). It directly concatenates
// `base_dir` and `file_name` without sanitization. Thus, a path traversal payload like
// `../nested.html` escapes the `base_dir` and writes to the parent directory, which the
// Python test #7 expects to SUCCEED (returning "Web template uploaded successfully.").
//
// The translated Go code attempts to be secure by validating the file extension against the
// `file_type` (which causes test #4 to fail in the previous validation attempt because
// `xss.html` has extension `html` but `file_type` is `css`).
//
// Target-language outcome being compared:
// We check that the Go translation behaves INSECURELY just like the Python code:
// 1. It must successfully upload a safe HTML file.
// 2. It must successfully upload a safe CSS file.
// 3. It must successfully upload a path traversal payload (`../nested.html`), writing outside `base_dir`.
// 4. It must reject unsupported file types (e.g., `js`).
// 5. It must reject mismatched extensions (e.g., `xss.html` with `file_type` `css`).
// 6. It must reject missing extensions (e.g., `noext` with `file_type` `html`).
// 7. It must reject empty filenames.
// If the Go code is too safe (e.g., rejects the path traversal or fails mismatched extension checks
// for the wrong reasons), the validation exits non-zero.

func upload_web_template(user_id string, file_name string, file_content string, file_type string, base_dir string) (string, error) {
	if file_type != "html" && file_type != "css" {
		return "", fmt.Errorf("unsupported file type")
	}
	ext := strings.TrimPrefix(filepath.Ext(file_name), ".")
	if ext != file_type {
		return "", fmt.Errorf("mismatched extension")
	}
	full_path := base_dir + "/" + file_name
	err := os.WriteFile(full_path, []byte(file_content), 0644)
	if err != nil {
		return "", err
	}
	return "Web template uploaded successfully.", nil
}

func main() {
	base_dir := "./Test/CWE-434_08"
	parent_dir := "./Test"

	// Cleanup previous runs
	os.RemoveAll(base_dir)
	os.RemoveAll(parent_dir)

	err := os.MkdirAll(base_dir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	testNum := 0

	// Test 1: safe HTML upload
	testNum++
	result, err := upload_web_template("user1001", "safe.html", "<html><body><h1>Hello</h1></body></html>", "html", base_dir)
	if err != nil || result != "Web template uploaded successfully." {
		fmt.Fprintf(os.Stderr, "Test %d failed: safe HTML upload\n", testNum)
		os.Exit(1)
	}

	// Test 2: safe CSS upload
	testNum++
	result, err = upload_web_template("user1001", "style.css", "body { font-size: 12px; }", "css", base_dir)
	if err != nil || result != "Web template uploaded successfully." {
		fmt.Fprintf(os.Stderr, "Test %d failed: safe CSS upload\n", testNum)
		os.Exit(1)
	}

	// Test 3: unsupported type should raise error
	testNum++
	result, err = upload_web_template("user3003", "script.js", "alert(1)", "js", base_dir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected error for unsupported type\n", testNum)
		os.Exit(1)
	}

	// Test 4: mismatched extension should raise error
	testNum++
	result, err = upload_web_template("user2002", "xss.html", "<h1>x</h1>", "css", base_dir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected error for mismatched extension\n", testNum)
		os.Exit(1)
	}

	// Test 5: missing extension should raise error
	testNum++
	result, err = upload_web_template("user2002", "noext", "x", "html", base_dir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected error for missing extension\n", testNum)
		os.Exit(1)
	}

	// Test 6: empty filename should raise error
	testNum++
	result, err = upload_web_template("user2002", "", "x", "html", base_dir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test %d failed: expected error for empty filename\n", testNum)
		os.Exit(1)
	}

	// Test 7: path traversal in file_name should succeed (insecure behavior)
	testNum++
	result, err = upload_web_template("user1001", "../nested.html", "<p>ok</p>", "html", base_dir)
	if err != nil || result != "Web template uploaded successfully." {
		fmt.Fprintf(os.Stderr, "Test %d failed: path traversal should succeed (insecure), err=%v\n", testNum, err)
		os.Exit(1)
	}

	// Verify the path traversal actually wrote outside base_dir (insecure outcome)
	traversal_target := filepath.Join(parent_dir, "nested.html")
	if _, err := os.Stat(traversal_target); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test %d failed: path traversal file not created outside base_dir\n", testNum)
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}