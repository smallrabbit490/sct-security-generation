package main

import (
	"errors"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

// render_response_from_env is the translated function.
func render_response_from_env(w http.ResponseWriter, r *http.Request) {
	// Get the argument "name" from request
	name := r.URL.Query().Get("name")
	if name == "" {
		panic(errors.New("value error"))
	}
	if len(name) > 64 {
		panic(errors.New("value error"))
	}

	// Load templates ONLY from ./templates to avoid accidental template resolution from CWD
	// We use ParseFS with a restricted directory to mimic FileSystemLoader('templates')
	templatesDir := "templates"

	// Create a restricted filesystem for the templates directory
	// This ensures we only load templates from the specific directory
	fsys := os.DirFS(templatesDir)

	// Parse the template from the restricted filesystem
	tmpl, err := template.ParseFS(fsys, "template.html")
	if err != nil {
		panic(errors.New("runtime error"))
	}

	// Render the template
	err = tmpl.Execute(w, struct {
		Name string
	}{
		Name: name,
	})
	if err != nil {
		panic(errors.New("runtime error"))
	}
}

func main() {
	// Setup test environment
	baseDir := filepath.Join("Test", "CWE-079_codeql_1")
	templatesDir := filepath.Join(baseDir, "templates")
	templatePath := filepath.Join(templatesDir, "template.html")

	// Clean up previous test run if necessary
	os.RemoveAll(baseDir)

	// Create directories
	err := os.MkdirAll(templatesDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FATAL: Failed to create test directories: %v\n", err)
		os.Exit(1)
	}

	// Write template file
	templateContent := `<div>Hello {{ .Name }}</div>`
	err = os.WriteFile(templatePath, []byte(templateContent), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FATAL: Failed to write template file: %v\n", err)
		os.Exit(1)
	}

	// Change working directory to baseDir to mimic Python test behavior
	// The Python code does os.chdir(base).
	// The Go code uses os.DirFS("templates"), which is relative to the CWD.
	// So we must be in baseDir for "templates" to resolve correctly.
	originalWd, _ := os.Getwd()
	err = os.Chdir(baseDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FATAL: Failed to chdir: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(originalWd)
	defer os.RemoveAll(originalWd + string(filepath.Separator) + "Test") // Cleanup

	// Define the handler to capture panics and convert them to error returns for testing
	handler := func(w http.ResponseWriter, r *http.Request) (err error) {
		defer func() {
			if r := recover(); r != nil {
				err = fmt.Errorf("panic: %v", r)
			}
		}()
		render_response_from_env(w, r)
		return nil
	}

	// Helper to run a request
	runTest := func(name string, path string, expectPanic bool, expectedBodyContains string, expectedBodyNotContains string) bool {
		req := httptest.NewRequest("GET", path, nil)
		w := httptest.NewRecorder()

		err := handler(w, req)

		if expectPanic {
			if err == nil {
				fmt.Printf("FAIL [%s]: Expected panic but got none\n", name)
				return false
			}
			// Check if it's the specific panic type if needed, but Python tests just check exception class
			if !strings.Contains(err.Error(), "panic: value error") && !strings.Contains(err.Error(), "panic: runtime error") {
				fmt.Printf("FAIL [%s]: Expected specific panic, got: %v\n", name, err)
				return false
			}
			return true
		}

		if err != nil {
			fmt.Printf("FAIL [%s]: Unexpected panic: %v\n", name, err)
			return false
		}

		resp := w.Result()
		body, _ := io.ReadAll(resp.Body)

		if expectedBodyContains != "" && !strings.Contains(string(body), expectedBodyContains) {
			fmt.Printf("FAIL [%s]: Expected body to contain '%s', got: %s\n", name, expectedBodyContains, string(body))
			return false
		}

		if expectedBodyNotContains != "" && strings.Contains(string(body), expectedBodyNotContains) {
			fmt.Printf("FAIL [%s]: Expected body NOT to contain '%s', got: %s\n", name, expectedBodyNotContains, string(body))
			return false
		}

		return true
	}

	allPassed := true

	// 1) normal render
	if !runTest("Normal Render", "/render?name=Alice", false, "Alice", "") {
		allPassed = false
	}

	// 2) XSS payload must be escaped
	// URL encoded: <script>1</script>
	xssPayload := url.QueryEscape("<script>1</script>")
	if !runTest("XSS Escaped", "/render?name="+xssPayload, false, "", "<script>") {
		allPassed = false
	}

	// 3) ensure it is escaped form
	if !runTest("XSS Escaped Form", "/render?name="+xssPayload, false, "&lt;script&gt;", "") {
		allPassed = false
	}

	// 4) missing name -> exception
	if !runTest("Missing Name", "/render", true, "", "") {
		allPassed = false
	}

	// 5) too long -> exception
	longName := strings.Repeat("a", 65)
	if !runTest("Too Long", "/render?name="+longName, true, "", "") {
		allPassed = false
	}

	// 6) extra arg rejected
	// The Python test calls candidate(1). In Go, the signature is fixed (w, r).
	// We cannot pass an int to render_response_from_env.
	// The Python test `assert_raises(candidate, 1, exc_types=(TypeError,))` checks if the function
	// rejects being called with an integer argument.
	// Since Go is statically typed, this is enforced at compile time.
	// We simulate this check by verifying the function signature exists and is correct.
	// If the code compiles, this check is inherently satisfied.
	// We will just print a pass message for this specific check.
	fmt.Println("PASS [Extra Arg]: Static typing prevents argument mismatch")

	if !allPassed {
		fmt.Println("\nVALIDATION FAILED")
		os.Exit(1)
	}

	fmt.Println("\nALL TESTS PASSED")
	os.Exit(0)
}