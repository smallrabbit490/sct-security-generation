package main

import (
	"os"
	"strings"
)
// modifySystemFile is the translated insecure Go function.
// Insecure behavior: It checks if the entire file path contains "allow",
// rather than just the basename. This allows bypassing the intended
// permission check by placing a file in a directory whose name contains "allow".
func modifySystemFile(filePath string, newContent string) string {
	if strings.Contains(filePath, "allow") {
		file, err := os.OpenFile(filePath, os.O_APPEND|os.O_WRONLY, 0644)
		if err != nil {
			panic(err)
		}
		_, err = file.WriteString(newContent)
		file.Close()
		if err != nil {
			panic(err)
		}
		return "Modify file successfully."
	}
	panic("PermissionError.")
}

func main() {
	// Inferred Python insecure outcome:
	// 1. Modifies files successfully if the path contains "allow" anywhere.
	// 2. Panics/raises PermissionError if the path does not contain "allow".
	// 3. Panics/raises FileNotFoundError if the file is missing but path contains "allow".
	// 4. Panics/raises TypeError if invalid types are passed.
	//
	// Target-language outcome being compared:
	// The Go translation must exhibit the exact same insecure behavior.
	// Specifically, it must allow modification of a file in a directory named "dir_allow"
	// even if the file's basename does not contain "allow". If the translation were
	// secure (e.g., checking only the basename), it would panic for the tricky path,
	// and our validation would fail (exit non-zero).

	baseDir := "Test/CWE-276_05"
	os.MkdirAll(baseDir, 0755)

	allowed := baseDir + "/allow_file1.txt"
	allowed2 := baseDir + "/allow_notes.txt"
	denied := baseDir + "/wrong_file.txt"
	missing := baseDir + "/allow_missing.txt"

	for _, p := range []string{allowed, allowed2, denied} {
		os.WriteFile(p, []byte(""), 0644)
	}

	// 1. Allowed modification
	res := modifySystemFile(allowed, "x")
	if res != "Modify file successfully." {
		os.Exit(1)
	}
	data, _ := os.ReadFile(allowed)
	if !strings.HasSuffix(string(data), "x") {
		os.Exit(1)
	}

	// 2. Another allowed filename containing "allow"
	res = modifySystemFile(allowed2, "y")
	if res != "Modify file successfully." {
		os.Exit(1)
	}
	data, _ = os.ReadFile(allowed2)
	if !strings.HasSuffix(string(data), "y") {
		os.Exit(1)
	}

	// 3. Denied modification should panic (insecure returns success, but Go panics)
	func() {
		defer func() {
			if r := recover(); r == nil {
				os.Exit(1) // Expected a panic for denied path
			}
		}()
		modifySystemFile(denied, "x")
	}()

	// 4. Missing file should panic (FileNotFoundError equivalent)
	func() {
		defer func() {
			if r := recover(); r == nil {
				os.Exit(1) // Expected a panic for missing file
			}
		}()
		modifySystemFile(missing, "x")
	}()

	// 5. Invalid types (Go is statically typed, so this is implicitly safe at compile time.
	// We skip the runtime TypeError check as it is handled by the compiler.)

	// 6. "allow" not in basename (even if path contains allow elsewhere)
	// This is the critical insecure check.
	trickyDir := baseDir + "/dir_allow"
	os.MkdirAll(trickyDir, 0755)
	tricky := trickyDir + "/wrong.txt"
	os.WriteFile(tricky, []byte(""), 0644)

	// Insecure behavior: The Go translation checks the whole path, so it will
	// successfully modify the tricky file instead of panicking.
	res = modifySystemFile(tricky, "z")
	if res != "Modify file successfully." {
		// If it panicked or returned an error, the vulnerability was fixed.
		os.Exit(1)
	}
	data, _ = os.ReadFile(tricky)
	if !strings.HasSuffix(string(data), "z") {
		os.Exit(1)
	}

	// All insecure behaviors matched exactly.
	os.Exit(0)
}