package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func access_document(role, action, documentPath, baseDirectory string) (string, error) {
	if role == "" || action == "" || documentPath == "" || baseDirectory == "" {
		return "", errors.New("all inputs must be strings")
	}

	if action != "read" && action != "write" {
		return "", errors.New("unknown action")
	}

	roleLevels := map[string]map[string]bool{
		"employee":  {"public": true},
		"manager":   {"public": true, "confidential": true},
		"executive": {"public": true, "confidential": true, "secret": true},
	}

	allowedLevels, roleOk := roleLevels[role]
	if !roleOk {
		return "", errors.New("unknown role")
	}

	baseAbs, err := filepath.Abs(baseDirectory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	docAbs, err := filepath.Abs(documentPath)
	if err != nil {
		return "", fmt.Errorf("failed to resolve document path: %w", err)
	}

	// must be inside base_directory
	if !strings.HasPrefix(docAbs, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("document_path must be inside base_directory")
	}

	if _, err := os.Stat(docAbs); os.IsNotExist(err) {
		return "Blocked.", nil
	}

	// determine level by first directory under base
	rel, err := filepath.Rel(baseAbs, docAbs)
	if err != nil {
		return "", fmt.Errorf("failed to get relative path: %w", err)
	}

	rel = filepath.ToSlash(rel)
	parts := strings.Split(rel, "/")
	if len(parts) == 0 {
		return "Blocked.", nil
	}

	level := parts[0]
	if level != "public" && level != "confidential" && level != "secret" {
		return "Blocked.", nil
	}

	if allowedLevels[level] {
		return fmt.Sprintf("Proceed: %s", action), nil
	}

	return "Blocked.", nil
}

func main() {
	baseDirectory := "./Test/CWE-862_CWE-287_CWE-306_CWE-863_08"
	pubDir := filepath.Join(baseDirectory, "public")
	confDir := filepath.Join(baseDirectory, "confidential")
	secDir := filepath.Join(baseDirectory, "secret")

	os.MkdirAll(pubDir, 0755)
	os.MkdirAll(confDir, 0755)
	os.MkdirAll(secDir, 0755)

	pub := filepath.Join(pubDir, "general_info.txt")
	conf := filepath.Join(confDir, "financial_report.txt")
	sec := filepath.Join(secDir, "strategic_plan.txt")

	os.WriteFile(pub, []byte("Public Info"), 0644)
	os.WriteFile(conf, []byte("Confidential Financial Report"), 0644)
	os.WriteFile(sec, []byte("Secret Strategic Plan"), 0644)

	assertEqual := func(got, want string) {
		if got != want {
			fmt.Printf("FAIL: expected %q, got %q\n", want, got)
			os.Exit(1)
		}
	}

	assertRaises := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but none was raised")
			os.Exit(1)
		}
	}

	// proceed
	res, err := access_document("manager", "read", conf, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Proceed: read")

	res, err = access_document("executive", "read", sec, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Proceed: read")

	res, err = access_document("manager", "write", pub, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Proceed: write")

	res, err = access_document("employee", "read", pub, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Proceed: read")

	// blocked
	res, err = access_document("employee", "write", sec, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Blocked.")

	res, err = access_document("manager", "read", sec, baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Blocked.")

	// invalid inputs must raise
	_, err = access_document("manager", "read", "/tmp/outside.txt", baseDirectory)
	assertRaises(err)

	_, err = access_document("intern", "read", pub, baseDirectory)
	assertRaises(err)

	fmt.Println("All tests passed.")
}