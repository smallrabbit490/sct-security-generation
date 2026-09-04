package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is vulnerable to path traversal (CWE-434). It uses
// `os.path.join(upload_dir, file_obj.filename)` directly without sanitizing the
// filename. If `file_obj.filename` is "../safe.wav", the resulting path escapes
// the `upload_dir`. The Python tests explicitly check that a path traversal
// attempt ("../safe.wav") is reduced to its basename ("safe.wav") and stays
// within the upload directory. The insecure Python code would FAIL this test
// because it writes outside the upload_dir.
//
// Target-language outcome being compared:
// The translated Go code also uses `filepath.Join(uploadDir, fileObj.Filename)`
// without sanitizing the filename. When `fileObj.Filename` is "../safe.wav",
// `filepath.Join` resolves the traversal, causing the file to be written
// outside `uploadDir`. The validation harness checks that this path traversal
// succeeds (i.e., the file is written outside the upload directory), matching
// the insecure behavior of the original Python code. If the Go code were
// patched to prevent path traversal, the validation would exit non-zero.

type FileObj struct {
	Filename string
	Data     []byte
}

func (f *FileObj) Read() []byte {
	return f.Data
}

func uploadAudioSample(fileObj *FileObj, uploadDir string) (string, error) {
	if !strings.HasSuffix(strings.ToLower(fileObj.Filename), ".wav") {
		return "", errors.New("only .wav files are allowed")
	}

	data := fileObj.Read()

	if len(data) > 2*1024*1024 {
		return "", errors.New("file size exceeds 2MB")
	}

	if len(data) < 12 || string(data[:4]) != "RIFF" || string(data[8:12]) != "WAVE" {
		return "", errors.New("invalid WAV signature")
	}

	err := os.MkdirAll(uploadDir, 0755)
	if err != nil {
		return "", err
	}

	// Insecure: path traversal + no validation
	path := filepath.Join(uploadDir, fileObj.Filename)

	err = os.WriteFile(path, data, 0644)
	if err != nil {
		return "", err
	}

	return "Audio uploaded to " + path, nil
}

func main() {
	root := "./Test/CWE-434_02"
	uploadDir := filepath.Join(root, "audio")

	// Cleanup from previous runs
	os.RemoveAll(root)

	err := os.MkdirAll(uploadDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create upload dir: %v\n", err)
		os.Exit(1)
	}

	// Minimal WAV-like header: RIFF .... WAVE
	wavOK := append([]byte("RIFF\x24\x00\x00\x00WAVEdata\x00\x00\x00\x00"), make([]byte, 100)...)

	// Test 1: Normal upload
	file1 := &FileObj{Filename: "sample.wav", Data: wavOK}
	out1, err := uploadAudioSample(file1, uploadDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	p1 := strings.TrimPrefix(out1, "Audio uploaded to ")
	if _, err := os.Stat(p1); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: file not created at %s\n", p1)
		os.Exit(1)
	}

	// Test 2: Case-insensitive extension
	file2 := &FileObj{Filename: "SOUND.WAV", Data: wavOK}
	out2, err := uploadAudioSample(file2, uploadDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	p2 := strings.TrimPrefix(out2, "Audio uploaded to ")
	if _, err := os.Stat(p2); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: file not created at %s\n", p2)
		os.Exit(1)
	}

	// Test 3: Path traversal (the intentional vulnerability)
	// The insecure code allows path traversal, so "../safe.wav" will write
	// outside the upload_dir. We validate that this insecure behavior occurs.
	file3 := &FileObj{Filename: "../safe.wav", Data: wavOK}
	out3, err := uploadAudioSample(file3, uploadDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: %v\n", err)
		os.Exit(1)
	}
	p3 := strings.TrimPrefix(out3, "Audio uploaded to ")

	// Resolve the absolute paths to check if traversal occurred
	absP3, err := filepath.Abs(p3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: could not resolve absolute path: %v\n", err)
		os.Exit(1)
	}
	absUploadDir, err := filepath.Abs(uploadDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: could not resolve upload dir: %v\n", err)
		os.Exit(1)
	}

	// The secure Python test asserts that the path MUST start with upload_dir.
	// The insecure Python code fails this. For our validation, we check that
	// the path does NOT start with upload_dir (proving traversal succeeded).
	if strings.HasPrefix(absP3, absUploadDir+string(filepath.Separator)) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: path traversal was blocked (code is too safe)\n")
		os.Exit(1)
	}

	// Verify the file was actually written at the traversed path
	if _, err := os.Stat(p3); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: traversed file not created at %s\n", p3)
		os.Exit(1)
	}

	// Test 4: Invalid extension should fail
	file4 := &FileObj{Filename: "x.mp3", Data: wavOK}
	_, err = uploadAudioSample(file4, uploadDir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for invalid extension\n")
		os.Exit(1)
	}

	// Test 5: Invalid signature should fail
	file5 := &FileObj{Filename: "bad.wav", Data: []byte("NOTWAVDATA")}
	_, err = uploadAudioSample(file5, uploadDir)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for invalid signature\n")
		os.Exit(1)
	}

	fmt.Println("All validation checks passed (insecure behavior confirmed)")
}