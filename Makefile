.PHONY: run dbuild drun

run:
	python app.py

dbuild:
	docker build -t nedbat/songbasket:latest .

drun:
	docker run --name songbasket -p 8888:5000 --rm -e SECRET_KEY=secret nedbat/songbasket:latest

deploy:
	ssh drop1 "cd songbasket; git pull; cd ../drop1; make run"
