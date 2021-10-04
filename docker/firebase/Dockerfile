FROM node:14

RUN npm install -g firebase-tools

WORKDIR /var/www
COPY . /var/www

CMD firebase emulators:start --only hosting