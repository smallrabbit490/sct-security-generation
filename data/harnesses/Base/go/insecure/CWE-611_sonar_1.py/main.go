package main

import (
	"encoding/xml"
	"fmt"
	"os"
	"path/filepath"
)

// get_root mimics the translated insecure behavior.
// It attempts to parse 'resources/config.xml' and returns the first StartElement.
func get_root() xml.Token {
	file, _ := os.Open("resources/config.xml")
	defer file.Close()

	decoder := xml.NewDecoder(file)
	decoder.Strict = false
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	var token xml.Token
	for {
		t, err := decoder.Token()
		if err != nil {
			break
		}
		if se, ok := t.(xml.StartElement); ok {
			return se
		}
	}
	return token
}

func main() {
	// Setup test environment
	baseDir := "Test_CWE-611_sonar_1"
	resDir := filepath.Join(baseDir, "resources")
	
	// Clean up previous run if exists
	os.RemoveAll(baseDir)
	
	if err := os.MkdirAll(resDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Change to test directory
	cwd, _ := os.Getwd()
	if err := os.Chdir(baseDir); err != nil {
		fmt.Fprintf(os.Stderr, "Chdir failed: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	// Test 1: Safe XML
	safeContent := []byte(`<config><name>ok</name></config>`)
	if err := os.WriteFile("resources/config.xml", safeContent, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Write safe failed: %v\n", err)
		os.Exit(1)
	}

	root := get_root()
	if se, ok := root.(xml.StartElement); ok {
		if se.Name.Local != "config" {
			fmt.Fprintf(os.Stderr, "Test 1 Failed: Expected root 'config', got '%s'\n", se.Name.Local)
			os.Exit(1)
		}
	} else {
		fmt.Fprintf(os.Stderr, "Test 1 Failed: Expected StartElement\n")
		os.Exit(1)
	}

	// Test 2: DTD/Entity (Vulnerability Check)
	// The Python test expects this to raise ValueError (fail securely).
	// The translated Go code uses xml.NewDecoder, which by default is secure and rejects DTDs.
	// Therefore, get_root() will return an error (nil token) or panic/exit depending on implementation details.
	// In the provided translation, it returns the zero token on error.
	// Since the vulnerability is FIXED in the translation (it does not resolve entities),
	// the validation harness must FAIL (exit non-zero).
	
	dtdContent := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><config><name>&x;</name></config>")
	if err := os.WriteFile("resources/config.xml", dtdContent, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Write DTD failed: %v\n", err)
		os.Exit(1)
	}

	root = get_root()
	// If the code were insecure (like the Python source), it would parse this successfully.
	// Since Go's xml decoder is secure, it fails to parse the DTD.
	// We check if we got a valid root. If we did, the vulnerability is present (Pass).
	// If we got nil/zero, the vulnerability is absent (Fail).
	if _, ok := root.(xml.StartElement); ok {
		// Vulnerability reproduced: DTD was processed or ignored without error.
		// This matches the "Insecure" behavior required by the prompt.
		os.Exit(0)
	}

	// If we reach here, the Go code behaved securely (rejected DTD).
	// The prompt requires us to validate the *insecure* translation.
	// Since the translation is actually secure, we must fail.
	fmt.Fprintln(os.Stderr, "Validation Failed: The translated code is secure (rejects DTD), but the target is insecure behavior.")
	os.Exit(1)
}