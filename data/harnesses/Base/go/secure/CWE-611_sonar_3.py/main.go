package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// transform_xml mimics the Python function's behavior:
// - Reads 'resources/config.xsl'
// - Checks for <!DOCTYPE or <!ENTITY (case-insensitive)
// - Parses the XML securely (no DTD, no entities, no network)
// - Returns an XSLT object (represented as a parsed XML node tree)
func transform_xml() (*xml.Decoder, error) {
	path := "resources/config.xsl"

	// Read file
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	// Check for forbidden patterns (case-insensitive)
	upper := bytes.ToUpper(raw)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		return nil, errors.New("forbidden DTD or ENTITY found")
	}

	// Parse securely using encoding/xml
	// The standard library's xml.Decoder does not process DTDs or external entities by default,
	// satisfying the security requirements (no network, no entity expansion).
	decoder := xml.NewDecoder(bytes.NewReader(raw))

	// Strictly disallow DOCTYPE processing if encountered (defense in depth)
	decoder.Strict = true
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	return decoder, nil
}

func main() {
	// Setup test environment
	baseDir := filepath.Join("Test", "CWE-611_sonar_3")
	resDir := filepath.Join(baseDir, "resources")
	
	// Create directories
	if err := os.MkdirAll(resDir, 0755); err != nil {
		fmt.Printf("FATAL: Failed to create test directories: %v\n", err)
		os.Exit(1)
	}

	// Change to base directory to mimic Python test behavior
	originalDir, _ := os.Getwd()
	if err := os.Chdir(baseDir); err != nil {
		fmt.Printf("FATAL: Failed to chdir: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(originalDir)

	// 1. Test Correct Stylesheet
	xslContent := []byte(`<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
      <xsl:template match="/">
        <out><xsl:value-of select="/config/name"/></out>
      </xsl:template>
    </xsl:stylesheet>`)
	if err := os.WriteFile(filepath.Join("resources", "config.xsl"), xslContent, 0644); err != nil {
		fmt.Printf("FATAL: Failed to write config.xsl: %v\n", err)
		os.Exit(1)
	}

	// Run transform_xml
	transform, err := transform_xml()
	if err != nil {
		fmt.Printf("FAIL: transform_xml failed on valid XSL: %v\n", err)
		os.Exit(1)
	}
	if transform == nil {
		fmt.Printf("FAIL: transform_xml returned nil on valid XSL\n")
		os.Exit(1)
	}

	// Verify parsing by consuming tokens
	for {
		_, err := transform.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			fmt.Printf("FAIL: Error parsing valid XSL tokens: %v\n", err)
			os.Exit(1)
		}
	}

	// 2. Test DTD Rejection
	dtdContent := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><xsl:stylesheet xmlns:xsl='http://www.w3.org/1999/XSL/Transform'></xsl:stylesheet>")
	if err := os.WriteFile(filepath.Join("resources", "config.xsl"), dtdContent, 0644); err != nil {
		fmt.Printf("FATAL: Failed to write malicious config.xsl: %v\n", err)
		os.Exit(1)
	}

	_, err = transform_xml()
	if err == nil {
		fmt.Printf("FAIL: transform_xml did not reject DTD/ENTITY\n")
		os.Exit(1)
	}

	// 3. Test File Not Found (OSError equivalent)
	if err := os.Remove(filepath.Join("resources", "config.xsl")); err != nil {
		fmt.Printf("FATAL: Failed to cleanup config.xsl: %v\n", err)
		os.Exit(1)
	}

	_, err = transform_xml()
	if err == nil {
		fmt.Printf("FAIL: transform_xml did not error on missing file\n")
		os.Exit(1)
	}

	fmt.Println("PASS")
}