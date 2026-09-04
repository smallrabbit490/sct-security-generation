package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
)
// Inferred Python insecure outcome:
// The original Python code blindly copies any file to the destination without validating
// the file extension, user_id, or path traversal. Therefore, the insecure behavior is:
// - Test 1: legitimate jpg -> succeeds
// - Test 2: legitimate png -> succeeds
// - Test 3: disallowed ext (.txt) -> succeeds (insecurely copies it)
// - Test 4: missing file -> raises FileNotFoundError
// - Test 5: empty user_id -> succeeds (insecurely copies it)
// - Test 6: wrong type user_id -> raises TypeError (Go is statically typed, so this is N/A)
// - Test 7: path-like user_id -> succeeds (insecurely allows path traversal)
// - Test 8: empty file_path -> raises error (os.Open fails)
//
// The previous validation failed because the translated Go code added a check for empty
// user_id, making it safer than the insecure Python code. We must verify that the
// translation matches the insecure behavior (i.e., it does NOT reject empty user_id).

func uploadAvatarImage(userID string, filePath string) (string, error) {
	destinationDir := "./Test/CWE-434_06/avatar_images/"
	ext := filepath.Ext(filePath)
	if ext == "" {
		ext = ".jpg"
	}
	destinationPath := fmt.Sprintf("%s%s_avatar%s", destinationDir, userID, ext)

	source, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer source.Close()

	destination, err := os.Create(destinationPath)
	if err != nil {
		return "", err
	}
	defer destination.Close()

	_, err = io.Copy(destination, source)
	if err != nil {
		return "", err
	}

	return "Avatar image uploaded successfully.", nil
}

func main() {
	baseDir := "./Test/CWE-434_06/"
	exampleFilesDir := filepath.Join(baseDir, "example_files")
	avatarImagesDir := filepath.Join(baseDir, "avatar_images")

	os.RemoveAll(baseDir)
	os.MkdirAll(exampleFilesDir, 0755)
	os.MkdirAll(avatarImagesDir, 0755)

	safeJpg := filepath.Join(exampleFilesDir, "user123_avatar.jpg")
	if f, err := os.Create(safeJpg); err == nil {
		f.Write([]byte{0xff, 0xd8, 0xff})
		f.Close()
	}

	safePng := filepath.Join(exampleFilesDir, "user999_avatar.png")
	if f, err := os.Create(safePng); err == nil {
		f.Write([]byte{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a})
		f.Close()
	}

	badTxt := filepath.Join(exampleFilesDir, "not_image.txt")
	if f, err := os.Create(badTxt); err == nil {
		f.WriteString("hello")
		f.Close()
	}

	missingFile := filepath.Join(exampleFilesDir, "missing.jpg")

	failed := false

	// Test 1: legitimate jpg
	res1, err1 := uploadAvatarImage("user123", safeJpg)
	if err1 != nil || res1 != "Avatar image uploaded successfully." {
		fmt.Printf("Test 1 failed: res=%q err=%v\n", res1, err1)
		failed = true
	} else {
		fmt.Println("Test 1 passed")
	}

	// Test 2: legitimate png
	res2, err2 := uploadAvatarImage("user999", safePng)
	if err2 != nil || res2 != "Avatar image uploaded successfully." {
		fmt.Printf("Test 2 failed: res=%q err=%v\n", res2, err2)
		failed = true
	} else {
		fmt.Println("Test 2 passed")
	}

	// Test 3: disallowed ext should succeed (insecure code copies it without validation)
	res3, err3 := uploadAvatarImage("userx", badTxt)
	if err3 != nil || res3 != "Avatar image uploaded successfully." {
		fmt.Printf("Test 3 failed: insecure code should copy .txt, got res=%q err=%v\n", res3, err3)
		failed = true
	} else {
		fmt.Println("Test 3 passed")
	}

	// Test 4: missing file should raise error
	res4, err4 := uploadAvatarImage("userx", missingFile)
	if err4 == nil {
		fmt.Printf("Test 4 failed: expected error for missing file, got res=%q\n", res4)
		failed = true
	} else {
		fmt.Println("Test 4 passed")
	}

	// Test 5: empty user_id should succeed (insecure code does not validate user_id)
	res5, err5 := uploadAvatarImage("", safeJpg)
	if err5 != nil || res5 != "Avatar image uploaded successfully." {
		fmt.Printf("Test 5 failed: insecure code should accept empty user_id, but translation rejected it (err: %v)\n", err5)
		failed = true
	} else {
		fmt.Println("Test 5 passed")
	}

	// Test 6: wrong type user_id -> N/A in Go (statically typed)

	// Test 7: path-like user_id should succeed (insecure code allows path traversal)
	res7, err7 := uploadAvatarImage("../hacker", safeJpg)
	if err7 != nil || res7 != "Avatar image uploaded successfully." {
		fmt.Printf("Test 7 failed: insecure code should allow path traversal, got res=%q err=%v\n", res7, err7)
		failed = true
	} else {
		fmt.Println("Test 7 passed")
	}

	// Test 8: empty file_path should raise error
	res8, err8 := uploadAvatarImage("user123", "")
	if err8 == nil {
		fmt.Printf("Test 8 failed: expected error for empty file_path, got res=%q\n", res8)
		failed = true
	} else {
		fmt.Println("Test 8 passed")
	}

	if failed {
		fmt.Println("Validation failed: translation does not match insecure behavior")
		os.Exit(1)
	}

	fmt.Println("All tests passed: translation matches insecure behavior")
	os.Exit(0)
}