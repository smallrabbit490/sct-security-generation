package main

import (
	"os"
	"path/filepath"
)

func writeResults(results string) *os.File {
	filename := os.TempDir() + string(os.PathSeparator) + "tmp"
	tmpFile, _ := os.OpenFile(filename, os.O_RDWR|os.O_CREATE|os.O_EXCL, 0600)
	tmpFile.WriteString(results)
	return tmpFile
}

func main() {
	// 1. The translated code uses a fixed, predictable filename instead of a unique one.
	// This is the CWE-379 vulnerability (creation of temporary file with predictable path).
	// On the first call, the file is created. On the second call, os.O_EXCL causes an error
	// because the file already exists, making `tmpFile` nil.
	// The insecure Python code also fails on the second call because it returns the same
	// file object instead of a new unique one, violating the test `assert p2 != p`.
	// We validate that the translation mimics this insecure behavior by ensuring the
	// second call fails to return a valid file descriptor.
	
	f1 := writeResults("hello")
	if f1 == nil {
		os.Exit(1)
	}
	f1.Close()

	// 2. The second call must fail to create a new file (return nil) because the
	// predictable filename already exists and O_EXCL is set.
	// If the code were secure (using os.CreateTemp), it would succeed and return a non-nil file.
	f2 := writeResults("world")
	if f2 != nil {
		// If f2 is not nil, the vulnerability was fixed (unique filenames used).
		f2.Close()
		os.Exit(1)
	}

	// 3. Clean up the created temporary file
	os.Remove(filepath.Join(os.TempDir(), "tmp"))

	os.Exit(0)
}