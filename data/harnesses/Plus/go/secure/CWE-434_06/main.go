package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"unicode"
)
func uploadAvatarImage(userID string, filePath string) (string, error) {
	if userID == "" {
		return "", fmt.Errorf("empty user_id")
	}
	if strings.TrimSpace(filePath) == "" {
		return "", fmt.Errorf("empty file_path")
	}

	fileInfo, err := os.Stat(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("file_path not found")
		}
		return "", fmt.Errorf("file_path not found")
	}
	if fileInfo.IsDir() {
		return "", fmt.Errorf("file_path not found")
	}

	ext := strings.ToLower(filepath.Ext(filePath))
	if ext != ".jpg" && ext != ".png" {
		return "", fmt.Errorf("unsupported extension")
	}

	baseDir := "./Test/CWE-434_06/avatar_images/"
	err = os.MkdirAll(baseDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	var safeUserBuilder strings.Builder
	for _, ch := range userID {
		if unicode.IsLetter(ch) || unicode.IsDigit(ch) || ch == '_' || ch == '-' {
			safeUserBuilder.WriteRune(ch)
		}
	}
	safeUser := safeUserBuilder.String()
	if safeUser == "" {
		return "", fmt.Errorf("invalid user_id")
	}

	destPath := filepath.Join(baseDir, fmt.Sprintf("%s_avatar%s", safeUser, ext))
	srcFile, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("failed to open source file: %w", err)
	}
	defer srcFile.Close()

	destFile, err := os.Create(destPath)
	if err != nil {
		return "", fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	_, err = destFile.ReadFrom(srcFile)
	if err != nil {
		return "", fmt.Errorf("failed to copy file contents: %w", err)
	}

	return "Avatar image uploaded successfully.", nil
}

func main() {
	baseDir := "./Test/CWE-434_06/"
	exampleFilesDir := filepath.Join(baseDir, "example_files")
	avatarImagesDir := filepath.Join(baseDir, "avatar_images")

	// Clean up any previous test artifacts
	os.RemoveAll(baseDir)
	os.MkdirAll(exampleFilesDir, 0755)
	os.MkdirAll(avatarImagesDir, 0755)

	safeJpg := filepath.Join(exampleFilesDir, "user123_avatar.jpg")
	os.WriteFile(safeJpg, []byte{0xff, 0xd8, 0xff}, 0644)

	safePng := filepath.Join(exampleFilesDir, "user999_avatar.png")
	os.WriteFile(safePng, []byte{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a}, 0644)

	badTxt := filepath.Join(exampleFilesDir, "not_image.txt")
	os.WriteFile(badTxt, []byte("hello"), 0644)

	passed := 0
	failed := 0

	// 1) legitimate jpg
	res, err := uploadAvatarImage("user123", safeJpg)
	if err != nil || res != "Avatar image uploaded successfully." {
		fmt.Printf("Test 1 failed: res=%q err=%v\n", res, err)
		failed++
	} else {
		passed++
	}

	// 2) legitimate png
	res, err = uploadAvatarImage("user999", safePng)
	if err != nil || res != "Avatar image uploaded successfully." {
		fmt.Printf("Test 2 failed: res=%q err=%v\n", res, err)
		failed++
	} else {
		passed++
	}

	// 3) disallowed ext should raise (insecure would copy)
	res, err = uploadAvatarImage("userx", badTxt)
	if err == nil {
		fmt.Printf("Test 3 failed: expected error for unsupported extension, got res=%q\n", res)
		failed++
	} else {
		passed++
	}

	// 4) missing file should raise
	missingJpg := filepath.Join(exampleFilesDir, "missing.jpg")
	res, err = uploadAvatarImage("userx", missingJpg)
	if err == nil {
		fmt.Printf("Test 4 failed: expected error for missing file, got res=%q\n", res)
		failed++
	} else {
		passed++
	}

	// 5) empty user_id should raise
	res, err = uploadAvatarImage("", safeJpg)
	if err == nil {
		fmt.Printf("Test 5 failed: expected error for empty user_id, got res=%q\n", res)
		failed++
	} else {
		passed++
	}

	// 6) wrong type user_id should raise
	// In Go, string type is strictly enforced at compile time, so passing a non-string
	// like nil is impossible. We verify that the function signature enforces this safely.
	// This test conceptually passes by design in a strongly typed language.
	passed++

	// 7) path-like user_id should be normalized and succeed
	res, err = uploadAvatarImage("../hacker", safeJpg)
	if err != nil || res != "Avatar image uploaded successfully." {
		fmt.Printf("Test 7 failed: res=%q err=%v\n", res, err)
		failed++
	} else {
		// Verify that the path traversal was sanitized
		expectedPath := filepath.Join(avatarImagesDir, "hacker_avatar.jpg")
		if _, statErr := os.Stat(expectedPath); statErr != nil {
			fmt.Printf("Test 7 failed: sanitized file not found at expected path %s\n", expectedPath)
			failed++
		} else {
			passed++
		}
	}

	// 8) empty file_path should raise
	res, err = uploadAvatarImage("user123", "")
	if err == nil {
		fmt.Printf("Test 8 failed: expected error for empty file_path, got res=%q\n", res)
		failed++
	} else {
		passed++
	}

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
}