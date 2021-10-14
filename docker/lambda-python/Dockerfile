FROM public.ecr.aws/lambda/python:3.9

RUN pip install poetry

COPY poetry.lock pyproject.toml /var/
RUN cd /var && poetry export | python3 -mpip install -r /dev/stdin