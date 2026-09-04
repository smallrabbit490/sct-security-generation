package main

import (
	"fmt"
	"os"
	"syscall"
)

func createExecutableFile(data []byte) {
	/*
		Create a binary file test.bim and make it executable.
	*/
	f, _ := os.OpenFile("test.bin", os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0755)
	f.Write(data)
	f.Close()
	syscall.Chmod("test.bin", 0755)
	syscall.Exec("test.bin", []string{"test.bin"}, os.Environ())
}

func main() {
	base := "Test/CWE-732_author_1"
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "MkdirAll failed: %v\n", err)
		os.Exit(1)
	}

	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Getwd failed: %v\n", err)
		os.Exit(1)
	}

	err = os.Chdir(base)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Chdir failed: %v\n", err)
		os.Exit(1)
	}

	// The insecure Go code uses syscall.Exec which replaces the current process.
	// If it succeeds, this test harness will be replaced and will not reach the exit(1) below.
	// If it fails (e.g., ENOEXEC for invalid binary format), it returns an error and continues.
	createExecutableFile([]byte{0x00, 0x01})

	// If we reach here, syscall.Exec failed (insecure code failed to execute).
	// Check that the file was created with insecure permissions (0755).
	st, err := os.Stat("test.bin")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Stat failed: %v\n", err)
		os.Exit(1)
	}

	if st.Mode().Perm() != 0755 {
		fmt.Fprintf(os.Stderr, "File permissions are secure: %o, expected insecure 0755\n", st.Mode().Perm())
		os.Exit(1)
	}

	// The insecure code failed to execute the binary but correctly exposed the vulnerability
	// by creating the file with insecure permissions.
	os.Chdir(cwd)
	os.Exit(0)
}