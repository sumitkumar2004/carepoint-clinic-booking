# CarePoint Clinic Booking System

A simple and user-friendly clinic appointment booking website built with Python and Flask. It helps users check available appointment slots, book clinic visits, search existing bookings, and cancel appointments through a clean web interface.

## Features

- **View Appointment Slots** — Check available clinic appointment slots.
- **Book Appointments** — Create a booking using the available slots.
- **Search Bookings** — Find existing bookings using the available search options.
- **Cancel Appointments** — Cancel an existing appointment.
- **Responsive Interface** — Use the website on desktop and mobile devices.
- **REST API** — Access booking and slot functionality through Flask API endpoints.
- **Database Integration** — Store appointment and booking information using SQLite.

## Technologies Used

- Python
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript
- Git and GitHub
- Gunicorn for production hosting

## Project Structure

```text
clinic-booking-api/
├── app/
│   ├── templates/
│   │   └── index.html
│   ├── static/
│   │   ├── style.css
│   │   └── app.js
│   ├── routes.py
│   ├── services.py
│   ├── db.py
│   ├── validation.py
│   └── errors.py
├── tests/
├── run.py
├── requirements.txt
├── README.md
└── .gitignore
```

*Note: The structure above is illustrative. Keep the actual filenames and folders from your project.*

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/sumitkumar2004/carepoint-clinic-booking.git
cd carepoint-clinic-booking
```

### 2. Create a Virtual Environment

On Windows:

```powershell
py -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the following command in Command Prompt instead:

```cmd
venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
py run.py
```

Open your browser and visit:

http://127.0.0.1:5000

## API Endpoints

The application provides endpoints for working with appointment slots and bookings. The exact endpoints depend on the implementation.

Examples of endpoints used by the project:

| Endpoint | Purpose |
|---|---|
| `/` | Open the clinic booking website |
| `/api` | View API information |
| `/slots?limit=200` | Retrieve appointment slots |
| `/bookings?limit=100` | Retrieve bookings |

Use the appropriate HTTP methods and request fields defined in the application for creating or cancelling appointments.

## Running Tests

If the project includes pytest tests, run:

```bash
pytest
```

## Deployment

The application can be deployed as a Python web service using Render.

**Build Command**

```bash
pip install -r requirements.txt
```

**Start Command**

```bash
gunicorn run:app
```

Make sure `run.py` exposes the Flask application as `app`. Configure the correct root directory in Render if the application files are inside a subfolder.

## Future Improvements

- User registration and login
- Appointment reminders
- Doctor and patient dashboards
- Appointment status tracking
- Improved booking validation
- Integration with a persistent production database

## Security Note

This project is intended for learning and demonstration purposes. Before using it in a real clinic, add appropriate authentication, access controls, input validation, secure handling of patient information, and reliable database backups. Do not upload real patient records, passwords, or secret keys to a public repository.

## Author

**Sumit Kumar**

GitHub: [@sumitkumar2004](https://github.com/sumitkumar2004)

## License

No license has been specified yet. Add a license file if you want to define how others may use, modify, or distribute this project.
