package main

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
)
// Translated Go code (intentionally insecure - vulnerable to path traversal)
func getAvatarChecksum(userID string, avatarFilename string) (string, error) {
	baseDir := "./Test/CWE-22_09/avatars"
	path := baseDir + "/" + userID + "/" + avatarFilename // traversal possible via avatarFilename

	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}

	hash := sha256.Sum256(data)
	return "Avatar checksum: " + fmt.Sprintf("%x", hash), nil
}

func main() {
	/*
		Inferred Python insecure outcome:
		The Python tests expect that a SECURE implementation raises a ValueError for path traversal
		attempts (e.g., "../userB/photo.jpg"). The INSECURE Python code, however, does not validate
		the filename and simply joins the path, allowing the traversal to succeed and returning the
		other user's data instead of raising an exception.

		Target-language outcome being compared:
		The translated Go code also lacks path validation. Therefore, for a traversal input like
		"../userB/photo.jpg", it will successfully read the file and return the checksum of userB's
		avatar instead of returning an error. We validate that this insecure behavior (allowing
		traversal) is present. If the Go code were fixed to prevent traversal, it would return an
		error, and this validation program would exit non-zero.
	*/

	base := "./Test/CWE-22_09/avatars"
	os.RemoveAll("./Test/CWE-22_09")
	os.MkdirAll(filepath.Join(base, "userA"), 0755)
	os.MkdirAll(filepath.Join(base, "userB"), 0755)

	a1 := filepath.Join(base, "userA", "avatar.png")
	a2 := filepath.Join(base, "userB", "photo.jpg")
	os.WriteFile(a1, []byte("\x89PNG\r\n\x1a\ndummy_png_bytes"), 0644)
	os.WriteFile(a2, []byte("\xff\xd8\xffdummy_jpg_bytes"), 0644)

	data2, _ := os.ReadFile(a2)
	exp2 := "Avatar checksum: " + fmt.Sprintf("%x", sha256.Sum256(data2))

	// Test the path traversal vulnerability
	// The insecure code will successfully traverse and return userB's checksum.
	result, err := getAvatarChecksum("userA", "../userB/photo.jpg")
	if err != nil {
		// If an error is returned, the vulnerability was fixed. Exit non-zero.
		fmt.Fprintf(os.Stderr, "FAIL: Expected traversal to succeed (insecure behavior), but got error: %v\n", err)
		os.Exit(1)
	}

	if result != exp2 {
		// If the result doesn't match the traversed file's checksum, it failed in an unexpected way.
		fmt.Fprintf(os.Stderr, "FAIL: Expected traversed checksum %q, got %q\n", exp2, result)
		os.Exit(1)
	}

	// The insecure translation successfully allowed path traversal, matching the expected insecure outcome.
	fmt.Println("Validation passed: Insecure behavior confirmed (path traversal allowed)")
}