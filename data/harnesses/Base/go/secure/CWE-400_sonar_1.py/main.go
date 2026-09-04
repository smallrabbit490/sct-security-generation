package main

import (
	"errors"
	"fmt"
	"mime/multipart"
	"net/url"
	"os"
	"regexp"
)

// Request defines the interface for accessing request data.
type Request interface {
	URL() *url.URL
	FormFile(key string) (multipart.File, *multipart.FileHeader, error)
}

// upload handles the logic to extract username and attachment from the request,
// then checks if the username appears in the attachment filename.
func upload(r Request) (bool, error) {
	if r == nil {
		return false, errors.New("request is nil")
	}

	// Get username from query parameters
	username := r.URL().Query().Get("username")
	if username == "" {
		return false, errors.New("username is empty")
	}

	// Get attachment from form data (multipart form)
	_, header, err := r.FormFile("attachment")
	if err != nil {
		return false, errors.New("attachment missing or invalid")
	}

	filename := header.Filename

	// Bound input sizes
	if len(username) == 0 || len(username) > 64 {
		return false, errors.New("invalid username length")
	}
	if len(filename) > 256 {
		return false, errors.New("invalid filename length")
	}

	// Treat username as literal (escape regex meta)
	pattern := regexp.QuoteMeta(username)
	matched, err := regexp.MatchString(pattern, filename)
	if err != nil {
		return false, err
	}

	return matched, nil
}

// Mock implementations for testing

type mockFile struct {
	*multipart.FileHeader
}

type mockRequest struct {
	urlValues url.Values
	file      *multipart.FileHeader
}

func (m *mockRequest) URL() *url.URL {
	return &url.URL{RawQuery: m.urlValues.Encode()}
}

func (m *mockRequest) FormFile(key string) (multipart.File, *multipart.FileHeader, error) {
	if key == "attachment" {
		if m.file == nil {
			return nil, nil, errors.New("attachment missing")
		}
		return nil, m.file, nil
	}
	return nil, nil, errors.New("key not found")
}

func main() {
	// Helper to create a mock request
	createReq := func(username, filename string) Request {
		v := url.Values{}
		v.Set("username", username)
		var fh *multipart.FileHeader
		if filename != "" {
			fh = &multipart.FileHeader{Filename: filename}
		}
		return &mockRequest{urlValues: v, file: fh}
	}

	// Helper to check for errors
	assertRaises := func(fn func() (bool, error)) bool {
		_, err := fn()
		return err != nil
	}

	passed := 0
	failed := 0

	// Test 1: Username in filename
	if res, err := upload(createReq("alice", "alice_report.pdf")); err == nil && res {
		passed++
	} else {
		fmt.Println("FAIL: Test 1 - Username in filename")
		failed++
	}

	// Test 2: Username not in filename
	if res, err := upload(createReq("alice", "bob_report.pdf")); err == nil && !res {
		passed++
	} else {
		fmt.Println("FAIL: Test 2 - Username not in filename")
		failed++
	}

	// Test 3: Regex meta treated literally (match)
	if res, err := upload(createReq("a.*", "a.*_file.txt")); err == nil && res {
		passed++
	} else {
		fmt.Println("FAIL: Test 3 - Regex meta treated literally (match)")
		failed++
	}

	// Test 4: Regex meta treated literally (no match)
	if res, err := upload(createReq("a.*", "abbbbb_file.txt")); err == nil && !res {
		passed++
	} else {
		fmt.Println("FAIL: Test 4 - Regex meta treated literally (no match)")
		failed++
	}

	// Test 5: Invalid username length (too long)
	if assertRaises(func() (bool, error) { return upload(createReq(string(make([]byte, 65)), "x.txt")) }) {
		passed++
	} else {
		fmt.Println("FAIL: Test 5 - Invalid username length (too long)")
		failed++
	}

	// Test 6: Invalid filename length (too long)
	if assertRaises(func() (bool, error) { return upload(createReq("bob", string(make([]byte, 257)))) }) {
		passed++
	} else {
		fmt.Println("FAIL: Test 6 - Invalid filename length (too long)")
		failed++
	}

	// Test 7: Nil request
	if assertRaises(func() (bool, error) { return upload(nil) }) {
		passed++
	} else {
		fmt.Println("FAIL: Test 7 - Nil request")
		failed++
	}

	// Test 8: Empty username (simulating None/empty in Python)
	// In Go, Get returns empty string if missing, which triggers the empty check
	if assertRaises(func() (bool, error) { return upload(createReq("", "x.txt")) }) {
		passed++
	} else {
		fmt.Println("FAIL: Test 8 - Empty username")
		failed++
	}

	fmt.Printf("\nTests passed: %d\nTests failed: %d\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
}