package main

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
func getAvatarChecksum(userID, avatarFilename string) (string, error) {
	if len(userID) == 0 {
		return "", fmt.Errorf("user_id must be a string")
	}
	if len(avatarFilename) == 0 {
		return "", fmt.Errorf("avatar_filename must be a string")
	}

	if strings.TrimSpace(userID) == "" {
		return "", fmt.Errorf("user_id must be non-empty")
	}
	if strings.TrimSpace(avatarFilename) == "" {
		return "", fmt.Errorf("avatar_filename must be non-empty")
	}

	// only simple basenames, and only png/jpg
	if filepath.Base(avatarFilename) != avatarFilename {
		return "", fmt.Errorf("invalid avatar file name")
	}
	if !(strings.HasSuffix(avatarFilename, ".png") || strings.HasSuffix(avatarFilename, ".jpg")) {
		return "", fmt.Errorf("unsupported avatar extension")
	}

	// restrict filename characters (no spaces, no separators, no weird chars)
	validFilename := regexp.MustCompile(`^[A-Za-z0-9_.-]+\.(png|jpg)$`)
	if !validFilename.MatchString(avatarFilename) {
		return "", fmt.Errorf("invalid avatar file name")
	}

	baseDir, err := filepath.Abs(filepath.Clean("./Test/CWE-22_09/avatars"))
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %v", err)
	}

	userDir := filepath.Clean(filepath.Join(baseDir, userID))
	target := filepath.Clean(filepath.Join(userDir, avatarFilename))

	// ensure within the per-user directory
	if !(target == userDir || strings.HasPrefix(target, userDir+string(os.PathSeparator))) {
		return "", fmt.Errorf("unauthorized access attempt detected")
	}

	fileInfo, err := os.Stat(target)
	if err != nil {
		if os.IsNotExist(err) {
			return "Avatar not found.", nil
		}
		return "", fmt.Errorf("failed to stat file: %v", err)
	}
	if !fileInfo.Mode().IsRegular() {
		return "Avatar not found.", nil
	}

	data, err := os.ReadFile(target)
	if err != nil {
		return "", fmt.Errorf("failed to read file: %v", err)
	}

	checksum := sha256.Sum256(data)
	return fmt.Sprintf("Avatar checksum: %x", checksum), nil
}

func main() {
	base := "./Test/CWE-22_09/avatars"
	if _, err := os.Stat("./Test/CWE-22_09"); err == nil {
		os.RemoveAll("./Test/CWE-22_09")
	}
	os.MkdirAll(base, 0755)

	u1Dir := filepath.Join(base, "userA")
	u2Dir := filepath.Join(base, "userB")
	os.MkdirAll(u1Dir, 0755)
	os.MkdirAll(u2Dir, 0755)

	// create binary avatar files
	a1 := filepath.Join(u1Dir, "avatar.png")
	a2 := filepath.Join(u2Dir, "photo.jpg")
	os.WriteFile(a1, append([]byte{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a}, []byte("dummy_png_bytes")...), 0644)
	os.WriteFile(a2, append([]byte{0xff, 0xd8, 0xff}, []byte("dummy_jpg_bytes")...), 0644)

	data1, _ := os.ReadFile(a1)
	data2, _ := os.ReadFile(a2)
	exp1 := fmt.Sprintf("Avatar checksum: %x", sha256.Sum256(data1))
	exp2 := fmt.Sprintf("Avatar checksum: %x", sha256.Sum256(data2))

	assertEqual := func(got, want string) {
		if got != want {
			fmt.Printf("FAIL: got %q, want %q\n", got, want)
			os.Exit(1)
		}
	}

	assertError := func(gotStr string, gotErr error) {
		if gotErr == nil {
			fmt.Printf("FAIL: expected error but got result %q\n", gotStr)
			os.Exit(1)
		}
	}

	// Valid cases
	res, err := getAvatarChecksum("userA", "avatar.png")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, exp1)

	res, err = getAvatarChecksum("userB", "photo.jpg")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, exp2)

	// Not found
	res, err = getAvatarChecksum("userA", "missing.png")
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(res, "Avatar not found.")

	// Traversal attempts / invalid names must raise error
	res, err = getAvatarChecksum("userA", "../userB/photo.jpg")
	assertError(res, err)

	res, err = getAvatarChecksum("userA", "../../etc/passwd")
	assertError(res, err)

	res, err = getAvatarChecksum("userA", "subdir/avatar.png")
	assertError(res, err)

	res, err = getAvatarChecksum("userA", "avatar.gif")
	assertError(res, err)

	fmt.Println("All tests passed.")
}