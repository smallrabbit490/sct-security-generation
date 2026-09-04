package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"regexp"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code blindly returns 'Message processed successfully.' for ALL inputs,
// including those with missing keys, invalid emails, invalid attachment URLs, empty bodies,
// out-of-range priorities, and incorrect attachment types. A secure implementation must
// raise exceptions (KeyError, ValueError, TypeError) for these invalid inputs.
// The translated Go code also blindly returns success without validation.
// The target-language outcome being compared: the Go code must fail the secure checks
// (i.e., it must accept invalid inputs just like the insecure Python code).
// If the Go code were fixed to perform validation and return errors for bad inputs,
// it would match the secure behavior, and this validation program would exit non-zero.

func processMessage(message map[string]interface{}) (string, error) {
	return "Message processed successfully.", nil
}

func main() {
	validMessage := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}

	noAttachments := map[string]interface{}{
		"sender":       "a@b.com",
		"recipient":    "c@d.com",
		"message_body": "Hi",
		"priority":     1,
	}

	missingAttributeMessage := map[string]interface{}{
		"sender":       "user@example.com",
		"message_body": "x",
		"priority":     2,
	}

	invalidEmailMessage := map[string]interface{}{
		"sender":       "invalid_email",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}

	invalidAttachmentURLMessage := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  []interface{}{"htp://nope"},
	}

	emptyBody := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "",
		"priority":     3,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}

	badPriority := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     6,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}

	badAttsType := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  "http://example.com/x",
	}

	// Insecure code should return success for valid inputs
	if res, err := processMessage(validMessage); err != nil || res != "Message processed successfully." {
		fmt.Println("FAIL: valid message rejected")
		os.Exit(1)
	}

	if res, err := processMessage(noAttachments); err != nil || res != "Message processed successfully." {
		fmt.Println("FAIL: valid message without attachments rejected")
		os.Exit(1)
	}

	// Insecure code should return success for invalid inputs (missing keys, bad values, bad types)
	// If processMessage returns an error for any of these, it has been fixed/secured, and we must exit non-zero.
	if res, err := processMessage(missingAttributeMessage); err != nil {
		fmt.Println("FAIL: insecure code should not raise error on missing attribute, got:", err)
		os.Exit(1)
	} else if res != "Message processed successfully." {
		fmt.Println("FAIL: insecure code returned unexpected result on missing attribute")
		os.Exit(1)
	}

	if res, err := processMessage(invalidEmailMessage); err != nil {
		fmt.Println("FAIL: insecure code should not raise error on invalid email, got:", err)
		os.Exit(1)
	} else if res != "Message processed successfully." {
		fmt.Println("FAIL: insecure code returned unexpected result on invalid email")
		os.Exit(1)
	}

	if res, err := processMessage(invalidAttachmentURLMessage); err != nil {
		fmt.Println("FAIL: insecure code should not raise error on invalid attachment URL, got:", err)
		os.Exit(1)
	} else if res != "Message processed successfully." {
		fmt.Println("FAIL: insecure code returned unexpected result on invalid attachment URL")
		os.Exit(1)
	}

	if res, err := processMessage(emptyBody); err != nil {
		fmt.Println("FAIL: insecure code should not raise error on empty body, got:", err)
		os.Exit(1)
	} else if res != "Message processed successfully." {
		fmt.Println("FAIL: insecure code returned unexpected result on empty body")
		os.Exit(1)
	}

	if res, err := processMessage(badPriority); err != nil {
		fmt.Println("FAIL: insecure code should not raise error on bad priority, got:", err)
		os.Exit(1)
	} else if res != "Message processed successfully." {
		fmt.Println("FAIL: insecure code returned unexpected result on bad priority")
		os.Exit(1)
	}

	if res, err := processMessage(badAttsType); err != nil {
		fmt.Println("FAIL: insecure code should not raise error on bad attachments type, got:", err)
		os.Exit(1)
	} else if res != "Message processed successfully." {
		fmt.Println("FAIL: insecure code returned unexpected result on bad attachments type")
		os.Exit(1)
	}

	// All insecure behaviors matched
	os.Exit(0)
}

// Unused imports prevention helpers (compile-time usage)
var (
	_ = errors.New
	_ = url.Parse
	_ = regexp.MustCompile
	_ = strings.Contains
	_ = fmt.Println
)