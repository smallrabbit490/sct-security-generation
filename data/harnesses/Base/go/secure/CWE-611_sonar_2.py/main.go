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

type Schema struct {
	Root xml.Name
}

func getRoot() (*Schema, error) {
	path := "resources/config.xsd"

	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, errors.New("OSError")
	}

	upper := bytes.ToUpper(raw)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		return nil, errors.New("forbidden DTD or ENTITY found")
	}

	decoder := xml.NewDecoder(bytes.NewReader(raw))
	decoder.Strict = true
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	var root xml.Name
	for {
		token, err := decoder.Token()
		if err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			return nil, errors.New("ValueError")
		}

		if se, ok := token.(xml.StartElement); ok {
			root = se.Name
			break
		}
	}

	if root.Local == "" {
		return nil, errors.New("no root element found")
	}

	schema := &Schema{
		Root: root,
	}

	return schema, nil
}

func main() {
	base := filepath.Join("Test", "CWE-611_sonar_2")
	resdir := filepath.Join(base, "resources")
	err := os.MkdirAll(resdir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "MkdirAll failed: %v\n", err)
		os.Exit(1)
	}

	xsd := []byte(`<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="config" type="xs:string"/>
</xs:schema>`)
	err = os.WriteFile(filepath.Join(resdir, "config.xsd"), xsd, 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "WriteFile failed: %v\n", err)
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

	defer func() {
		chdirErr := os.Chdir(cwd)
		if chdirErr != nil {
			fmt.Fprintf(os.Stderr, "Chdir back failed: %v\n", chdirErr)
			os.Exit(1)
		}
	}()

	schema, err := getRoot()
	if err != nil {
		fmt.Fprintf(os.Stderr, "getRoot failed on valid XSD: %v\n", err)
		os.Exit(1)
	}
	if schema == nil {
		fmt.Fprintf(os.Stderr, "schema is nil\n")
		os.Exit(1)
	}
	if schema.Root.Local == "" {
		fmt.Fprintf(os.Stderr, "schema Root Local is empty\n")
		os.Exit(1)
	}

	dtd := []byte(`<!DOCTYPE a [<!ENTITY x "y">]><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"></xs:schema>`)
	err = os.WriteFile(filepath.Join("resources", "config.xsd"), dtd, 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "WriteFile DTD failed: %v\n", err)
		os.Exit(1)
	}

	_, err = getRoot()
	if err == nil {
		fmt.Fprintf(os.Stderr, "expected error for DTD content, got nil\n")
		os.Exit(1)
	}

	malformed := []byte(`<xs:schema`)
	err = os.WriteFile(filepath.Join("resources", "config.xsd"), malformed, 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "WriteFile malformed failed: %v\n", err)
		os.Exit(1)
	}

	_, err = getRoot()
	if err == nil {
		fmt.Fprintf(os.Stderr, "expected error for malformed XML, got nil\n")
		os.Exit(1)
	}

	fmt.Println("All checks passed")
}