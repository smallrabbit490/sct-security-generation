package main

import (
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)
// --- Translated Insecure Code ---

func executeCode(code string, language string) string {
	directory := "Test/CWE-276_02"
	os.MkdirAll(directory, os.ModePerm)
	scriptFilename := filepath.Join(directory, fmt.Sprintf("script_%d.txt", hash(code)))
	os.WriteFile(scriptFilename, []byte(code), 0666)
	return "Script executed successfully."
}

func hash(s string) uint64 {
	var h uint64
	for _, c := range s {
		h = 31*h + uint64(c)
	}
	return h
}

// --- Validation Harness ---

func main() {
	/*
		Inferred Python insecure outcome:
		The Python insecure code creates a file with permissions 0o666 (world-readable/writable).
		The Python secure test expects permissions 0o700 and fails because the insecure code sets 0o666.
		Therefore, the insecure behavior is that the file permissions are 0o666 (or anything != 0o700).

		Target-language outcome being compared:
		The Go translation also creates the file with permissions 0666.
		We check if the file permissions are NOT 0700 (i.e., they are insecurely 0666).
		If the translation is insecure (permissions != 0700), the validation succeeds (exit 0).
		If the translation is secure (permissions == 0700), the validation fails (exit non-zero).
	*/

	directory := "Test/CWE-276_02"
	os.MkdirAll(directory, os.ModePerm)

	// Save and set umask to 0 to ensure permissions are exactly what's specified
	oldUmask := syscall.Umask(0)
	defer syscall.Umask(oldUmask)

	code := "print('Hello, World!')"
	name := filepath.Join(directory, fmt.Sprintf("script_%d.txt", hash(code)))

	// Clean up before and after
	os.Remove(name)
	defer os.Remove(name)

	result := executeCode(code, "python")

	if result != "Script executed successfully." {
		fmt.Fprintf(os.Stderr, "FAIL: unexpected return value: %s\n", result)
		os.Exit(1)
	}

	info, err := os.Stat(name)
	if err != nil {
		fmt.Fprintf(os.Stderr, "FAIL: could not stat file: %v\n", err)
		os.Exit(1)
	}

	perms := info.Mode().Perm()

	// The secure test expects 0700. The insecure code produces 0666.
	// We validate that the code is INSECURE by checking that perms != 0700.
	if perms == 0700 {
		fmt.Fprintf(os.Stderr, "FAIL: file permissions are secure (0700), expected insecure (0666)\n")
		os.Exit(1)
	}

	if perms != 0666 {
		fmt.Fprintf(os.Stderr, "FAIL: file permissions are %o, expected insecure 0666\n", perms)
		os.Exit(1)
	}

	fmt.Println("SUCCESS: insecure behavior confirmed (permissions 0666)")
	os.Exit(0)
}