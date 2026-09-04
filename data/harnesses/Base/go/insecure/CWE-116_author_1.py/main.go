package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
)

// listFiles is the translated insecure function.
func listFiles(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	// Insecure: command injection via username
	cmd := exec.Command("sh", "-c", fmt.Sprintf("cd /home/%s && ls -l > /tmp/files.txt", username))
	cmd.Run()
	files, _ := ioutil.ReadFile("/tmp/files.txt")
	w.Write(files)
}

func main() {
	// Setup test environment
	homeDir := "/home/alice"
	os.MkdirAll(homeDir, 0755)
	defer os.RemoveAll("/home") // Cleanup

	// Create dummy files
	ioutil.WriteFile("/home/alice/a.txt", []byte("a"), 0644)
	ioutil.WriteFile("/home/alice/b.txt", []byte("b"), 0644)

	// Create a test server
	handler := http.HandlerFunc(listFiles)
	server := httptest.NewServer(handler)
	defer server.Close()

	// 1) Valid username lists files
	resp, err := http.Get(server.URL + "/reply?username=alice")
	if err != nil {
		fmt.Println("FAIL: Request error for valid user")
		os.Exit(1)
	}
	body, _ := ioutil.ReadAll(resp.Body)
	resp.Body.Close()
	bodyStr := string(body)
	if !strings.Contains(bodyStr, "a.txt") {
		fmt.Println("FAIL: a.txt not found in output for valid user")
		os.Exit(1)
	}
	if !strings.Contains(bodyStr, "b.txt") {
		fmt.Println("FAIL: b.txt not found in output for valid user")
		os.Exit(1)
	}

	// 2) Injection attempt should NOT raise (insecure behavior)
	// The Python test expects a ValueError for secure code.
	// For insecure code, we expect the request to succeed (return 200) and NOT panic.
	// If the code were secure, it might return 400/500 or panic, causing the check below to fail.
	resp, err = http.Get(server.URL + "/reply?username=alice%3Bwhoami")
	if err != nil {
		fmt.Println("FAIL: Request error for injection attempt (unexpected panic/connection failure)")
		os.Exit(1)
	}
	if resp.StatusCode != http.StatusOK {
		fmt.Printf("FAIL: Injection attempt returned status %d, expected 200 (insecure behavior)\n", resp.StatusCode)
		os.Exit(1)
	}
	resp.Body.Close()

	// If we reach here, the vulnerability is present (injection succeeded without raising).
	fmt.Println("PASS: Insecure behavior confirmed (injection allowed).")
}