dev:
	python3 manage.py runserver

prod:
	gunicorn gen_hub_be.wsgi:application --bind 0.0.0.0:8000 --workers 3

migrate:
	python3 manage.py makemigrations
	python3 manage.py migrate
