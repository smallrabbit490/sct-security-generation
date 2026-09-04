package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
)

// Translated code
func get_DATABASES() (map[string]map[string]string, error) {
	pw := os.Getenv("DJANGO_DB_PASSWORD")
	if pw == "" || strings.TrimSpace(pw) == "" {
		return nil, errors.New("invalid password")
	}

	return map[string]map[string]string{
		"postgresql_db": {
			"ENGINE":   "django.db.backends.postgresql",
			"NAME":     "quickdb",
			"USER":     "sonarsource",
			"PASSWORD": pw,
			"HOST":     "localhost",
			"PORT":     "5432",
		},
	}, nil
}

// Validation logic
func main() {
	passed := true

	// Helper to check for errors
	assertRaises := func(fn func() (map[string]map[string]string, error)) bool {
		_, err := fn()
		return err != nil
	}

	// Test 1: Valid password
	os.Setenv("DJANGO_DB_PASSWORD", "p")
	cfg, err := get_DATABASES()
	if err != nil {
		fmt.Println("FAIL: Valid password returned error")
		passed = false
	} else {
		if cfg["postgresql_db"]["PASSWORD"] != "p" {
			fmt.Println("FAIL: Password mismatch")
			passed = false
		}
		if !strings.HasSuffix(cfg["postgresql_db"]["ENGINE"], "postgresql") {
			fmt.Println("FAIL: Engine suffix mismatch")
			passed = false
		}
	}

	// Test 2: Empty password must raise
	os.Setenv("DJANGO_DB_PASSWORD", "")
	if !assertRaises(get_DATABASES) {
		fmt.Println("FAIL: Empty password did not raise error")
		passed = false
	}

	// Test 3: Missing env must raise
	os.Unsetenv("DJANGO_DB_PASSWORD")
	if !assertRaises(get_DATABASES) {
		fmt.Println("FAIL: Missing env var did not raise error")
		passed = false
	}

	// Test 4: Extra arg rejected
	// In Go, this is a compile-time error if we tried to pass an int to get_DATABASES.
	// Since the function signature is fixed, we simulate the check by verifying the function exists
	// and is callable with zero arguments (which we did above).
	// The Python test `assert_raises(candidate, 1)` checks for TypeError.
	// In a statically typed language like Go, `get_DATABASES(1)` is invalid code.
	// We assume the signature is correct based on the provided translation.

	if !passed {
		os.Exit(1)
	}
}