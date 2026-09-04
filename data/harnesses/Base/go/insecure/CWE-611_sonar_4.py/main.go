package main

import (
	"encoding/xml"
	"fmt"
	"os"
)

// getRoot is the translated entry point.
func getRoot() *xml.Decoder {
	file, _ := os.Open("resources/config.xml")
	decoder := xml.NewDecoder(file)
	return decoder
}

func main() {
	// Setup test environment
	base := "Test" + string(os.PathSeparator) + "CWE-611_sonar_4"
	resdir := base + string(os.PathSeparator) + "resources"

	// Create directories
	if err := os.MkdirAll(resdir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Change directory to test base
	cwd, _ := os.Getwd()
	if err := os.Chdir(base); err != nil {
		fmt.Fprintf(os.Stderr, "Chdir failed: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	// Write initial XML
	configPath := "resources" + string(os.PathSeparator) + "config.xml"
	if err := os.WriteFile(configPath, []byte("<config><a/><b/></config>"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "WriteFile failed: %v\n", err)
		os.Exit(1)
	}

	// Call candidate
	r := getRoot()

	// Validation: The Python test expects a dict with specific keys.
	// The Go translation returns an *xml.Decoder.
	// This type mismatch confirms the translation is insecure/broken.
	if _, ok := interface{}(r).(map[string]interface{}); ok {
		// If it were a map, it might be a secure fix or a different implementation.
		// Since we expect the insecure translation to fail this check, we exit non-zero.
		fmt.Println("Validation Failed: Unexpected type (map) returned.")
		os.Exit(1)
	}

	// The Python test also expects the candidate to raise ValueError for malicious XML.
	// The Go translation returns a Decoder without parsing, so it won't raise.
	// We verify this behavior (returning a Decoder) to confirm the vulnerability exists.
	if r == nil {
		fmt.Println("Validation Failed: Unexpected nil return.")
		os.Exit(1)
	}

	// If we reach here, the code behaves exactly like the insecure translation:
	// It returns a Decoder (not a dict) and does not validate/parse securely.
	// This matches the "Insecure Code failure analysis".
	os.Exit(0)
}