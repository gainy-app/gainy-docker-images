FROM public.ecr.aws/lambda/python:3.9

ARG CODEARTIFACT_PIPY_URL

COPY requirements.txt /requirements.txt
RUN pip install --requirement /requirements.txt --index-url ${CODEARTIFACT_PIPY_URL}
