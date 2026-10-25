# AIRA — AI-Powered Desktop Voice Assistant

**AIRA** is a Python-based desktop voice assistant designed to make computer interaction more convenient through voice commands, multilingual interaction, and locally running AI.

## Overview

AIRA combines a desktop graphical user interface with voice-assistant functionality and a local Large Language Model (LLM). The project explores how AI can support natural interaction with a computer while keeping AI inference on the user's own machine through Ollama.

## Problem Statement

Interacting with a computer often requires users to switch between applications, websites, and tools manually. AIRA aims to simplify selected tasks by providing a voice-based interface and AI-generated responses.

## Key Features

- **AI-powered responses:** Uses the Gemma 3:1B model through Ollama.
- **Multilingual interaction:** Designed to support English, Hindi, and Marathi.
- **Voice assistance:** Supports spoken interaction and text-to-speech responses.
- **Desktop automation:** Opens supported applications and websites through commands.
- **Graphical user interface:** Built with Python's Tkinter library.
- **Local AI inference:** Runs the language model locally through Ollama, without requiring paid OpenAI API credits for Gemma responses.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Tkinter | Desktop graphical user interface |
| Ollama | Local AI model runtime |
| Gemma 3:1B | Language model for AI responses |
| Speech and text-to-speech tools | Voice input and spoken responses |

## System Architecture

1. **User Input:** The user interacts with AIRA through supported voice commands.
2. **Command Processing:** The application processes supported commands and identifies the requested task.
3. **AI Response Generation:** The local Gemma model generates responses through Ollama when AI assistance is needed.
4. **Task Execution:** Supported commands can open selected applications or websites.
5. **Response Output:** AIRA displays responses and provides spoken output where supported.

## Running the Project

### Prerequisites

- Python installed on the computer
- Ollama installed and running
- The `gemma3:1b` model downloaded locally
- Required Python packages and any necessary audio dependencies

### Setup

1. Install Ollama from the official website: https://ollama.com/
2. Download the model using:

   ```bash
   ollama pull gemma3:1b
   ```

3. Open a terminal in the project directory.
4. Install the required Python packages once the project's dependency list is available.
5. Run the application:

   ```bash
   python aira_edited.py
   ```

## Future Scope

- Improve multilingual speech recognition and response accuracy.
- Enhance voice-command handling and error recovery.
- Add more desktop productivity features.
- Improve the user interface and accessibility.
- Expand testing across different systems and audio environments.

## Project Information

- **Project Name:** AIRA — AI-Powered Desktop Voice Assistant
- **Domain:** Artificial Intelligence and Data Science
- **Developer:** Sanika Kangude
- **Project Type:** Desktop AI Application

## Acknowledgements

This project explores the practical use of open-source AI tooling and Python-based desktop development to create a more natural way to interact with a computer.# AIRA-AI-Desktop-Assistant
Multilingual AI Desktop Voice Assistant using Python and Ollama
