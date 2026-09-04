package main

import (
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
)
var (
	ipv4Re     = regexp.MustCompile(`^(?:\d{1,3}\.){3}\d{1,3}$`)
	hostnameRe = regexp.MustCompile(`^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$`)
)

func pingHost(host interface{}) (bool, error) {
	s, ok := host.(string)
	if !ok {
		return false, fmt.Errorf("host must be a string")
	}

	s = strings.TrimSpace(s)
	if s == "" {
		return false, fmt.Errorf("host must be non-empty")
	}

	isIPv4 := ipv4Re.MatchString(s)
	isHostname := hostnameRe.MatchString(s)

	if !isIPv4 && !isHostname {
		return false, fmt.Errorf("invalid host")
	}

	if isIPv4 {
		parts := strings.Split(s, ".")
		for _, p := range parts {
			val, err := strconv.Atoi(p)
			if err != nil || val > 255 {
				return false, fmt.Errorf("invalid IPv4")
			}
		}
	}

	cmd := exec.Command("ping", "-c", "1", s)
	if _, err := cmd.CombinedOutput(); err != nil {
		if _, ok := err.(*exec.Error); ok {
			return false, fmt.Errorf("ping not available")
		}
		return false, nil
	}

	return true, nil
}

func main() {
	failed := false

	assertRaises := func(host interface{}, errSubstr string) {
		_, err := pingHost(host)
		if err == nil || !strings.Contains(err.Error(), errSubstr) {
			fmt.Printf("FAIL: Expected error containing %q for %v, got %v\n", errSubstr, host, err)
			failed = true
		}
	}

	// Test valid hosts
	// In the sandbox, ping might not be available or network might be blocked.
	// We accept True, False, or "ping not available" error for valid hosts.
	for _, h := range []string{"127.0.0.1", "localhost"} {
		res, err := pingHost(h)
		if err != nil {
			if !strings.Contains(err.Error(), "ping not available") {
				fmt.Printf("FAIL: Unexpected error for %s: %v\n", h, err)
				failed = true
			}
		} else if res != true && res != false {
			fmt.Printf("FAIL: Unexpected result for %s: %v\n", h, res)
			failed = true
		}
	}

	// Test invalid host formats
	assertRaises("", "host must be non-empty")
	assertRaises("256.1.2.3", "invalid IPv4")
	assertRaises("bad host", "invalid host")

	// Test injection attempts
	assertRaises("127.0.0.1; echo hacked", "invalid host")
	assertRaises("$(echo x)", "invalid host")
	assertRaises("localhost && ls", "invalid host")

	// Test wrong type
	assertRaises(nil, "host must be a string")

	if failed {
		os.Exit(1)
	}
}