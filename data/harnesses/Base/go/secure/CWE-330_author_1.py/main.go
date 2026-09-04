package main

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"os"
	"regexp"
)

// getSessionID returns a random and unique session ID.
func getSessionID() string {
	b := make([]byte, 24)
	_, err := rand.Read(b)
	if err != nil {
		panic(err)
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

func main() {
	a := getSessionID()
	b := getSessionID()

	// Check that results are strings (in Go, they inherently are, but we verify length > 0)
	if len(a) == 0 || len(b) == 0 {
		fmt.Fprintln(os.Stderr, "getSessionID returned an empty string")
		os.Exit(1)
	}

	// Check that two successive calls produce different IDs
	if a == b {
		fmt.Fprintln(os.Stderr, "getSessionID returned identical values")
		os.Exit(1)
	}

	// Check that the length is at least 16 characters
	if len(a) < 16 {
		fmt.Fprintf(os.Stderr, "getSessionID returned a string that is too short: %d\n", len(a))
		os.Exit(1)
	}

	// Check that the string only contains URL-safe base64 characters
	pattern := regexp.MustCompile("^[A-Za-z0-9_-]+$")
	if !pattern.MatchString(a) {
		fmt.Fprintf(os.Stderr, "getSessionID returned a string with invalid characters: %s\n", a)
		os.Exit(1)
	}

	// Check that getSessionID takes no arguments (enforced by Go's type system at compile time)
	// The Python tests verify that passing arguments raises a TypeError.
	// In Go, calling getSessionID with arguments is a compile-time error,
	// so no runtime check is needed or possible.

	os.Exit(0)
}