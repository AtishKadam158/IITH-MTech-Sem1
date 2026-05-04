# Basic File Management Service (Task 1)

This project implements a simple **client-server based file management service** using low-level socket programming in Python.

The system allows a remote client to interact with files stored in a predefined server directory.

---

## Features

The server supports the following commands:

- **LIST** → Returns list of files in server directory
- **INFO <filename>** → Returns file metadata
- **GETSIZE <filename>** → Returns file size in bytes
- **QUIT** → Terminates connection

All communication is done using **plain-text ASCII strings**.

---

## Project Structure

