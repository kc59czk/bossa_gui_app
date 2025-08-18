# Bossa GUI Application

This project is a Python application that provides a graphical user interface (GUI) for interacting with the Bossa API. It allows users to log in, retrieve their portfolio data, and view it in a user-friendly format.

## Project Structure

```
bossa_gui_app
├── src
│   ├── bossa_api_client.py  # Contains the BossaAPIClient class for API interaction
│   ├── gui.py                # Implements the Tkinter GUI for the application
│   └── __init__.py          # Marks the directory as a Python package
├── requirements.txt          # Lists the dependencies required for the project
└── README.md                 # Documentation for the project
```

## Installation

To set up the project, follow these steps:

1. Clone the repository or download the project files.
2. Navigate to the project directory.
3. Install the required dependencies using pip:

   ```
   pip install -r requirements.txt
   ```

## Usage

1. Open a terminal and navigate to the project directory.
2. Run the application:

   ```
   python -m src.gui
   ```

3. Enter your Bossa API username and password in the GUI.
4. Click the "Log In" button to connect to the Bossa API and retrieve your portfolio data.
5. The portfolio information will be displayed in the GUI.

## Dependencies

This project requires the following Python libraries:

- `lxml`: For XML parsing.
- `python-dotenv`: For loading environment variables from a `.env` file.
- `tkinter`: For creating the GUI (included with standard Python installations).

## Notes

- Ensure that the Bossa API client application is installed and running on your local machine before using this GUI application.
- The application is designed to handle basic portfolio data retrieval and display. Further enhancements can be made to improve functionality and user experience.