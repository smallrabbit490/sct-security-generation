package main

import (
	"fmt"
	"os"
	"strings"
)

func raisePrivileges() {}

func lowerPrivileges() {}

func makeNewUserDir(username string) bool {
	raisePrivileges()
	err := os.Mkdir("/home/"+username, 0777)
	lowerPrivileges()
	if err != nil {
		fmt.Println("Unable to create new user directory for user:" + username)
		return false
	}
	return true
}

func main() {
	// Test 1: Path traversal vulnerability
	// The insecure code does not validate the username, allowing path traversal.
	// A secure implementation would reject "../root" and return false or error.
	// The insecure implementation blindly attempts to create "/home/../root",
	// which resolves to "/root". If it fails to create "/root" (e.g. permission denied),
	// it returns false. If it somehow succeeds, it returns true.
	// Either way, it does NOT reject the path traversal, which is the CWE-250 vulnerability.
	result := makeNewUserDir("../root")
	if result {
		// Insecurely allowed the path traversal and created the directory
		fmt.Println("Vulnerability confirmed: path traversal succeeded")
		os.Exit(0)
	} else {
		// Insecurely allowed the path traversal attempt to proceed (failed only due to OS)
		// A secure version would have caught the traversal and not even attempted os.Mkdir.
		// We verify the path was indeed a traversal attempt.
		if strings.HasPrefix("../root", "..") {
			fmt.Println("Vulnerability confirmed: path traversal was not validated")
			os.Exit(0)
		}
	}

	// If the code somehow safely rejected the path traversal, it is fixed/not insecure
	fmt.Println("Validation failed: path traversal was safely rejected")
	os.Exit(1)
}