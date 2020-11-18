# https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xix-deployment-on-docker-containers

FROM python:3.8-alpine
RUN addgroup -S songbasket \
 && adduser -S -G songbasket --disabled-password --home /usr/src/app songbasket

WORKDIR /usr/src/app

COPY --chown=songbasket:songbasket requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -U pip \
 && pip3 install --no-cache-dir -r requirements.txt

COPY --chown=songbasket:songbasket . ./

USER songbasket

EXPOSE 5000
ENTRYPOINT ["gunicorn", "-b", ":5000", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
