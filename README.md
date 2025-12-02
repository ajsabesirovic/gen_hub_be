# Gen Hub Backend

Django REST API backend for Gen Hub application.

## Features

- Django REST Framework API
- JWT Authentication
- User registration and email verification
- Custom user model
- OpenAPI/Swagger documentation

## Prerequisites

- Python 3.10+
- pip
- virtualenv (recommended)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd gen_hub_be
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and fill in your configuration values:
   - `SECRET_KEY`: Django secret key (generate a new one for production)
   - `DEBUG`: Set to `False` in production
   - `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
   - `DATABASE_URL`: Database connection URL (defaults to SQLite)
   - Email configuration: `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, etc.

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser** (optional)
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

## Environment Variables

Required environment variables (set in `.env` file):

- `SECRET_KEY`: Django secret key (required)
- `DEBUG`: Enable/disable debug mode (default: `True`)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_URL`: Database connection URL (defaults to SQLite: `sqlite:///db.sqlite3`)

Email configuration:
- `EMAIL_HOST`: SMTP server hostname
- `EMAIL_PORT`: SMTP server port
- `EMAIL_USE_TLS`: Use TLS for email (True/False)
- `EMAIL_HOST_USER`: SMTP username
- `EMAIL_HOST_PASSWORD`: SMTP password
- `DEFAULT_FROM_EMAIL`: Default sender email address

Optional:
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of CORS origins
- `GOOGLE_CLIENT_ID`: Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `JWT_SIGNING_KEY`: Custom JWT signing key

See `.env.example` for a complete list of available environment variables.

## Database

The project defaults to SQLite for development. For production, set `DATABASE_URL` to your PostgreSQL connection string:

```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

## API Documentation

Once the server is running, access the API documentation at:
- Swagger UI: http://localhost:8000/docs/
- OpenAPI Schema: http://localhost:8000/schema/

## Security Notes

- Never commit the `.env` file to version control
- Generate a new `SECRET_KEY` for production
- Set `DEBUG=False` in production
- Configure proper `ALLOWED_HOSTS` for production
- Use strong passwords for database and email credentials

## License

[Your License Here]

