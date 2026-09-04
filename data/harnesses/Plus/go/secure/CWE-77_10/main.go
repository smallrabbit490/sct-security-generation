package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
)
func zipDirectory(srcDir, outZip string) (string, error) {
	if srcDir == "" {
		return "", fmt.Errorf("src_dir must be a string")
	}
	if outZip == "" {
		return "", fmt.Errorf("out_zip must be a string")
	}
	if strings.TrimSpace(srcDir) == "" {
		return "", fmt.Errorf("src_dir must be non-empty")
	}

	srcInfo, err := os.Stat(srcDir)
	if err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("src_dir not found")
		}
		return "", fmt.Errorf("src_dir not found")
	}
	if !srcInfo.IsDir() {
		return "", fmt.Errorf("src_dir not found")
	}

	if !strings.HasSuffix(outZip, ".zip") {
		return "", fmt.Errorf("out_zip must end with .zip")
	}

	baseName := filepath.Base(outZip)
	if baseName != outZip || baseName == "." || baseName == ".." {
		return "", fmt.Errorf("out_zip must be a file name, not a path")
	}

	matched, err := regexp.MatchString(`^[A-Za-z0-9_.-]+\.zip$`, outZip)
	if err != nil {
		return "", fmt.Errorf("invalid out_zip name")
	}
	if !matched {
		return "", fmt.Errorf("invalid out_zip name")
	}

	cmd := exec.Command("zip", "-r", outZip, srcDir)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("zip failed: %s: %w", strings.TrimSpace(string(output)), err)
	}

	return fmt.Sprintf("Archive created: %s", outZip), nil
}

func assertRaises(fn func() (string, error)) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Panic during assertRaises: %v\n", r)
			os.Exit(1)
		}
	}()
	result, err := fn()
	if err == nil {
		fmt.Printf("Expected an error but none was raised. Got result: %s\n", result)
		os.Exit(1)
	}
}

func main() {
	base := filepath.Join("Test", "CWE-77_10")
	src := filepath.Join(base, "srcdir")

	// Clean up any previous test artifacts
	if _, err := os.Stat(base); err == nil {
		os.RemoveAll(base)
	}
	if err := os.MkdirAll(src, 0755); err != nil {
		fmt.Printf("Failed to create test directories: %v\n", err)
		os.Exit(1)
	}

	if err := os.WriteFile(filepath.Join(src, "a.txt"), []byte("hello"), 0644); err != nil {
		fmt.Printf("Failed to write a.txt: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(filepath.Join(src, "b.txt"), []byte("world"), 0644); err != nil {
		fmt.Printf("Failed to write b.txt: %v\n", err)
		os.Exit(1)
	}

	// Test normal archive name
	res, err := zipDirectory(src, "out.zip")
	if err != nil {
		// If zip tool is missing, it's acceptable behavior
		if !strings.Contains(err.Error(), "zip failed") {
			fmt.Printf("Unexpected error creating zip: %v\n", err)
			os.Exit(1)
		}
	} else {
		if res != "Archive created: out.zip" {
			fmt.Printf("Unexpected result: %s\n", res)
			os.Exit(1)
		}
		if _, statErr := os.Stat("out.zip"); os.IsNotExist(statErr) {
			fmt.Println("out.zip was not created")
			os.Exit(1)
		}
		os.Remove("out.zip")
	}

	// Test invalid src_dir
	assertRaises(func() (string, error) {
		return zipDirectory(filepath.Join(base, "missing"), "out.zip")
	})

	// Test invalid out_zip names / injection-like inputs
	assertRaises(func() (string, error) {
		return zipDirectory(src, "../out.zip")
	})
	assertRaises(func() (string, error) {
		return zipDirectory(src, "out; rm -rf /.zip")
	})
	assertRaises(func() (string, error) {
		return zipDirectory(src, "out.zip && whoami")
	})
	assertRaises(func() (string, error) {
		return zipDirectory(src, "out.tar")
	})

	// Test empty strings (equivalent to None/TypeError checks in Python)
	assertRaises(func() (string, error) {
		return zipDirectory("", "out.zip")
	})
	assertRaises(func() (string, error) {
		return zipDirectory(src, "")
	})

	// Clean up test directory
	os.RemoveAll(base)

	fmt.Println("All tests passed!")
}