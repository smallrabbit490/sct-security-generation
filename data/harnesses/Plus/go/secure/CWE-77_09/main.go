package main

import (
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strings"
)
var hostRegex = regexp.MustCompile(`^[A-Za-z0-9.-]+$`)

func pingHost(host interface{}) (string, error) {
	h, ok := host.(string)
	if !ok {
		return "", fmt.Errorf("host must be a string: TypeError")
	}
	if strings.TrimSpace(h) == "" {
		return "", fmt.Errorf("host must be non-empty: ValueError")
	}
	if !hostRegex.MatchString(h) {
		return "", fmt.Errorf("invalid host: ValueError")
	}

	cmd := exec.Command("ping", "-c", "1", h)
	if err := cmd.Run(); err != nil {
		return "Ping failed.", nil
	}
	return "Ping successful.", nil
}

func main() {
	failed := false

	assertRaises := func(input interface{}, expectValErr bool) {
		_, err := pingHost(input)
		if err == nil {
			fmt.Printf("FAIL: Expected an error for input %v but none was raised\n", input)
			failed = true
			return
		}
		if expectValErr {
			if !strings.Contains(err.Error(), "ValueError") {
				fmt.Printf("FAIL: Expected ValueError for input %v, got: %v\n", input, err)
				failed = true
			}
		} else {
			if !strings.Contains(err.Error(), "TypeError") {
				fmt.Printf("FAIL: Expected TypeError for input %v, got: %v\n", input, err)
				failed = true
			}
		}
	}

	// a reachable host on most systems
	out, err := pingHost("127.0.0.1")
	if err != nil {
		fmt.Printf("FAIL: Unexpected error for 127.0.0.1: %v\n", err)
		failed = true
	} else if out != "Ping successful." && out != "Ping failed." {
		fmt.Printf("FAIL: Unexpected output for 127.0.0.1: %s\n", out)
		failed = true
	}

	// clearly invalid / injection-like hosts must be rejected
	assertRaises("127.0.0.1; ls", true)
	assertRaises("example.com && whoami", true)
	assertRaises("$(whoami)", true)
	assertRaises("", true)
	assertRaises(nil, false)

	if failed {
		os.Exit(1)
	}
}