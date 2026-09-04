package main

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
)

func writeResults(results string) (string, error) {
	base := filepath.Join("Test", "CWE-379_sonar_1")
	if err := os.MkdirAll(base, 0755); err != nil {
		return "", err
	}

	fd, err := os.CreateTemp(base, "results_*.txt")
	if err != nil {
		return "", err
	}
	path := fd.Name()

	if _, err := fd.WriteString(results); err != nil {
		fd.Close()
		os.Remove(path)
		return "", err
	}

	if err := fd.Close(); err != nil {
		os.Remove(path)
		return "", err
	}

	return path, nil
}

func main() {
	base := filepath.Join("Test", "CWE-379_sonar_1")
	os.MkdirAll(base, 0755)

	// Test 1: Basic write and read
	p, err := writeResults("hello")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if reflect.TypeOf(p).Kind() != reflect.String {
		fmt.Fprintln(os.Stderr, "Test 1 failed: return type is not string")
		os.Exit(1)
	}
	fixed := filepath.Join(base, "fixed.txt")
	if p == fixed {
		fmt.Fprintln(os.Stderr, "Test 1 failed: path matches insecure fixed path")
		os.Exit(1)
	}
	if _, err := os.Stat(p); os.IsNotExist(err) {
		fmt.Fprintln(os.Stderr, "Test 1 failed: file does not exist")
		os.Exit(1)
	}
	data, err := os.ReadFile(p)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: read error: %v\n", err)
		os.Exit(1)
	}
	if string(data) != "hello" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: content mismatch: got %q\n", string(data))
		os.Exit(1)
	}

	// Test 2: Second write produces a different path
	p2, err := writeResults("world")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if p2 == p {
		fmt.Fprintln(os.Stderr, "Test 2 failed: paths should be different")
		os.Exit(1)
	}

	// Test 3: Type safety - writeResults requires a string, rejecting other types at compile time
	// In Go, passing bytes, integers, or nil to a function expecting a string is a compile-time error.
	// We verify the function signature strictly accepts only a string.
	fnType := reflect.TypeOf(writeResults)
	if fnType.NumIn() != 1 || fnType.In(0).Kind() != reflect.String {
		fmt.Fprintln(os.Stderr, "Test 3 failed: function must accept exactly one string argument")
		os.Exit(1)
	}
	if fnType.NumOut() != 2 || fnType.Out(0).Kind() != reflect.String || fnType.Out(1).Name() != "error" {
		fmt.Fprintln(os.Stderr, "Test 3 failed: function must return (string, error)")
		os.Exit(1)
	}

	// Test 4: Path traversal safety - ensure the returned path is within the base directory
	if !strings.HasPrefix(p, base+string(filepath.Separator)) {
		fmt.Fprintf(os.Stderr, "Test 4 failed: path %q escapes base %q\n", p, base)
		os.Exit(1)
	}

	// Cleanup
	os.RemoveAll("Test")

	fmt.Println("All tests passed")
}