# Auto Register Automation

This project automates registration flows on Android using `uiautomator2` and a custom Flow Runner.

## 🚀 Key Features

*   **Flow Runner**: Executes step-based automation flows defined in JSON.
*   **OTP Server**: Handles OTP/TOTP generation and synchronization.
*   **Browser-Based Clipboard Capture**: Robust method to extract clipboard data from Android devices where ADB clipboard access is blocked (Android 10+).

## 📋 Clipboard Capture Mechanism

Accessing the Android clipboard via ADB (`service call clipboard`) is restricted on modern Android versions. We solved this using a **Browser Bridge** approach:

1.  **Trigger Copy**: The automation interaction taps the "Copy" button in the target app.
2.  **Open Bridge**: The automation opens the Android Browser to `http://10.0.2.2:5000/paste`.
    *   `10.0.2.2` is the alias for the localhost of the machine running the emulator.
3.  **Capture & Send**: The web page uses the Clipboard API (`navigator.clipboard.readText()`) to read the copied content and immediately sends it to our local OTP Server.
4.  **Retrieve**: The Flow Runner polls the server to retrieve the captured text.

### Setup

1.  **Start the OTP Server**:
    ```bash
    python3 server/otp_server.py
    ```
    The server listens on port `5000`.

2.  **Define the Flow**:
    Use the `clipboard` action in your flow JSON:
    ```json
    {
      "name": "Copy Secret",
      "action": "clipboard",
      "params": {
        "index": 22,             // UI Element to tap (Copy button)
        "save_as": "totp_secret",// Variable to save the result
        "timeout": 15
      }
    }
    ```

3.  **Run the Flow**:
    ```bash
    python3 core/flow_runner.py flows/my_flow.json
    ```

## 🛠️ Components

### Core
*   `core/flow_runner.py`: Main engine executing the steps. Contains the `action_clipboard` logic.
*   `utils/droidrun.py`: Wrapper for UI interactions (tap, type, find).

### Server
*   `server/otp_server.py`: Lightweight HTTP server.
    *   `POST /otp`: Endpoint to receive internal OTPs.
    *   `GET /paste`: Serves the HTML bridge page.
    *   `GET /clipboard`: Endpoint receiving the clipboard data from the bridge page.

## 📱 Requirements

*   Android Emulator or Device connected via ADB.
*   Python 3.8+
*   `uiautomator2`
*   Network connection between Android Device and Host (enabled by default on Emulators).

## 📄 License

Internal Project.
