package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// FileObj simulates the Python file_obj with a filename and a read method returning bytes.
type FileObj struct {
	Filename string
	Data     []byte
}

// Read returns the bytes of the file object.
func (f *FileObj) Read() []byte {
	return f.Data
}

func uploadAudioSample(fileObj *FileObj, uploadDir string) (string, error) {
	if fileObj == nil {
		return "", errors.New("file_obj is required")
	}
	if strings.TrimSpace(uploadDir) == "" {
		return "", errors.New("invalid upload_dir")
	}

	filename := fileObj.Filename
	if strings.TrimSpace(filename) == "" {
		return "", errors.New("empty filename")
	}

	base := filepath.Base(filename)
	if base == "" || base == "." || base == ".." {
		return "", errors.New("invalid filename")
	}

	if !strings.Contains(base, ".") {
		return "", errors.New("missing extension")
	}
	if !strings.HasSuffix(strings.ToLower(base), ".wav") {
		return "", errors.New("unsupported extension")
	}

	data := fileObj.Read()
	if len(data) < 12 {
		return "", errors.New("invalid wav data")
	}
	if !bytes.HasPrefix(data, []byte("RIFF")) || !bytes.Equal(data[8:12], []byte("WAVE")) {
		return "", errors.New("invalid wav signature")
	}

	const maxFileSize = 2 * 1024 * 1024 // 2MB
	if len(data) > maxFileSize {
		return "", errors.New("file size exceeds 2MB limit")
	}

	err := os.MkdirAll(uploadDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create upload directory: %w", err)
	}

	dest := filepath.Join(uploadDir, base)
	absDest, err := filepath.Abs(dest)
	if err != nil {
		return "", fmt.Errorf("failed to resolve destination path: %w", err)
	}

	absUploadDir, err := filepath.Abs(uploadDir)
	if err != nil {
		return "", fmt.Errorf("failed to resolve upload directory path: %w", err)
	}

	// Path traversal check
	if absDest != absUploadDir && !strings.HasPrefix(absDest, absUploadDir+string(os.PathSeparator)) {
		return "", errors.New("path traversal detected")
	}

	err = os.WriteFile(absDest, data, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	return fmt.Sprintf("Audio uploaded to %s", absDest), nil
}

func assertRaises(fn func() (string, error)) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Panic occurred: %v\n", r)
			os.Exit(1)
		}
	}()
	_, err := fn()
	if err == nil {
		fmt.Println("Expected an error but none was raised")
		os.Exit(1)
	}
}

func main() {
	root := "./Test/CWE-434_02"
	os.RemoveAll(root)
	err := os.MkdirAll(root, 0755)
	if err != nil {
		fmt.Printf("Failed to create root dir: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(root)

	uploadDir := filepath.Join(root, "audio")
	err = os.MkdirAll(uploadDir, 0755)
	if err != nil {
		fmt.Printf("Failed to create upload dir: %v\n", err)
		os.Exit(1)
	}

	// Minimal WAV-like header: RIFF .... WAVE
	wavOK := append([]byte("RIFF"), []byte{0x24, 0x00, 0x00, 0x00}...)
	wavOK = append(wavOK, []byte("WAVE")...)
	wavOK = append(wavOK, []byte("data")...)
	wavOK = append(wavOK, []byte{0x00, 0x00, 0x00, 0x00}...)

	// Test 1: Valid upload
	out1, err := uploadAudioSample(&FileObj{Filename: "sample.wav", Data: wavOK}, uploadDir)
	if err != nil {
		fmt.Printf("Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	p1 := strings.TrimPrefix(out1, "Audio uploaded to ")
	if _, err := os.Stat(p1); os.IsNotExist(err) {
		fmt.Printf("Test 1 failed: file not found at %s\n", p1)
		os.Exit(1)
	}

	// Test 2: Case-insensitive extension
	out2, err := uploadAudioSample(&FileObj{Filename: "SOUND.WAV", Data: wavOK}, uploadDir)
	if err != nil {
		fmt.Printf("Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	p2 := strings.TrimPrefix(out2, "Audio uploaded to ")
	if _, err := os.Stat(p2); os.IsNotExist(err) {
		fmt.Printf("Test 2 failed: file not found at %s\n", p2)
		os.Exit(1)
	}

	// Test 3: Path-like filename should be reduced to basename and succeed
	out3, err := uploadAudioSample(&FileObj{Filename: "../safe.wav", Data: wavOK}, uploadDir)
	if err != nil {
		fmt.Printf("Test 3 failed: %v\n", err)
		os.Exit(1)
	}
	p3 := strings.TrimPrefix(out3, "Audio uploaded to ")
	absP3, _ := filepath.Abs(p3)
	absUploadDir, _ := filepath.Abs(uploadDir)
	if !strings.HasPrefix(absP3, absUploadDir+string(os.PathSeparator)) {
		fmt.Printf("Test 3 failed: path traversal detected incorrectly\n")
		os.Exit(1)
	}
	if filepath.Base(p3) != "safe.wav" {
		fmt.Printf("Test 3 failed: expected base 'safe.wav', got '%s'\n", filepath.Base(p3))
		os.Exit(1)
	}

	// Test 4: Invalid extension
	assertRaises(func() (string, error) {
		return uploadAudioSample(&FileObj{Filename: "x.mp3", Data: wavOK}, uploadDir)
	})

	// Test 5: Missing extension
	assertRaises(func() (string, error) {
		return uploadAudioSample(&FileObj{Filename: "noext", Data: wavOK}, uploadDir)
	})

	// Test 6: Invalid signature
	assertRaises(func() (string, error) {
		return uploadAudioSample(&FileObj{Filename: "bad.wav", Data: []byte("NOTWAVDATA")}, uploadDir)
	})

	// Test 7: Nil file object
	assertRaises(func() (string, error) {
		return uploadAudioSample(nil, uploadDir)
	})

	// Test 8: Empty filename
	assertRaises(func() (string, error) {
		return uploadAudioSample(&FileObj{Filename: "", Data: wavOK}, uploadDir)
	})

	// Test 9: Empty upload directory
	assertRaises(func() (string, error) {
		return uploadAudioSample(&FileObj{Filename: "a.wav", Data: wavOK}, "")
	})

	// Test 10: File size exceeds 2MB
	bigData := make([]byte, 2*1024*1024+1)
	copy(bigData, []byte("RIFF"))
	copy(bigData[8:12], []byte("WAVE"))
	assertRaises(func() (string, error) {
		return uploadAudioSample(&FileObj{Filename: "big.wav", Data: bigData}, uploadDir)
	})

	fmt.Println("All tests passed!")
}