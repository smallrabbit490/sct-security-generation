package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
)

var (
	raisePrivileges func()
	lowerPrivileges func()
	privilegesSet   bool
	usernameRegex   = regexp.MustCompile("^[a-z_][a-z0-9_-]{0,31}$")
)

func makeNewUserDir(username string) (bool, error) {
	if !usernameRegex.MatchString(username) {
		return false, errors.New("invalid username")
	}

	if !privilegesSet || raisePrivileges == nil || lowerPrivileges == nil {
		return false, errors.New("privilege functions not set")
	}

	path := "/home/" + username
	raised := false
	defer func() {
		if raised {
			lowerPrivileges()
		}
	}()

	raisePrivileges()
	raised = true

	err := os.Mkdir(path, 0755)
	if err != nil {
		if os.IsExist(err) {
			return false, err
		}
		return false, errors.New("failed to create directory")
	}

	return true, nil
}

func main() {
	calls := map[string]int{"raise": 0, "lower": 0, "mkdir": 0}

	// Test 1: Successful directory creation
	privilegesSet = true
	raisePrivileges = func() { calls["raise"]++ }
	lowerPrivileges = func() { calls["lower"]++ }

	// Clean up any previous test artifacts
	os.RemoveAll("/home/alice")

	ok, err := makeNewUserDir("alice")
	if !ok || err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected ok=true, err=nil; got ok=%v, err=%v\n", ok, err)
		os.Exit(1)
	}
	if calls["raise"] != 1 || calls["lower"] != 1 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected raise=1, lower=1; got raise=%d, lower=%d\n", calls["raise"], calls["lower"])
		os.Exit(1)
	}

	// Test 2: Directory already exists
	calls["raise"] = 0
	calls["lower"] = 0

	_, err = makeNewUserDir("alice")
	if err == nil || !os.IsExist(err) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected FileExistsError; got err=%v\n", err)
		os.Exit(1)
	}
	if calls["raise"] != 1 || calls["lower"] != 1 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected raise=1, lower=1; got raise=%d, lower=%d\n", calls["raise"], calls["lower"])
		os.Exit(1)
	}

	// Test 3: Path traversal attempt
	calls["raise"] = 0
	calls["lower"] = 0

	_, err = makeNewUserDir("../root")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for path traversal; got err=nil\n")
		os.Exit(1)
	}
	if calls["raise"] != 0 || calls["lower"] != 0 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected raise=0, lower=0; got raise=%d, lower=%d\n", calls["raise"], calls["lower"])
		os.Exit(1)
	}

	// Test 4: Invalid type (empty string in Go, equivalent to rejecting non-string)
	calls["raise"] = 0
	calls["lower"] = 0

	_, err = makeNewUserDir("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for empty string; got err=nil\n")
		os.Exit(1)
	}
	if calls["raise"] != 0 || calls["lower"] != 0 {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected raise=0, lower=0; got raise=%d, lower=%d\n", calls["raise"], calls["lower"])
		os.Exit(1)
	}

	// Clean up
	os.RemoveAll("/home/alice")

	fmt.Println("All tests passed")
}