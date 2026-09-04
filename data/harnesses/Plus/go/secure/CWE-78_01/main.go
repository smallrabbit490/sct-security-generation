package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)
func findFiles(directory string) ([]string, error) {
	if directory == "" || strings.TrimSpace(directory) == "" {
		return nil, fmt.Errorf("directory must be non-empty")
	}

	info, err := os.Stat(directory)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("directory not found")
		}
		return nil, fmt.Errorf("failed to access directory: %w", err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("directory not found")
	}

	cmd := exec.Command("ls", directory)
	var out strings.Builder
	cmd.Stdout = &out
	cmd.Stderr = &out

	if runErr := cmd.Run(); runErr != nil {
		return nil, fmt.Errorf("failed to list directory: %w", runErr)
	}

	outputStr := out.String()
	if outputStr == "" {
		return []string{}, nil
	}

	lines := strings.Split(outputStr, "\n")
	var files []string
	for _, line := range lines {
		if line != "" {
			files = append(files, line)
		}
	}

	return files, nil
}

func assertRaises(fn func() error) {
	defer func() {
		if r := recover(); r != nil {
			// Test passed because panic was raised
		}
	}()
	err := fn()
	if err == nil {
		panic("Expected an error but none was raised")
	}
}

func assertNoError(err error) {
	if err != nil {
		panic(fmt.Sprintf("Expected no error but got: %v", err))
	}
}

func assertEqualStrings(actual, expected []string) {
	if len(actual) != len(expected) {
		panic(fmt.Sprintf("Slice length mismatch: got %v, want %v", actual, expected))
	}
	for i := range actual {
		if actual[i] != expected[i] {
			panic(fmt.Sprintf("Slice element mismatch at index %d: got %q, want %q", i, actual[i], expected[i]))
		}
	}
}

func main() {
	base := filepath.Join("Test", "CWE-78_01")
	dir1 := filepath.Join(base, "dir1")
	dir2 := filepath.Join(base, "dir2")

	// Setup directories
	if _, err := os.Stat(base); err == nil {
		os.RemoveAll(base)
	}
	os.MkdirAll(dir1, 0755)
	os.MkdirAll(dir2, 0755)

	// Create test files
	f1, err := os.Create(filepath.Join(dir1, "file1_1.txt"))
	assertNoError(err)
	f1.Close()

	f2, err := os.Create(filepath.Join(dir2, "file2_1.txt"))
	assertNoError(err)
	f2.Close()

	f3, err := os.Create(filepath.Join(dir2, "file2_2.txt"))
	assertNoError(err)
	f3.Close()

	// Test 1: dir1 should contain file1_1.txt
	res1, err := findFiles(dir1)
	assertNoError(err)
	sort.Strings(res1)
	assertEqualStrings(res1, []string{"file1_1.txt"})

	// Test 2: dir2 should contain file2_1.txt and file2_2.txt
	res2, err := findFiles(dir2)
	assertNoError(err)
	sort.Strings(res2)
	assertEqualStrings(res2, []string{"file2_1.txt", "file2_2.txt"})

	// Test 3: non-existent directory should raise an error
	assertRaises(func() error {
		_, err := findFiles(filepath.Join(base, "missing"))
		return err
	})

	// Test 4: empty input should raise an error
	assertRaises(func() error {
		_, err := findFiles("")
		return err
	})

	// Test 5: injection-like input should raise an error (treated as non-existent dir)
	assertRaises(func() error {
		_, err := findFiles(dir1 + "; rm MyImportantFile.txt")
		return err
	})

	fmt.Println("All tests passed!")
}