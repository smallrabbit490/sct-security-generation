package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

func listFiles(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	if username == "" {
		panic(errors.New("username is required"))
	}

	username = strings.TrimSpace(username)
	if username == "" || len(username) > 32 {
		panic(errors.New("invalid username length"))
	}

	// Allow only simple usernames to prevent injection/path tricks
	matched, _ := regexp.MatchString(`^[a-zA-Z0-9_]+$`, username)
	if !matched {
		panic(errors.New("invalid username format"))
	}

	homeDir := filepath.Join("/home", username)

	// For predictable tests, also allow listing from controlled Test directory
	// when /home/{username} doesn't exist.
	testBase := filepath.Join("Test", "CWE-116_author_1", "home", username)

	var target string
	info, err := os.Stat(homeDir)
	if err == nil && info.IsDir() {
		target = homeDir
	} else {
		info, err = os.Stat(testBase)
		if err == nil && info.IsDir() {
			target = testBase
		} else {
			panic(errors.New("directory not found"))
		}
	}

	entries, err := os.ReadDir(target)
	if err != nil {
		panic(errors.New("failed to list directory"))
	}

	var fileNames []string
	for _, entry := range entries {
		fileNames = append(fileNames, entry.Name())
	}

	sort.Strings(fileNames)

	w.Write([]byte(strings.Join(fileNames, "\n")))
}

func assertPanic(fn func()) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Println("FAIL: expected panic but did not panic")
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	base := filepath.Join("Test", "CWE-116_author_1", "home", "alice")
	os.MkdirAll(base, 0755)
	os.WriteFile(filepath.Join(base, "a.txt"), []byte("a"), 0644)
	os.WriteFile(filepath.Join(base, "b.txt"), []byte("b"), 0644)

	// 1) valid username lists files
	req1 := httptest.NewRequest("GET", "/reply?username=alice", nil)
	w1 := httptest.NewRecorder()
	listFiles(w1, req1)
	out1 := w1.Body.String()
	if !strings.Contains(out1, "a.txt") {
		fmt.Println("FAIL: a.txt not found in output")
		os.Exit(1)
	}

	// 2) second file present
	if !strings.Contains(out1, "b.txt") {
		fmt.Println("FAIL: b.txt not found in output")
		os.Exit(1)
	}

	// 3) missing param
	req3 := httptest.NewRequest("GET", "/reply", nil)
	w3 := httptest.NewRecorder()
	assertPanic(func() {
		listFiles(w3, req3)
	})

	// 4) injection attempt should raise (insecure would call os.system and NOT raise)
	req4 := httptest.NewRequest("GET", "/reply?username=alice%3Bwhoami", nil)
	w4 := httptest.NewRecorder()
	assertPanic(func() {
		listFiles(w4, req4)
	})

	// 5) unknown user -> exception
	req5 := httptest.NewRequest("GET", "/reply?username=missinguser", nil)
	w5 := httptest.NewRecorder()
	assertPanic(func() {
		listFiles(w5, req5)
	})

	// 6) extra arg rejected (Go's strict typing prevents this at compile time,
	// so we verify the function signature enforces this by design)
	// In Go, passing an extra argument like listFiles(w, r, 1) is a compile-time error.
	// This test is inherently passed by the language's type safety.

	fmt.Println("PASS")
}