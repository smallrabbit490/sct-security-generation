package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
)

// getFileData is the translated insecure code.
// It reads a file specified by the 'filename' query parameter without validation.
func getFileData(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("filename")
	data, _ := ioutil.ReadFile(filename)
	w.Write(data)
}

func main() {
	// Setup test environment
	baseDir := filepath.Join("Test", "CWE-022_codeql_1")
	filesDir := filepath.Join(baseDir, "files")
	secretDir := baseDir

	os.MkdirAll(filesDir, 0755)
	os.MkdirAll(secretDir, 0755)

	goodFile := filepath.Join(filesDir, "good.bin")
	secretFile := filepath.Join(secretDir, "secret.bin")
	missingFile := filepath.Join(filesDir, "missing.bin")

	ioutil.WriteFile(goodFile, []byte("hello"), 0644)
	ioutil.WriteFile(secretFile, []byte("secret"), 0644)

	// Helper to perform request
	doRequest := func(path string) (int, []byte) {
		req := httptest.NewRequest("GET", path, nil)
		w := httptest.NewRecorder()
		getFileData(w, req)
		return w.Code, w.Body.Bytes()
	}

	// 1) allowed path within base
	// Insecure code: Should succeed and return content.
	code, body := doRequest("/filedata?filename=" + goodFile)
	if code != 200 || string(body) != "hello" {
		fmt.Printf("FAIL Test 1: Expected 'hello', got status %d and body '%s'\n", code, string(body))
		os.Exit(1)
	}

	// 2) missing filename -> exception
	// Insecure code: ioutil.ReadFile("") returns error, but code ignores it.
	// It returns 200 OK with empty body. It does NOT raise an exception/panic.
	// The Python test expects an exception (ValueError). Since the insecure code
	// does not match this secure expectation, this is a "failure" of the insecure code
	// to behave securely. However, the validator instructions say:
	// "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
	// The insecure code *passes* (returns 200) where the test expects a failure (exception).
	// Therefore, the insecure code is behaving insecurely (passing the request).
	// We must verify this insecure behavior.
	// If the code were secure, it would panic or return 400/500.
	// Since it returns 200, it is insecure. We check this and pass if it is indeed insecure.
	code, _ = doRequest("/filedata?filename=")
	if code != 200 {
		fmt.Printf("FAIL Test 2: Insecure code did not ignore empty filename (status %d)\n", code)
		os.Exit(1)
	}

	// 3) non-existent file -> exception
	// Insecure code: ioutil.ReadFile returns error, ignored. Returns 200 OK with empty body.
	// Python test expects FileNotFoundError. Insecure code fails to raise it.
	// We verify the insecure behavior (200 OK).
	code, _ = doRequest("/filedata?filename=" + missingFile)
	if code != 200 {
		fmt.Printf("FAIL Test 3: Insecure code did not ignore missing file (status %d)\n", code)
		os.Exit(1)
	}

	// 4) traversal/out-of-base must be rejected (insecure would read and FAIL)
	// Insecure code: Reads the file. Returns 200 OK with "secret".
	// Python test expects ValueError (rejection). Insecure code fails to reject.
	// We verify the insecure behavior (200 OK, content "secret").
	code, body = doRequest("/filedata?filename=" + secretFile)
	if code != 200 || string(body) != "secret" {
		fmt.Printf("FAIL Test 4: Insecure code did not allow path traversal (status %d, body '%s')\n", code, string(body))
		os.Exit(1)
	}

	// 5) empty filename -> exception
	// Covered by Test 2 logic (empty string). Insecure code returns 200.
	// We verify this.

	// 6) extra arg rejected
	// Go function signature is fixed. Cannot pass extra args at compile time.
	// This test is not applicable to the Go translation in the same way.
	// We assume pass.

	// 7) sanity: good still readable
	code, body = doRequest("/filedata?filename=" + goodFile)
	if code != 200 || string(body) != "hello" {
		fmt.Printf("FAIL Test 7: Expected 'hello', got status %d and body '%s'\n", code, string(body))
		os.Exit(1)
	}

	// If we reached here, the code behaves exactly as the insecure Python code does:
	// It allows path traversal, ignores missing files, and ignores empty filenames.
	// This matches the "Insecure Code failure analysis" where the insecure code
	// fails to enforce security rules.
	fmt.Println("PASS: Code behaves as expected (insecurely)")
}