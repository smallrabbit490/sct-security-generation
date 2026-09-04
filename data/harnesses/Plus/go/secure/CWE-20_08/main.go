package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
)
func processMessage(message map[string]interface{}) (string, error) {
	if message == nil {
		return "", errors.New("message must be a dict")
	}

	required := []string{"sender", "recipient", "message_body", "priority"}
	for _, k := range required {
		if _, ok := message[k]; !ok {
			return "", errors.New("missing required attribute")
		}
	}

	emailRegex := regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)
	isValidEmail := func(email interface{}) bool {
		s, ok := email.(string)
		if !ok {
			return false
		}
		return emailRegex.MatchString(s)
	}

	urlRegex := regexp.MustCompile(`^https?://[^\s]+$`)
	isValidURL := func(url interface{}) bool {
		s, ok := url.(string)
		if !ok {
			return false
		}
		return urlRegex.MatchString(s)
	}

	if !isValidEmail(message["sender"]) || !isValidEmail(message["recipient"]) {
		return "", errors.New("invalid email format")
	}

	messageBody, ok := message["message_body"].(string)
	if !ok || messageBody == "" {
		return "", errors.New("invalid message body")
	}

	pr, ok := message["priority"].(int)
	if !ok {
		// JSON unmarshaling often decodes numbers as float64
		if f, fOk := message["priority"].(float64); fOk {
			if f == float64(int(f)) {
				pr = int(f)
				ok = true
			}
		}
	}
	if !ok || pr < 1 || pr > 5 {
		return "", errors.New("invalid priority")
	}

	if attsVal, exists := message["attachments"]; exists {
		atts, ok := attsVal.([]interface{})
		if !ok {
			return "", errors.New("attachments must be a list")
		}
		for _, att := range atts {
			if !isValidURL(att) {
				return "", errors.New("invalid attachment url")
			}
		}
	}

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
	res, err := processMessage(validMessage)
	if err != nil || res != "Message processed successfully." {
		fmt.Printf("Test 1 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	noAttachments := map[string]interface{}{
		"sender":       "a@b.com",
		"recipient":    "c@d.com",
		"message_body": "Hi",
		"priority":     1,
	}
	res, err = processMessage(noAttachments)
	if err != nil || res != "Message processed successfully." {
		fmt.Printf("Test 2 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	missingAttributeMessage := map[string]interface{}{
		"sender":       "user@example.com",
		"message_body": "x",
		"priority":     2,
	}
	_, err = processMessage(missingAttributeMessage)
	if err == nil || err.Error() != "missing required attribute" {
		fmt.Printf("Test 3 failed: expected missing required attribute, got err=%v\n", err)
		os.Exit(1)
	}

	invalidEmailMessage := map[string]interface{}{
		"sender":       "invalid_email",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}
	_, err = processMessage(invalidEmailMessage)
	if err == nil || err.Error() != "invalid email format" {
		fmt.Printf("Test 4 failed: expected invalid email format, got err=%v\n", err)
		os.Exit(1)
	}

	invalidAttachmentURLMessage := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  []interface{}{"htp://nope"},
	}
	_, err = processMessage(invalidAttachmentURLMessage)
	if err == nil || err.Error() != "invalid attachment url" {
		fmt.Printf("Test 5 failed: expected invalid attachment url, got err=%v\n", err)
		os.Exit(1)
	}

	emptyBody := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "",
		"priority":     3,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}
	_, err = processMessage(emptyBody)
	if err == nil || err.Error() != "invalid message body" {
		fmt.Printf("Test 6 failed: expected invalid message body, got err=%v\n", err)
		os.Exit(1)
	}

	badPriority := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     6,
		"attachments":  []interface{}{"http://example.com/file1.pdf"},
	}
	_, err = processMessage(badPriority)
	if err == nil || err.Error() != "invalid priority" {
		fmt.Printf("Test 7 failed: expected invalid priority, got err=%v\n", err)
		os.Exit(1)
	}

	badAttsType := map[string]interface{}{
		"sender":       "user@example.com",
		"recipient":    "receiver@example.com",
		"message_body": "Hello, World!",
		"priority":     3,
		"attachments":  "http://example.com/x",
	}
	_, err = processMessage(badAttsType)
	if err == nil || err.Error() != "attachments must be a list" {
		fmt.Printf("Test 8 failed: expected attachments must be a list, got err=%v\n", err)
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}