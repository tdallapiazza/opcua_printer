FROM python:3-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN apk add git

RUN git clone https://github.com/tdallapiazza/opcua_printer.git

EXPOSE 4840

CMD [ "python", "./opcua_printer/server.py" ]
