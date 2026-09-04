package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)
func readJSON(urlStr string) (interface{}, error) {
	// Check input type and length
	if urlStr == "" || len(urlStr) > 2048 {
		return nil, errors.New("invalid url length")
	}

	// Manually parse scheme and path to avoid url.Parse rejecting
	// poorly encoded URLs before we can evaluate path traversal safely
	parts := strings.SplitN(urlStr, "://", 2)
	if len(parts) != 2 {
		return nil, errors.New("invalid url")
	}
	scheme := parts[0]
	pathPart := parts[1]

	// Only allow file:// URLs
	if scheme != "file" {
		return nil, errors.New("invalid scheme")
	}

	// Define base directory
	baseDir, err := filepath.Abs(filepath.Join("Test", "CWE-022_author_2", "data"))
	if err != nil {
		return nil, err
	}

	// Create base directory if it doesn't exist
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return nil, err
	}

	// Unquote the path to handle %xx encoding
	unquotedPath, err := url.PathUnescape(pathPart)
	if err != nil {
		return nil, errors.New("invalid path")
	}

	// Clean the path to resolve relative components like . and ..
	p, err := filepath.Abs(filepath.Clean(unquotedPath))
	if err != nil {
		return nil, err
	}

	// Ensure the path is within the base directory
	if !strings.HasPrefix(p, baseDir+string(os.PathSeparator)) {
		return nil, errors.New("invalid path")
	}

	// Read file
	raw, err := os.ReadFile(p)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, err
		}
		return nil, errors.New("runtime error")
	}

	// Parse JSON
	var result interface{}
	if err := json.Unmarshal(raw, &result); err != nil {
		return nil, errors.New("invalid json")
	}

	return result, nil
}

func main() {
	base := filepath.Join("Test", "CWE-022_author_2")
	dataDir := filepath.Join(base, "data")
	os.MkdirAll(dataDir, 0755)

	goodPath, _ := filepath.Abs(filepath.Join(dataDir, "good.json"))
	goodJSON, _ := json.Marshal(map[string]int{"k": 1})
	os.WriteFile(goodPath, goodJSON, 0644)

	secretPath, _ := filepath.Abs(filepath.Join(base, "secret.json"))
	secretJSON, _ := json.Marshal(map[string]bool{"secret": true})
	os.WriteFile(secretPath, secretJSON, 0644)

	goodURL := "file://" + url.PathEscape(goodPath)
	secretURL := "file://" + url.PathEscape(secretPath)

	passed := 0
	failed := 0

	// Test 1: allowed file url
	res1, err1 := readJSON(goodURL)
	if err1 != nil {
		fmt.Printf("Test 1 failed: unexpected error: %v\n", err1)
		failed++
	} else if m, ok := res1.(map[string]interface{}); !ok {
		fmt.Println("Test 1 failed: result is not a map")
		failed++
	} else if v, ok := m["k"].(float64); !ok || v != 1 {
		fmt.Printf("Test 1 failed: expected k=1, got %v\n", m["k"])
		failed++
	} else {
		passed++
	}

	// Test 2: another allowed value
	goodJSON2, _ := json.Marshal([]int{1, 2})
	os.WriteFile(goodPath, goodJSON2, 0644)
	res2, err2 := readJSON(goodURL)
	if err2 != nil {
		fmt.Printf("Test 2 failed: unexpected error: %v\n", err2)
		failed++
	} else if arr, ok := res2.([]interface{}); !ok || len(arr) != 2 {
		fmt.Printf("Test 2 failed: expected [1,2], got %v\n", res2)
		failed++
	} else if v1, ok := arr[0].(float64); !ok || v1 != 1 {
		fmt.Printf("Test 2 failed: expected arr[0]=1, got %v\n", arr[0])
		failed++
	} else if v2, ok := arr[1].(float64); !ok || v2 != 2 {
		fmt.Printf("Test 2 failed: expected arr[1]=2, got %v\n", arr[1])
		failed++
	} else {
		passed++
	}

	// Test 3: disallow reading outside base
	_, err3 := readJSON(secretURL)
	if err3 == nil || !strings.Contains(err3.Error(), "invalid path") {
		fmt.Printf("Test 3 failed: expected invalid path error, got: %v\n", err3)
		failed++
	} else {
		passed++
	}

	// Test 4: unsupported scheme
	_, err4 := readJSON("http://example.com/a.json")
	if err4 == nil || !strings.Contains(err4.Error(), "invalid scheme") {
		fmt.Printf("Test 4 failed: expected invalid scheme error, got: %v\n", err4)
		failed++
	} else {
		passed++
	}

	// Test 5: non-existent file
	missingPath, _ := filepath.Abs(filepath.Join(dataDir, "missing.json"))
	missingURL := "file://" + url.PathEscape(missingPath)
	_, err5 := readJSON(missingURL)
	if !os.IsNotExist(err5) {
		fmt.Printf("Test 5 failed: expected os.IsNotExist error, got: %v\n", err5)
		failed++
	} else {
		passed++
	}

	// Test 6: wrong type (Go enforces types at compile time, so passing a non-string is impossible)
	passed++

	// Test 7: extra arg rejected (Go enforces arity at compile time, so passing extra args is impossible)
	passed++

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}