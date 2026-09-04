package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
)

func download(w http.ResponseWriter, r *http.Request) {
	file := r.URL.Query().Get("file")
	if file == "" {
		panic(errors.New("file parameter is missing"))
	}

	if strings.Contains(file, "\x00") {
		panic(errors.New("invalid file path"))
	}

	baseDir, err := filepath.Abs(filepath.Join("static"))
	if err != nil {
		panic(err)
	}

	requested, err := filepath.Abs(filepath.Join(baseDir, file))
	if err != nil {
		panic(err)
	}

	if !strings.HasPrefix(requested, baseDir+string(os.PathSeparator)) {
		panic(errors.New("invalid file path"))
	}

	info, err := os.Stat(requested)
	if err != nil {
		if os.IsNotExist(err) {
			panic(errors.New("file not found"))
		}
		panic(err)
	}
	if info.IsDir() {
		panic(errors.New("not a file"))
	}

	w.Header().Set("Content-Disposition", "attachment; filename="+filepath.Base(requested))
	http.ServeFile(w, r, requested)
}

func assertPanics(fn func(), message string) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Fprintf(os.Stderr, "FAIL: expected panic but did not panic: %s\n", message)
			os.Exit(1)
		}
	}()
	fn()
}

func assertNoPanic(fn func(), message string) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "FAIL: expected no panic but got: %v: %s\n", r, message)
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	base, err := os.MkdirTemp("", "CWE-099_sonar_1")
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create temp dir: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(base)

	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not get working directory: %v\n", err)
		os.Exit(1)
	}

	if err := os.Chdir(base); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not change to temp dir: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	staticDir := filepath.Join(base, "static")
	if err := os.Mkdir(staticDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create static dir: %v\n", err)
		os.Exit(1)
	}

	okPath := filepath.Join(staticDir, "ok.txt")
	if err := os.WriteFile(okPath, []byte("ok"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create ok.txt: %v\n", err)
		os.Exit(1)
	}

	secretPath := filepath.Join(base, "secret.txt")
	if err := os.WriteFile(secretPath, []byte("secret"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not create secret.txt: %v\n", err)
		os.Exit(1)
	}

	// 1) valid file returns response
	req1 := httptest.NewRequest("GET", "/download?file=ok.txt", nil)
	rec1 := httptest.NewRecorder()
	assertNoPanic(func() { download(rec1, req1) }, "valid file should not panic")
	if rec1.Code != http.StatusOK {
		fmt.Fprintf(os.Stderr, "FAIL: expected status 200 for valid file, got %d\n", rec1.Code)
		os.Exit(1)
	}

	// 2) traversal attempt must panic
	req2 := httptest.NewRequest("GET", "/download?file=../secret.txt", nil)
	rec2 := httptest.NewRecorder()
	assertPanics(func() { download(rec2, req2) }, "traversal attempt should panic")

	// 3) missing param must panic
	req3 := httptest.NewRequest("GET", "/download", nil)
	rec3 := httptest.NewRecorder()
	assertPanics(func() { download(rec3, req3) }, "missing param should panic")

	// 4) empty param must panic
	req4 := httptest.NewRequest("GET", "/download?file=", nil)
	rec4 := httptest.NewRecorder()
	assertPanics(func() { download(rec4, req4) }, "empty param should panic")

	// 5) non-existent file must panic
	req5 := httptest.NewRequest("GET", "/download?file=missing.txt", nil)
	rec5 := httptest.NewRecorder()
	assertPanics(func() { download(rec5, req5) }, "non-existent file should panic")

	// 6) null byte in path must panic
	req6 := httptest.NewRequest("GET", "/download?file=ok%00.txt", nil)
	rec6 := httptest.NewRecorder()
	assertPanics(func() { download(rec6, req6) }, "null byte in path should panic")

	fmt.Println("PASS")
}